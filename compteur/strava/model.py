"""StravaModel : les segments en favori et leur synchro, exposés à QML."""

import json
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

from PySide6.QtCore import Property, QObject, QPointF, QTimer, Signal, Slot

from ..model import segment_card
from ..segments import Result, StarredSegment
from ..storage import Writer, describe, write_atomic
from .client import Client, SyncError
from .decode import rounded_splits
from .files import CACHE_FILE, RECORDS_FILE, TOKENS_FILE, as_dict, load_cache
from .segments import kom_label, starred_segments, synced_text
from .sync import sync

ROW_PROFILE_POINTS = 40       # profil en vignette, dans la liste des segments
OFFLINE_RETRY_MS = 30_000     # au démarrage, sans réseau : nouvel essai toutes les 30 s...
OFFLINE_RETRIES = 10          # ... pendant 5 min, le temps que le Wi-Fi arrive


class StravaModel(QObject):
    """Expose à QML les segments en favori (`strava.segments`) et la synchro (`connected`, `syncing`, `error`,
    `syncedText`) ; `strava.sync()` la relance. Sans dossier (essais, captures, mesure), ni fichier ni réseau.
    `post(fonction)` fait appeler la fonction sur le fil de l'interface (voir relay.py). `writer` : fil d'écriture des
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
        temps de passage, il sert dès la sortie suivante, même sans réseau (voir reference). La côte d'essai du
        simulateur n'est pas gardée."""
        entries = self._cache.get("segments")
        entry = next((entry for entry in entries if isinstance(entry, dict) and entry.get("id") == result.segment.id),
                     None) if isinstance(entries, list) else None
        if self._folder is None or entry is None or not result.new_record:
            return
        self._records[str(result.segment.id)] = {
            "elapsed_s": round(result.elapsed_s, 1), "date": date.today().isoformat(),
            "strava_pr_s": as_dict(entry.get("pr")).get("elapsed_s"), "splits": rounded_splits(result.splits)}
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
