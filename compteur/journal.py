"""Fichier de reprise : la sortie en cours, écrite au fil de l'eau sur la carte SD, pour la retrouver après une coupure
(batterie vide, courant coupé, plantage).

Le moteur de calcul (ride.py) donne toujours le même résultat à partir des mêmes entrées. Le fichier garde donc ces
entrées, dans l'ordre : chaque mesure et chaque appui sur Start/Pause ou Lap (voir Ride.on_input). Les rejouer dans un
moteur neuf redonne la sortie telle qu'elle était : chrono, trace, tours, zones cardio.

Une ligne JSON par entrée, après une ligne d'en-tête (départ, parcours, réglages du moteur). Les mesures partent par
paquets de 30, soit toutes les 30 s ; Start/Pause, Lap et la fin de la sortie partent tout de suite. Peu d'écritures
pour ménager la carte, et au plus 30 s perdues. Le fil d'écriture force chaque paquet sur la carte, sans faire attendre
l'écran (voir storage.py).

Une coupure pendant une écriture peut laisser une ligne incomplète à la fin du fichier : elle est ignorée, comme tout ce
qui suivrait une ligne illisible. La sortie reprend ainsi dans un état cohérent, celui de sa dernière ligne complète.
Le fichier est effacé une fois la sortie enregistrée ou supprimée.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .ride import Ride, Sample
from .storage import Writer, sync_dir

FILE_NAME = "reprise.jsonl"  # dans le dossier des sorties
VERSION = 1
FLUSH_EVERY = 30  # mesures gardées en mémoire avant d'écrire : une écriture toutes les 30 s


@dataclass(frozen=True)
class Header:
    """Ce qu'il faut pour refaire la sortie : départ, parcours et réglages du moteur."""

    started_at: datetime
    route_file: str | None  # fichier GPX du parcours suivi ; None en sortie libre
    route_name: str         # nom de la sortie, gardé même si le fichier du parcours disparaît
    auto_pause: bool
    max_hr: float


@dataclass
class Recovered:
    """Une sortie retrouvée dans le fichier de reprise."""

    header: Header
    ride: Ride
    finished: bool     # terminée : elle attendait Enregistrer ou Supprimer
    size: int          # octets jusqu'à la fin de la dernière ligne complète
    written_at: float  # heure de la dernière écriture (horloge du système, en s)


def _header_line(header: Header) -> str:
    return json.dumps({"v": VERSION, "startedAt": header.started_at.isoformat(), "routeFile": header.route_file,
                       "routeName": header.route_name, "autoPause": header.auto_pause, "maxHr": header.max_hr},
                      ensure_ascii=False) + "\n"


def _parse_header(line: bytes) -> Header:
    try:
        data = json.loads(line)
        if not isinstance(data, dict) or data.get("v") != VERSION:
            raise ValueError("version inconnue")
        started_at = datetime.fromisoformat(data["startedAt"])
        route_file = data["routeFile"]
        if started_at.tzinfo is None or not (route_file is None or isinstance(route_file, str)):
            raise ValueError("départ ou parcours illisible")
        return Header(started_at, route_file, str(data["routeName"]), bool(data["autoPause"]), float(data["maxHr"]))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"en-tête illisible : {error}") from error


def _line(entry: tuple) -> str:
    """Une entrée du moteur, sur une ligne. Les nombres sont écrits exactement : la sortie rejouée est identique."""
    if entry[0] == "u":
        s = entry[1]
        values = ["u", s.t, s.speed_mps, s.heart_rate, s.lat, s.lon, s.altitude_m, s.heading_deg]
    else:
        values = [entry[0]]
    return json.dumps(values, separators=(",", ":")) + "\n"


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _entry(values) -> tuple:
    if isinstance(values, list) and values:
        if values[0] == "u" and len(values) == 8 and _number(values[1]) \
                and all(v is None or _number(v) for v in values[2:]):
            return "u", Sample(*values[1:])
        if values[0] in ("p", "l", "f") and len(values) == 1:
            return (values[0],)
    raise ValueError(f"entrée illisible : {values!r}")


def replay(ride: Ride, entry: tuple) -> None:
    """Rejoue une entrée sur le moteur."""
    if entry[0] == "u":
        ride.update(entry[1])
    elif entry[0] == "p":
        ride.start_pause()
    elif entry[0] == "l":
        ride.lap()


def load(path: Path) -> Recovered | None:
    """La sortie du fichier de reprise, rejouée dans un moteur neuf ; None s'il n'y a pas de fichier. ValueError si
    l'en-tête est illisible : il n'y a alors rien à reprendre."""
    try:
        data = path.read_bytes()
        written_at = path.stat().st_mtime
    except FileNotFoundError:
        return None
    lines = data.split(b"\n")[:-1]  # ce qui suit le dernier retour à la ligne est incomplet
    if not lines:
        raise ValueError("fichier de reprise sans en-tête")
    header = _parse_header(lines[0])
    ride = Ride(auto_pause=header.auto_pause, max_hr=header.max_hr)
    size = len(lines[0]) + 1
    finished = False
    for line in lines[1:]:
        if finished:
            break  # rien ne suit la fin de la sortie
        try:
            entry = _entry(json.loads(line))
            replay(ride, entry)
        except Exception:  # ligne coupée ou illisible : la sortie s'arrête à la dernière ligne complète
            break
        finished = entry[0] == "f"
        size += len(line) + 1
    return Recovered(header, ride, finished, size, written_at)


class Journal:
    """Le fichier de reprise de la sortie en cours. Ses méthodes s'appellent sur le fil de l'interface ; les écritures se
    font dans l'ordre sur le fil d'écriture. Si la carte refuse d'écrire, la sortie continue : ce qui n'a pas pu être
    écrit est gardé et repart à l'écriture suivante, et le fichier ne garde jamais de ligne coupée au milieu."""

    def __init__(self, path: Path, writer: Writer):
        self.path = path
        self._writer = writer
        self._lines: list[str] = []  # entrées pas encore confiées au fil d'écriture
        self._samples = 0            # dont mesures
        # Sur le fil d'écriture seulement :
        self._file = None
        self._fresh = True             # le fichier est à créer (sinon à reprendre à `_size`)
        self._size = 0                 # octets écrits et forcés sur la carte
        self._unwritten = bytearray()  # confié mais pas encore écrit

    # Fil de l'interface

    def start(self, header: Header, ride: Ride) -> None:
        """Départ : un fichier neuf, avec son en-tête, puis chaque entrée du moteur."""
        self._lines, self._samples = [_header_line(header)], 0
        self._writer.submit(lambda: self._reset(None))
        ride.on_input = self.record

    def resume(self, recovered: Recovered) -> None:
        """Sortie reprise : le même fichier continue, après sa dernière ligne complète (une sortie terminée n'y ajoute
        plus rien)."""
        self._lines, self._samples = [], 0
        size = recovered.size
        self._writer.submit(lambda: self._reset(size))
        if not recovered.finished:
            recovered.ride.on_input = self.record

    def record(self, entry: tuple) -> None:
        """Une entrée du moteur (voir Ride.on_input). Les mesures partent par paquets ; le reste, tout de suite."""
        self._lines.append(_line(entry))
        if entry[0] == "u":
            self._samples += 1
            if self._samples < FLUSH_EVERY:
                return
        self.flush()

    def flush(self) -> None:
        """Confie au fil d'écriture ce qui attend."""
        if not self._lines:
            return
        data = "".join(self._lines).encode("utf-8")
        self._lines, self._samples = [], 0
        self._writer.submit(lambda: self._write(data))

    def finish(self, ride: Ride) -> None:
        """Fin de la sortie : elle attend Enregistrer ou Supprimer, et doit survivre à une coupure pendant ce temps."""
        ride.on_input = None
        self._lines.append(_line(("f",)))
        self.flush()

    def discard(self) -> None:
        """Sortie supprimée : son fichier aussi."""
        self._lines, self._samples = [], 0
        self._writer.submit(self.delete)

    def close(self) -> None:
        """Fermeture de l'appli : ce qui attend est écrit, et le fichier reste pour la reprise."""
        self.flush()
        self._writer.submit(self._close)

    # Fil d'écriture

    def delete(self) -> None:
        """Efface le fichier : la sortie est enregistrée ou supprimée. À appeler sur le fil d'écriture."""
        self._close()
        self._unwritten.clear()
        self._fresh, self._size = True, 0
        try:
            self.path.unlink()
        except FileNotFoundError:
            return
        sync_dir(self.path.parent)

    def _reset(self, size: int | None) -> None:
        """Fichier neuf (None), ou fichier à reprendre à cette taille."""
        self._close()
        self._unwritten.clear()
        self._fresh, self._size = size is None, size or 0

    def _close(self) -> None:
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None

    def _open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self._fresh:
            self._file = open(self.path, "wb", buffering=0)
            self._fresh = False
            sync_dir(self.path.parent)
        else:
            self._file = open(self.path, "r+b", buffering=0)
            self._file.truncate(self._size)  # sans la ligne qu'une coupure aurait laissée incomplète
            self._file.seek(self._size)

    def _write(self, data: bytes) -> None:
        self._unwritten += data
        try:
            if self._file is None:
                self._open()
            pending = bytes(self._unwritten)
            written = 0
            while written < len(pending):
                written += self._file.write(pending[written:])
            os.fsync(self._file.fileno())
        except OSError:
            self._close()  # rouvert à l'écriture suivante, ramené à sa dernière ligne complète
            raise
        self._size += len(pending)
        self._unwritten.clear()
