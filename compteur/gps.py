"""GPS Adafruit Mini GPS PA1010D (puce MediaTek), sur le bus I2C : position, vitesse, cap, altitude, heure UTC, et
l'état de la réception (satellites dans le ciel et leur signal, précision).

Le GPS prépare chaque seconde des lignes de texte NMEA ; le compteur les lit sur le bus, par morceaux, dans un fil à
part. Quand il n'a rien à envoyer, le GPS répond par des sauts de ligne (0x0A). Un seul lecteur à la fois : deux
programmes qui lisent le GPS se partageraient ses lignes.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

ADDRESS = 0x10
KNOT_MPS = 1852 / 3600
CHUNK = 64               # octets lus par échange : le GPS en garde 255 au plus
IDLE_S = 0.25            # rien à lire : pause avant l'échange suivant (le GPS envoie ≈ 200 octets/s)
RETRY_S = 1.0            # bus en erreur : pause avant de réessayer
STALE_S = 3.0            # plus de position depuis 3 s : le GPS ne répond plus
SEARCH_S = 10.0          # GPS introuvable (pas encore branché) : on le cherche toutes les 10 s
# Heure plausible : avant d'avoir l'heure d'un satellite, le GPS part du 5 janvier 1980, soit « 80 », lu 2080
YEARS = range(2024, 2080)
ACCURACY_M_PER_HDOP = 3.0  # précision ≈ HDOP × 3 m : l'ordre de grandeur de la puce (3 m à ciel ouvert)
CONFIGURE_EVERY_S = 10.0  # réglage des messages renvoyé au plus toutes les 10 s, s'il a été perdu
MAX_LINE = 120           # une ligne NMEA fait 82 caractères au plus : au-delà, c'est du bruit


def checksum(body: str) -> int:
    """Somme de contrôle NMEA : ou exclusif des caractères entre « $ » et « * »."""
    value = 0
    for char in body.encode("ascii"):
        value ^= char
    return value


def command(body: str) -> bytes:
    """Commande pour le GPS, avec sa somme de contrôle (ex. « PMTK314,… »)."""
    return f"${body}*{checksum(body):02X}\r\n".encode("ascii")


# Messages voulus : position (RMC) et altitude (GGA) chaque seconde ; satellites utilisés et précision (GSA), satellites
# en vue et leur signal (GSV), toutes les 5 s. Par défaut le GPS envoie aussi VTG, et GSA et GSV chaque seconde : trois
# fois plus d'octets sur le bus partagé.
OUTPUT = command("PMTK314,0,1,0,1,5,5,0,0,0,0,0,0,0,0,0,0,0,0,0")
UNWANTED = {"VTG", "GLL"}  # l'un d'eux arrive : le GPS a oublié le réglage (coupure), on le renvoie
QUERY_FIRMWARE = command("PMTK605")  # réponse : PMTK705, version du micrologiciel
# Constellation d'après l'émetteur des lignes GSV ; les satellites SBAS (EGNOS) arrivent avec ceux du GPS, en 33 à 64
SYSTEMS = {"GP": "GPS", "GL": "GLONASS", "GA": "Galileo", "GB": "BeiDou", "BD": "BeiDou", "GQ": "QZSS", "QZ": "QZSS"}


def parse(line: str) -> tuple[str, list[str]] | None:
    """(type, champs) d'une ligne NMEA valide, ex. ("RMC", ["123519.000", "A", …]) ; None si elle est abîmée."""
    line = line.strip()
    if not line.startswith("$") or len(line) < 7 or line[-3] != "*":
        return None
    body = line[1:-3]
    try:
        if int(line[-2:], 16) != checksum(body):
            return None
    except (ValueError, UnicodeEncodeError):
        return None
    address, *fields = body.split(",")
    if address.startswith("P"):
        return address, fields  # message propre au fabricant (PMTK…) : gardé en entier
    return address[2:], fields  # sans l'émetteur (GP, GL, GA, GN…)


def coordinate(value: str, hemisphere: str) -> float | None:
    """« 4851.2345 », « N » → 48,853908 (degrés décimaux ; négatif au sud et à l'ouest)."""
    if not value or "." not in value:
        return None
    try:
        dot = value.index(".")
        degrees = float(value[:dot - 2]) + float(value[dot - 2:]) / 60
    except ValueError:
        return None
    return -degrees if hemisphere in ("S", "W") else degrees


def number(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class Satellite:
    system: str               # GPS, GLONASS, Galileo, BeiDou, QZSS, SBAS
    prn: int                  # numéro du satellite
    elevation: int | None     # degrés au-dessus de l'horizon
    azimuth: int | None       # degrés depuis le nord
    snr: int | None           # signal en dB-Hz ; None : en vue, mais pas capté


def satellite_system(talker: str, prn: int) -> str:
    if talker == "GP" and 33 <= prn <= 64:
        return "SBAS"
    if talker == "GP" and 193 <= prn <= 202:
        return "QZSS"
    return SYSTEMS.get(talker, talker)


@dataclass(frozen=True)
class Fix:
    """Dernier état connu du GPS. `valid` : position trouvée (sinon position, vitesse et cap sont absents)."""

    valid: bool = False
    lat: float | None = None
    lon: float | None = None
    speed_mps: float | None = None
    heading_deg: float | None = None
    altitude_m: float | None = None
    utc: datetime | None = None
    satellites: int = 0  # utilisés pour la position
    in_view: int = 0     # en vue, toutes constellations
    hdop: float | None = None  # dispersion horizontale : < 1 excellent, > 5 médiocre
    received: float | None = None  # horloge monotone de la dernière position (RMC)
    quality: int = 0           # GGA : 0 aucune position, 1 GPS, 2 corrigée par SBAS (EGNOS)…
    fix_type: int = 1          # GSA : 1 aucune position, 2 en 2D (sans altitude), 3 en 3D
    pdop: float | None = None  # dispersion en 3D
    vdop: float | None = None  # dispersion verticale
    used: frozenset[int] = frozenset()   # numéros des satellites utilisés (GSA)
    sky: tuple[Satellite, ...] = ()      # satellites en vue, avec leur place et leur signal (GSV)
    firmware: str | None = None          # version du micrologiciel (PMTK705)


@dataclass
class NmeaReader:
    """Assemble les lignes à partir des octets lus et tient le Fix à jour."""

    clock: Callable[[], float] = time.monotonic
    fix: Fix = Fix()
    unwanted: bool = False  # un message non voulu est arrivé : le réglage est à renvoyer
    _pending: bytearray = field(default_factory=bytearray)
    _in_view: dict[str, int] = field(default_factory=dict)  # satellites en vue, par constellation
    _sky: dict[str, list[Satellite]] = field(default_factory=dict)      # satellites en vue, par émetteur...
    _sky_next: dict[str, list[Satellite]] = field(default_factory=dict)  # ... et ceux de la série GSV en cours
    _gsa_open: bool = False  # une ligne GSA est arrivée depuis la dernière GGA (début de chaque seconde)
    lines: list[str] = field(default_factory=list)  # lignes valides reçues depuis la dernière lecture (pour l'essai)

    def feed(self, data: bytes) -> bool:
        """Ajoute les octets lus ; renvoie faux s'il n'y avait rien (que des sauts de ligne de remplissage)."""
        content = data.strip(b"\n")
        if not content:
            if self._pending and data:
                self._line_end()
            return False
        for byte in data:
            if byte == 0x0A:
                self._line_end()
            elif len(self._pending) < MAX_LINE:
                self._pending.append(byte)
            else:
                self._pending.clear()  # bruit sans fin de ligne
        return True

    def _line_end(self) -> None:
        text = self._pending.decode("ascii", errors="replace")
        self._pending.clear()
        if (parsed := parse(text)) is None:
            return
        self.lines.append(text.strip())
        kind, fields = parsed
        if kind == "RMC" and len(fields) >= 9:
            self._rmc(fields)
        elif kind == "GGA" and len(fields) >= 9:
            self._gga(fields)
        elif kind == "GSV" and len(fields) >= 3:
            talker = text.strip()[1:3]
            if fields[1] == "1" and (count := number(fields[2])) is not None:
                self._in_view[talker] = int(count)
                self.fix = replace(self.fix, in_view=sum(self._in_view.values()))
            self._gsv(talker, fields)
        elif kind == "GSA" and len(fields) >= 17:
            self._gsa(fields)
        elif kind == "PMTK705" and fields:
            self.fix = replace(self.fix, firmware=fields[0])
        elif kind in UNWANTED:
            self.unwanted = True

    def _rmc(self, fields: list[str]) -> None:
        valid = fields[1] == "A"
        utc = None
        clock, day = fields[0], fields[8]
        if len(clock) >= 6 and len(day) == 6 and clock[:6].isdigit() and day.isdigit():
            try:
                utc = datetime(2000 + int(day[4:6]), int(day[2:4]), int(day[0:2]), int(clock[0:2]), int(clock[2:4]),
                               int(clock[4:6]), tzinfo=timezone.utc)
            except ValueError:
                pass
            if utc is not None and utc.year not in YEARS:
                utc = None  # horloge du GPS pas encore réglée
        speed = number(fields[6])
        self.fix = replace(
            self.fix, valid=valid, utc=utc, received=self.clock(),
            lat=coordinate(fields[2], fields[3]) if valid else None,
            lon=coordinate(fields[4], fields[5]) if valid else None,
            speed_mps=speed * KNOT_MPS if valid and speed is not None else None,
            heading_deg=number(fields[7]) if valid else None)

    def _gga(self, fields: list[str]) -> None:
        used = number(fields[6])
        quality = number(fields[5]) or 0
        self.fix = replace(self.fix, satellites=int(used) if used is not None else 0, hdop=number(fields[7]),
                           altitude_m=number(fields[8]) if quality > 0 else None, quality=int(quality))
        self._gsa_open = False

    def _gsv(self, talker: str, fields: list[str]) -> None:
        """Une ligne d'une série GSV (4 satellites au plus par ligne) ; la série finie remplace la précédente."""
        total, index = number(fields[0]), number(fields[1])
        if total is None or index is None:
            return
        if index == 1:
            self._sky_next[talker] = []
        batch = self._sky_next.get(talker)
        if batch is None:
            return  # série prise en cours de route
        for i in range(3, len(fields) - 3, 4):
            prn = number(fields[i])
            if prn is None:
                continue
            elevation, azimuth, snr = (number(value) for value in fields[i + 1:i + 4])
            batch.append(Satellite(satellite_system(talker, int(prn)), int(prn),
                                   None if elevation is None else int(elevation),
                                   None if azimuth is None else int(azimuth), None if snr is None else int(snr)))
        if index == total:
            self._sky[talker] = self._sky_next.pop(talker)
            self.fix = replace(self.fix, sky=tuple(sat for sats in self._sky.values() for sat in sats))

    def _gsa(self, fields: list[str]) -> None:
        """Satellites utilisés : une ligne GSA par constellation, à réunir dans la même seconde."""
        prns = {int(value) for value in fields[2:14] if value.isdigit()}
        used = prns if not self._gsa_open else self.fix.used | prns
        self._gsa_open = True
        fix_type = number(fields[1])
        self.fix = replace(self.fix, used=frozenset(used), fix_type=int(fix_type) if fix_type else 1,
                           pdop=number(fields[14]), vdop=number(fields[16]))


@dataclass(frozen=True)
class Status:
    """État du GPS pour l'écran : le dernier Fix, et ce que le fil sait de la liaison."""

    fix: Fix
    present: bool = False              # le GPS envoie ses lignes
    age_s: float | None = None         # âge de la dernière ligne RMC
    first_fix_s: float | None = None   # première position, tant de secondes après le démarrage du fil
    errors: int = 0                    # échanges ratés sur le bus


class Receiver:
    """Le GPS lu en continu par un fil à part. `fix()` et `status()` donnent le dernier état, sans attendre le bus.
    Sans `bus`, `find()` le cherche toutes les 10 s (GPS pas encore branché)."""

    def __init__(self, bus=None, clock: Callable[[], float] = time.monotonic,
                 find: Callable[[], object | None] | None = None):
        self.bus = bus
        self.clock = clock
        self.errors = 0  # échanges ratés depuis le départ (fils mal branchés, bus saturé)
        self._find = find
        self._searched_at: float | None = None
        self._reader = NmeaReader(clock)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._configured_at: float | None = None
        self._queried_at: float | None = None  # dernière demande de la version du micrologiciel
        self._started = clock()
        self._last_data: float | None = None   # dernier échange qui a apporté des octets
        self._first_fix: float | None = None
        self._thread = threading.Thread(target=self._run, name="gps", daemon=True)

    def start(self) -> "Receiver":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def fix(self) -> Fix:
        with self._lock:
            fix = self._reader.fix
        if fix.received is not None and self.clock() - fix.received > STALE_S:
            return Fix(in_view=fix.in_view, firmware=fix.firmware)  # plus rien depuis 3 s : position perdue
        return fix

    def status(self) -> Status:
        now = self.clock()
        with self._lock:
            received, last, first = self._reader.fix.received, self._last_data, self._first_fix
        present = last is not None and now - last <= STALE_S
        fix = self.fix() if present else Fix(firmware=self.fix().firmware)
        return Status(fix, present, now - received if received is not None else None, first, self.errors)

    def take_lines(self) -> list[str]:
        """Lignes NMEA reçues depuis le dernier appel."""
        with self._lock:
            lines, self._reader.lines = self._reader.lines, []
        return lines

    def _configure(self) -> None:
        now = self.clock()
        if self._configured_at is None or now - self._configured_at >= CONFIGURE_EVERY_S:
            self.bus.transfer(ADDRESS, OUTPUT)
            self._configured_at = now
            self._reader.unwanted = False

    def _query_firmware(self) -> None:
        now = self.clock()
        if self._reader.fix.firmware is None and (self._queried_at is None
                                                  or now - self._queried_at >= CONFIGURE_EVERY_S):
            self.bus.transfer(ADDRESS, QUERY_FIRMWARE)
            self._queried_at = now

    def _search(self) -> bool:
        """Le bus du GPS, cherché s'il manque ; faux tant qu'on ne l'a pas."""
        if self.bus is None and self._find is not None:
            now = self.clock()
            if self._searched_at is None or now - self._searched_at >= SEARCH_S:
                self._searched_at = now
                self.bus = self._find()
        return self.bus is not None

    def _run(self) -> None:
        while not self._stop.is_set():
            if not self._search():
                self._stop.wait(RETRY_S)
                continue
            try:
                if self._configured_at is None or self._reader.unwanted:
                    self._configure()
                self._query_firmware()
                data = self.bus.transfer(ADDRESS, read=CHUNK)
            except OSError:
                self.errors += 1
                self._stop.wait(RETRY_S)
                continue
            with self._lock:
                busy = self._reader.feed(data)
                if busy:
                    self._last_data = self.clock()
                if self._first_fix is None and self._reader.fix.valid:
                    self._first_fix = self.clock() - self._started
                if len(self._reader.lines) > 200:  # personne ne les prend : on garde les dernières
                    del self._reader.lines[:-50]
            if not busy:
                self._stop.wait(IDLE_S)
