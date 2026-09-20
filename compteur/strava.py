"""Strava : les segments en favori, gardés sur la carte SD pour rouler sans réseau, et leur synchro.

tools/strava/connecter.py relie une fois pour toutes l'appareil au compte : ses jetons sont dans
~/.config/canyon-compteur/strava.json, les segments dans segments.json, à côté, et les records battus avec le compteur
dans records.json. La synchro ne relit que ce qui manque ou a vieilli, car Strava limite les lectures (100 par quart
d'heure). Elle passe par son propre fil : l'écran n'attend jamais le réseau, et une synchro lente ne retarde pas
l'écriture des sorties.
"""

import http.client
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Property, QObject, QPointF, QTimer, Signal, Slot

from .model import segment_card
from .ride import Sample
from .route import Point, Route
from .segments import Best, Result, StarredSegment, record_splits
from .storage import Writer, describe, write_atomic
from .summary import MONTHS

STRAVA_DIR = Path.home() / ".config" / "canyon-compteur"
TOKENS_FILE = "strava.json"   # jetons d'accès, posés par tools/strava/connecter.py
CACHE_FILE = "segments.json"  # segments en favori, tels qu'à la dernière synchro
RECORDS_FILE = "records.json"  # records battus avec le compteur, en attendant que Strava les donne
API_URL = "https://www.strava.com/api/v3"
TOKEN_URL = "https://www.strava.com/oauth/token"
TIMEOUT_S = 20
REFRESH_BEFORE_S = 600        # jeton d'accès renouvelé 10 min avant son expiration
DETAIL_MAX_AGE_S = 7 * 86400  # KOM, QOM et record relus une fois par semaine au plus
PAGE_SIZE = 200               # segments par page, dans la liste des favoris
ROW_PROFILE_POINTS = 40       # profil en vignette, dans la liste des segments
OFFLINE_RETRY_MS = 30_000     # au démarrage, sans réseau : nouvel essai toutes les 30 s...
OFFLINE_RETRIES = 10          # ... pendant 5 min, le temps que le Wi-Fi arrive
RECONNECT = "accès refusé, relancer tools/strava/connecter.py"


class SyncError(Exception):
    """Synchro impossible ; `str(erreur)` le dit en quelques mots, pour l'écran. `offline` : pas de réseau, ou Strava
    injoignable, un nouvel essai peut marcher. `status` : code HTTP de la réponse, s'il y en a une."""

    def __init__(self, message: str, offline: bool = False, status: int | None = None):
        super().__init__(message)
        self.offline = offline
        self.status = status


def _http_error(status: int) -> SyncError:
    if status in (401, 403):
        return SyncError(RECONNECT, status=status)
    if status == 429:
        return SyncError("limite de Strava atteinte, réessayer dans 15 min", status=status)
    if status >= 500:
        return SyncError("Strava ne répond pas", offline=True, status=status)
    return SyncError(f"erreur Strava ({status})", status=status)


def _call(request: urllib.request.Request) -> object:
    """Envoie la requête et renvoie sa réponse JSON ; SyncError si elle échoue."""
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise _http_error(error.code) from error
    except urllib.error.URLError as error:
        raise SyncError("pas de réseau", offline=True) from error
    except (OSError, http.client.HTTPException) as error:  # délai dépassé, connexion coupée en route
        raise SyncError("Strava ne répond pas", offline=True) from error
    except ValueError as error:
        raise SyncError("réponse de Strava illisible") from error


def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def save_tokens(path: Path, tokens: dict) -> None:
    """Écrit les jetons, lisibles par leur seul propriétaire."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(path, json.dumps(tokens, indent=2).encode("utf-8"), mode=0o600)


class Client:
    """Lectures sur l'API de Strava, avec le jeton d'accès du fichier, renouvelé quand il expire."""

    def __init__(self, tokens_file: Path, api_url: str | None = None, token_url: str | None = None,
                 clock: Callable[[], float] = time.time):
        self.tokens_file = tokens_file
        self.api_url = api_url or API_URL
        self.token_url = token_url or TOKEN_URL
        self.clock = clock
        try:
            self.tokens = json.loads(tokens_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise SyncError("pas relié à Strava") from error
        if not isinstance(self.tokens, dict) or not self.tokens.get("refresh_token"):
            raise SyncError("pas relié à Strava")

    def get(self, path: str, **params) -> object:
        """Lecture sur l'API. Un jeton refusé est renouvelé une fois : sans réseau au démarrage, l'horloge du Pi peut se
        tromper sur son expiration."""
        try:
            expires_at = float(self.tokens.get("expires_at", 0))
        except (TypeError, ValueError):
            expires_at = 0.0
        if expires_at - REFRESH_BEFORE_S <= self.clock():
            self.refresh()
        url = self.api_url + path + ("?" + urllib.parse.urlencode(params) if params else "")
        try:
            return self._get(url)
        except SyncError as error:
            if error.status != 401:
                raise
        self.refresh()
        return self._get(url)

    def _get(self, url: str) -> object:
        token = self.tokens.get("access_token", "")
        return _call(urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}))

    def refresh(self) -> None:
        """Nouveau jeton d'accès. Strava peut aussi remplacer le jeton de renouvellement, et l'ancien ne vaut alors
        plus : les deux sont écrits tout de suite."""
        form = urllib.parse.urlencode({
            "client_id": self.tokens.get("client_id", ""),
            "client_secret": self.tokens.get("client_secret", ""),
            "grant_type": "refresh_token",
            "refresh_token": self.tokens["refresh_token"],
        }).encode()
        try:
            answer = _call(urllib.request.Request(self.token_url, data=form, method="POST"))
        except SyncError as error:
            if error.status in (400, 401, 403):  # accès retiré, ou jeton remplacé depuis un autre appareil
                raise SyncError(RECONNECT, status=401) from error
            raise
        try:
            renewed = {"access_token": str(answer["access_token"]), "refresh_token": str(answer["refresh_token"]),
                       "expires_at": float(answer["expires_at"])}
        except (TypeError, KeyError, ValueError) as error:
            raise SyncError("réponse de Strava illisible") from error
        self.tokens |= renewed
        try:
            save_tokens(self.tokens_file, self.tokens)
        except OSError as error:  # ils valent jusqu'à l'arrêt ; au prochain démarrage, il faudra peut-être relier
            print(f"Jetons Strava pas enregistrés : {error}", file=sys.stderr)


def load_cache(path: Path) -> dict:
    """Le cache des segments (ou les records du compteur) ; vide s'il manque ou est illisible."""
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return _dict(cache)


def parse_time(text: object) -> float | None:
    """Un temps tel que Strava l'affiche (« 58s », « 4:37 », « 1:02:03 »), en secondes ; None s'il est illisible."""
    if not isinstance(text, str):
        return None
    text = text.strip().lower()
    try:
        if text.endswith("s"):
            seconds = float(text[:-1])
        else:
            parts = text.split(":")
            if len(parts) > 3:
                return None
            seconds = 0.0
            for part in parts:
                seconds = seconds * 60 + float(part)
    except ValueError:
        return None
    return seconds if math.isfinite(seconds) and seconds > 0 else None


def _record(segment: dict) -> dict | None:
    """Record perso, s'il est dans la réponse (Strava le réserve peut-être aux abonnés)."""
    effort = _dict(segment.get("athlete_pr_effort"))
    stats = _dict(segment.get("athlete_segment_stats"))
    elapsed = effort.get("elapsed_time") or stats.get("pr_elapsed_time")
    if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed <= 0:
        return None
    date = effort.get("start_date_local") or stats.get("pr_date")
    return {"elapsed_s": float(elapsed), "date": date[:10] if isinstance(date, str) and date else None,
            "activity_id": effort.get("activity_id") or stats.get("pr_activity_id"), "effort_id": effort.get("id")}


def _by_type(streams: object) -> dict:
    """Flux Strava rangés par type (ils arrivent en liste sans key_by_type)."""
    if isinstance(streams, list):
        return {stream.get("type"): stream for stream in streams if isinstance(stream, dict)}
    return _dict(streams)


def _points(streams: object) -> list[list]:
    """Tracé d'un segment, [lat, lon, altitude] point par point, depuis ses flux Strava."""
    streams = _by_type(streams)
    try:
        points = [[round(float(lat), 6), round(float(lon), 6), None] for lat, lon in streams["latlng"]["data"]]
        altitude = _dict(streams.get("altitude")).get("data") or []
        if len(altitude) == len(points):
            for point, ele in zip(points, altitude):
                point[2] = round(float(ele), 1)
    except (TypeError, KeyError, ValueError, AttributeError) as error:
        raise SyncError("réponse de Strava illisible") from error
    return points


def _samples(streams: object) -> list[Sample]:
    """Une sortie, mesure par mesure (heure et position), depuis ses flux Strava ; vide sans positions."""
    streams = _by_type(streams)
    try:
        return [Sample(t=float(t), lat=float(lat), lon=float(lon))
                for t, (lat, lon) in zip(streams["time"]["data"], streams["latlng"]["data"])]
    except (TypeError, KeyError, ValueError, AttributeError):
        return []


def _route(entry: dict) -> Route:
    """Tracé d'un segment du cache ; TypeError, KeyError ou ValueError s'il est incomplet."""
    name = str(entry["name"])
    return Route(name, [Point(float(lat), float(lon), None if ele is None else float(ele))
                        for lat, lon, ele in entry["points"]])


def _rounded(splits) -> list[list[float]]:
    return [[round(d, 1), round(t, 1)] for d, t in splits]


def _splits(value: object) -> tuple[tuple[float, float], ...]:
    try:
        return tuple((float(d), float(t)) for d, t in value)
    except (TypeError, ValueError):
        return ()


def _ghost(entry: dict, streams: object) -> list[list[float]]:
    """Fantôme du record : ses temps de passage, retrouvés dans la sortie du record (voir segments.record_splits)."""
    try:
        route, elapsed = _route(entry), float(entry["pr"]["elapsed_s"])
    except (TypeError, KeyError, ValueError):
        return []
    return _rounded(record_splits(route, _samples(streams), elapsed))


def _athlete(data: dict) -> dict:
    return {key: data.get(key) for key in ("id", "firstname", "sex")}


def sync(client: Client, cache_file: Path) -> dict:
    """Met le cache à jour avec les segments vélo en favori : la liste d'abord, puis le tracé de ceux qui n'en ont pas,
    les détails (KOM, QOM, record) de ceux relus il y a plus d'une semaine, et le fantôme de chaque nouveau record. Le
    cache est écrit même si la synchro s'arrête en route (limite de lectures, réseau perdu) : ce qui est arrivé sert
    déjà, et la synchro suivante reprend le reste. Renvoie le cache ; SyncError si la synchro n'est pas allée au
    bout."""
    now = client.clock()
    old = load_cache(cache_file)
    athlete = _athlete(_dict(client.tokens.get("athlete"))) if client.tokens.get("athlete") else {}
    cached_athlete = _dict(old.get("athlete"))
    known = {entry.get("id"): entry for entry in old.get("segments", []) if isinstance(entry, dict)} \
        if isinstance(old.get("segments"), list) else {}
    if athlete.get("id") is not None and cached_athlete.get("id") not in (None, athlete["id"]):
        known = {}  # relié à un autre compte : ses segments ne sont plus les nôtres
    if not athlete:
        athlete = cached_athlete or _athlete(_dict(client.get("/athlete")))

    starred = []
    page = 1
    while True:
        batch = client.get("/segments/starred", page=page, per_page=PAGE_SIZE)
        if not isinstance(batch, list):
            raise SyncError("réponse de Strava illisible")
        starred += batch
        if len(batch) < PAGE_SIZE:
            break
        page += 1

    entries = []
    for summary in starred:
        if not isinstance(summary, dict) or summary.get("activity_type") != "Ride" \
                or not isinstance(summary.get("id"), int):
            continue  # segments de course à pied, ou mal formés
        entry = dict(known.get(summary["id"], {"id": summary["id"], "detail_at": 0}))
        entry["name"] = str(summary.get("name") or entry.get("name") or "Segment")
        entry["pr"] = _record(summary) or entry.get("pr")
        entries.append(entry)

    # Les tracés qui manquent d'abord (sans eux, un segment ne sert à rien), puis les détails les plus vieux
    error = None
    todo = sorted((entry for entry in entries
                   if not entry.get("points") or now - entry.get("detail_at", 0) > DETAIL_MAX_AGE_S),
                  key=lambda entry: (bool(entry.get("points")), entry.get("detail_at", 0)))
    for entry in todo:
        try:
            if not entry.get("points"):
                entry["points"] = _points(client.get(f"/segments/{entry['id']}/streams", keys="latlng,altitude",
                                                     key_by_type="true"))
            detail = _dict(client.get(f"/segments/{entry['id']}"))
        except SyncError as failure:
            if failure.status == 404:  # segment supprimé, ou devenu privé
                entries.remove(entry)
                continue
            error = failure
            break
        xoms = _dict(detail.get("xoms"))
        entry |= {"name": str(detail.get("name") or entry["name"]), "kom_s": parse_time(xoms.get("kom")),
                  "qom_s": parse_time(xoms.get("qom")), "pr": _record(detail) or entry.get("pr"), "detail_at": now}

    # Enfin le fantôme de chaque record : la sortie du record, lue une fois (une lecture par record)
    if error is None:
        for entry in entries:
            activity = _dict(entry.get("pr")).get("activity_id")
            if not activity or not entry.get("points") or _dict(entry.get("ghost")).get("activity_id") == activity:
                continue
            try:
                streams = client.get(f"/activities/{activity}/streams", keys="time,latlng", key_by_type="true")
            except SyncError as failure:
                if failure.status != 404:
                    error = failure
                    break
                streams = None  # sortie supprimée : pas de fantôme, l'allure régulière le remplace
            entry["ghost"] = {"activity_id": activity, "splits": _ghost(entry, streams)}

    cache ={"athlete": athlete, "synced_at": now if error is None else old.get("synced_at"), "segments": entries}
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(cache_file, json.dumps(cache, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    except OSError as failure:
        raise SyncError(f"segments pas enregistrés ({describe(failure)})") from failure
    if error is not None:
        raise error
    return cache


def _reference(entry: dict, records: dict) -> Best | None:
    """Record auquel se comparer : celui de Strava, avec son fantôme, sauf si le compteur a fait mieux depuis. Le record
    du compteur tient tant que Strava donne encore celui qu'il a battu ; dès que Strava en donne un autre (la sortie
    envoyée, en principe), c'est son temps qui fait foi."""
    pr = _dict(entry.get("pr"))
    strava_s = pr.get("elapsed_s")
    local = _dict(records.get(str(entry.get("id"))))
    if local and local.get("strava_pr_s") == strava_s:
        try:
            if strava_s is None or float(local["elapsed_s"]) < float(strava_s):
                return Best(float(local["elapsed_s"]), _splits(local.get("splits")), local.get("date"))
        except (TypeError, KeyError, ValueError):
            pass  # record du compteur illisible : celui de Strava
    if not isinstance(strava_s, (int, float)) or strava_s <= 0:
        return None
    ghost = _dict(entry.get("ghost"))
    splits = _splits(ghost.get("splits")) if ghost.get("activity_id") == pr.get("activity_id") else ()
    return Best(float(strava_s), splits, pr.get("date"))


def starred_segments(cache: dict, records: dict | None = None) -> list[StarredSegment]:
    """Les segments du cache, prêts à suivre, avec leur record (`records` : ceux battus avec le compteur). Neufs à
    chaque appel : une sortie change leur record. Un segment sans tracé (pas encore arrivé) est laissé de côté."""
    entries = cache.get("segments")
    if not isinstance(entries, list):
        return []
    female = _dict(cache.get("athlete")).get("sex") == "F"
    segments = []
    for entry in entries:
        try:
            kom_s = entry.get("qom_s" if female else "kom_s")
            segments.append(StarredSegment(int(entry["id"]), str(entry["name"]), _route(entry),
                                           pr=_reference(entry, records or {}),
                                           kom=Best(float(kom_s)) if kom_s else None))
        except (TypeError, KeyError, ValueError, AttributeError):
            continue
    return segments


def kom_label(cache: dict) -> str:
    """KOM ou QOM, selon le profil Strava."""
    return "QOM" if _dict(cache.get("athlete")).get("sex") == "F" else "KOM"


def synced_text(timestamp: object, now: datetime | None = None) -> str:
    """Moment de la dernière synchro : « aujourd'hui à 09:41 », « hier à 18:02 », « le 3 juin »."""
    if not isinstance(timestamp, (int, float)) or timestamp <= 0:
        return ""
    when = datetime.fromtimestamp(timestamp)
    today = (now or datetime.now()).date()
    if when.date() == today:
        return f"aujourd'hui à {when:%H:%M}"
    if when.date() == today - timedelta(days=1):
        return f"hier à {when:%H:%M}"
    return f"le {when.day} {MONTHS[when.month - 1]}"


class StravaModel(QObject):
    """Expose à QML les segments en favori (`strava.segments`) et la synchro (`connected`, `syncing`, `error`,
    `syncedText`) ; `strava.sync()` la relance. Sans dossier (essais, captures, mesure), ni fichier ni réseau.
    `post(fonction)` fait appeler la fonction sur le fil de l'interface (voir app.py). `writer` : fil d'écriture des
    sorties, où s'écrivent aussi les records du compteur (sans lui, celui de la synchro)."""

    changed = Signal()

    def __init__(self, folder: Path | None, post: Callable[[Callable[[], None]], None],
                 parent: QObject | None = None, writer: Writer | None = None):
        super().__init__(parent)
        self._folder = folder
        self._post = post
        self._writer: Writer | None = None  # fil de la synchro, lancé à la première
        self._records_writer = writer
        self._records = load_cache(folder / RECORDS_FILE) if folder is not None else {}
        self._syncing = False
        self._error = ""
        self._retries = 0
        self._retry = QTimer(self)
        self._retry.setSingleShot(True)
        self._retry.setInterval(OFFLINE_RETRY_MS)
        self._retry.timeout.connect(lambda: self._start(self._retries))
        self._connected = self._has_tokens()
        self._show(load_cache(folder / CACHE_FILE) if folder is not None else {})

    def _has_tokens(self) -> bool:
        return self._folder is not None and (self._folder / TOKENS_FILE).is_file()

    def _show(self, cache: dict) -> None:
        self._cache = cache
        self.kom_label = kom_label(cache)
        self._cards = [
            segment_card(segment, self.kom_label) | {
                "prDate": segment.pr.date if segment.pr else None,
                "profile": [QPointF(d / 1000, ele) for d, ele in segment.route.profile(ROW_PROFILE_POINTS)],
            }
            for segment in starred_segments(cache, self._records)
        ]

    def _get_connected(self) -> bool:
        return self._connected

    def _get_syncing(self) -> bool:
        return self._syncing

    def _get_error(self) -> str:
        return self._error

    def _get_synced_text(self) -> str:
        return synced_text(self._cache.get("synced_at"))

    def _get_segments(self) -> list:
        return self._cards

    connected = Property(bool, _get_connected, notify=changed)      # jetons posés par connecter.py
    syncing = Property(bool, _get_syncing, notify=changed)
    error = Property(str, _get_error, notify=changed)               # dernière synchro inachevée, en quelques mots
    syncedText = Property(str, _get_synced_text, notify=changed)    # dernière synchro complète ; "" jamais
    segments = Property("QVariantList", _get_segments, notify=changed)

    def starred(self) -> list[StarredSegment]:
        """Les segments à suivre pendant une nouvelle sortie."""
        return starred_segments(self._cache, self._records)

    def keep_record(self, result: Result) -> None:
        """Record battu (ou premier temps) sur un segment en favori, pendant une sortie : gardé sur la carte SD avec ses
        temps de passage, il sert dès la sortie suivante, même sans réseau (voir _reference). La côte d'essai du
        simulateur n'est pas gardée."""
        entries = self._cache.get("segments")
        entry = next((entry for entry in entries if isinstance(entry, dict) and entry.get("id") == result.segment.id),
                     None) if isinstance(entries, list) else None
        if self._folder is None or entry is None or not result.new_record:
            return
        self._records[str(result.segment.id)] = {
            "elapsed_s": round(result.elapsed_s, 1), "date": date.today().isoformat(),
            "strava_pr_s": _dict(entry.get("pr")).get("elapsed_s"), "splits": _rounded(result.splits)}
        path = self._folder / RECORDS_FILE
        data = json.dumps(self._records, separators=(",", ":")).encode("utf-8")
        (self._records_writer or self._thread()).submit(lambda: write_atomic(path, data), self._record_written)
        self._show(self._cache)
        self.changed.emit()

    def _record_written(self, _result: object, error: Exception | None) -> None:
        if error is not None:  # il sert jusqu'à l'arrêt
            print(f"Record Strava pas enregistré : {describe(error)}", file=sys.stderr, flush=True)

    def _thread(self) -> Writer:
        """Fil de la synchro, lancé à la première tâche."""
        if self._writer is None:
            self._writer = Writer(self._post, name="strava")
        return self._writer

    @Slot()
    def check(self) -> None:
        """Regarde si l'appareil est relié : les jetons ont pu être posés depuis le démarrage (connecter.py --pi)."""
        connected = self._has_tokens()
        if connected != self._connected:
            self._connected = connected
            self.changed.emit()

    @Slot()
    def sync(self) -> None:
        """Synchronise (bouton Synchroniser), sauf si c'est déjà en cours ou si l'appareil n'est pas relié."""
        self._retry.stop()
        self._start(0)

    def sync_at_start(self) -> None:
        """Synchro du démarrage : sans réseau, elle réessaie quelques minutes."""
        self._start(OFFLINE_RETRIES)

    def _start(self, retries: int) -> None:
        self.check()
        if self._syncing or not self._connected:
            return
        self._retries = retries
        self._syncing, self._error = True, ""
        self.changed.emit()
        folder = self._folder

        def task():
            try:
                return sync(Client(folder / TOKENS_FILE), folder / CACHE_FILE), None
            except SyncError as error:
                return load_cache(folder / CACHE_FILE), error

        self._thread().submit(task, self._synced)

    def _synced(self, result: tuple[dict, SyncError | None] | None, failure: Exception | None) -> None:
        self._syncing = False
        if failure is not None:  # erreur imprévue : un bogue, le cache reste tel quel
            print(f"Synchro Strava arrêtée : {failure!r}", file=sys.stderr, flush=True)
            cache, error = self._cache, SyncError("erreur inattendue")
        else:
            cache, error = result
        self._error = str(error) if error is not None else ""
        self._show(cache)  # même inachevée : ce qui est arrivé sert déjà
        self.changed.emit()
        if error is None:
            print(f"Synchro Strava : {len(self._cards)} segments", flush=True)
            return
        print(f"Synchro Strava inachevée : {error}", file=sys.stderr, flush=True)
        if error.offline and self._retries > 0:
            self._retries -= 1
            self._retry.start()

    def close(self) -> None:
        """À la fermeture : une synchro en cours a quelques secondes pour finir, puis elle est abandonnée (le cache
        s'écrit d'un coup, jamais à moitié)."""
        self._retry.stop()
        if self._writer is not None and not self._writer.close(timeout=5):
            print("Synchro Strava abandonnée à la fermeture", file=sys.stderr)
