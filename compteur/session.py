"""Session : les parcours proposés à l'accueil, le départ, la fin d'une sortie et son résumé ;
l'historique des sorties enregistrées."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Property, QObject, QPointF, Signal, Slot

from . import history
from .ride import Ride
from .route import Route
from .summary import OUTLINE_POINTS, PROFILE_POINTS, thinned

THUMBNAIL_POINTS = 48  # points du tracé en vignette, dans la liste des sorties


def route_card(route: Route) -> dict:
    """Ce que l'accueil montre d'un parcours : nom, distance, dénivelé,
    tracé ramené entre 0 et 1, profil (distance en km, altitude en m)."""
    return {
        "name": route.name,
        "distanceKm": route.length_m / 1000,
        "ascentM": route.ascent_m,
        "outline": route.outline(OUTLINE_POINTS),
        "profile": [(d / 1000, ele) for d, ele in route.profile(PROFILE_POINTS)],
    }


def _points(pairs: list) -> list[QPointF]:
    """Des points que l'interface sait dessiner."""
    return [QPointF(x, y) for x, y in pairs]


def _drawable(summary: dict) -> dict:
    """Le résumé d'une sortie, avec son tracé et son profil en points que l'interface sait dessiner."""
    return summary | {"outline": _points(summary.get("outline", [])),
                      "profile": _points(summary.get("profile", []))}


class SessionModel(QObject):
    """Expose à QML les parcours de l'accueil (`session.routes`) et le résumé de la sortie terminée
    (`session.summary`) ; lance, termine, enregistre ou supprime la sortie ; éteint le compteur.

    `on_start(route)` reçoit le parcours choisi, ou None pour une sortie libre ; `on_finish()` termine la sortie et
    renvoie son résumé ; `on_save(done)` l'enregistre, puis appelle `done(None)`, ou `done(message)` en cas d'échec ;
    `on_discard()` l'oublie ; `on_power_off()` éteint le compteur, ou renvoie ce qui l'en empêche.
    """

    started = Signal()
    finished = Signal()
    summaryChanged = Signal()
    savingChanged = Signal()
    saved = Signal()               # sortie enregistrée : l'écran peut la quitter
    powerOffFailed = Signal(str)   # arrêt refusé, en quelques mots

    def __init__(self, routes: list[Route], on_start: Callable[[Route | None], None],
                 on_finish: Callable[[], dict], on_save: Callable[[Callable[[str | None], None]], None],
                 on_discard: Callable[[], None], on_power_off: Callable[[], str | None],
                 parent: QObject | None = None):
        super().__init__(parent)
        self._routes = routes
        self._on_start = on_start
        self._on_finish = on_finish
        self._on_save = on_save
        self._on_discard = on_discard
        self._on_power_off = on_power_off
        self._summary: dict = {}
        self._saving = False
        self._save_error = ""
        self._cards = []
        for route in routes:
            card = route_card(route)
            card["outline"] = _points(card["outline"])
            card["profile"] = _points(card["profile"])
            self._cards.append(card)

    def _get_routes(self) -> list:
        return self._cards

    def _get_summary(self) -> dict:
        return self._summary

    def _get_saving(self) -> bool:
        return self._saving

    def _get_save_error(self) -> str:
        return self._save_error

    routes = Property("QVariantList", _get_routes, constant=True)
    summary = Property("QVariantMap", _get_summary, notify=summaryChanged)
    saving = Property(bool, _get_saving, notify=savingChanged)        # enregistrement en cours
    saveError = Property(str, _get_save_error, notify=savingChanged)  # dernier échec, en quelques mots ; "" sinon

    def _set_saving(self, saving: bool, error: str = "") -> None:
        self._saving, self._save_error = saving, error
        self.savingChanged.emit()

    def show(self, summary: dict) -> None:
        """Résumé d'une sortie terminée, en attente d'Enregistrer ou Supprimer (sortie reprise au démarrage)."""
        self._summary = _drawable(summary)
        self._set_saving(False)
        self.summaryChanged.emit()

    @Slot(int)
    def start(self, index: int) -> None:
        """Départ sur le parcours d'indice `index`, ou en sortie libre (−1)."""
        self._on_start(self._routes[index] if 0 <= index < len(self._routes) else None)
        self.started.emit()

    @Slot()
    def finish(self) -> None:
        """Fin de la sortie : son résumé devient `summary`, en attendant Enregistrer ou Supprimer."""
        self.show(self._on_finish())
        self.finished.emit()

    @Slot()
    def save(self) -> None:
        """Enregistre la sortie terminée sans faire attendre l'écran : `saving` le temps de l'écrire, puis `saved` ; ou
        `saveError` si la carte refuse, et la sortie reste là, pour réessayer ou la supprimer."""
        if self._saving:
            return
        self._set_saving(True)
        self._on_save(self._save_done)

    def _save_done(self, error: str | None) -> None:
        self._set_saving(False, error or "")
        if error is None:
            self.saved.emit()

    @Slot()
    def discard(self) -> None:
        if self._saving:
            return  # déjà en train de l'écrire
        self._set_saving(False)
        self._on_discard()

    @Slot()
    def powerOff(self) -> None:
        error = self._on_power_off()
        if error:
            self.powerOffFailed.emit(error)


class HistoryModel(QObject):
    """Expose à QML les sorties enregistrées dans `folder` (`history.rides`, de la plus récente à la plus
    ancienne) et celle qu'on a rouverte (`history.opened`) ; enregistre et supprime des sorties."""

    changed = Signal()
    openedChanged = Signal()

    def __init__(self, folder: Path = history.RIDES_DIR, parent: QObject | None = None):
        super().__init__(parent)
        self.folder = folder
        self._summaries: list[dict] = []
        self._rides: list[dict] = []
        self._opened: dict = {}
        self.reload()

    def reload(self) -> None:
        """Relit le dossier des sorties."""
        self.show(history.load(self.folder))

    def show(self, summaries: list[dict]) -> None:
        """Les sorties lues dans le dossier (voir history.load). La liste n'emporte que ce qu'elle montre (le résumé
        complet est lu à l'ouverture), avec un tracé allégé pour la vignette. Un résumé mal formé (modifié à la main)
        est ignoré."""
        self._summaries, self._rides = [], []
        for summary in summaries:
            try:
                row = {
                    "id": summary["id"],
                    "name": summary.get("name", "Sortie"),
                    "dateText": summary.get("dateText", ""),
                    "distanceKm": summary.get("distanceKm"),
                    "timerS": summary.get("timerS"),
                    "outline": _points(thinned(summary.get("outline", []), THUMBNAIL_POINTS)),
                }
            except (TypeError, ValueError):
                continue
            self._summaries.append(summary)
            self._rides.append(row)
        self.changed.emit()

    def add(self, ride: Ride, summary: dict, started_at: datetime) -> Path:
        """Enregistre une sortie terminée (fichier FIT et résumé), tout de suite. Renvoie le fichier FIT."""
        path = history.save(ride, summary, started_at, self.folder)
        self.reload()
        return path

    def _get_rides(self) -> list:
        return self._rides

    def _get_opened(self) -> dict:
        return self._opened

    rides = Property("QVariantList", _get_rides, notify=changed)
    opened = Property("QVariantMap", _get_opened, notify=openedChanged)

    @Slot(int)
    def open(self, index: int) -> None:
        """Rouvre le résumé complet d'une sortie de la liste."""
        if 0 <= index < len(self._summaries):
            try:
                opened = _drawable(self._summaries[index])
            except (TypeError, ValueError):
                return  # profil illisible : la sortie ne s'ouvre pas
            self._opened = opened
            self.openedChanged.emit()

    @Slot()
    def removeOpened(self) -> None:
        """Supprime la sortie rouverte (ses deux fichiers). Son résumé reste affiché le temps de quitter l'écran."""
        ride_id = self._opened.get("id")
        if ride_id:
            history.remove(ride_id, self.folder)
            self.reload()
