"""Application : démarre Qt, charge l'interface QML et la relie aux données.

Le déroulé d'une sortie est dans ride_flow.py, les captures dans captures.py, ce qui est propre au Pi dans pi.py."""

import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import shiboken6
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

from . import battery, gps, history, i2c, iphone, journal, pi
from .captures import Captures
from .journal import Journal
from .model import BatteryModel, GpsModel, PhoneModel, RideModel
from .relay import Relay
from .ride import Ride, State
from .ride_flow import FREE_RIDE_NAME, RideFlow
from .route import Route
from .session import HistoryModel, SessionModel
from .settings import SettingsModel, apply_brightness
from .sim import SIMULATED_SUPPLY, SimulatedPhone, SimulatedRider, battery_reading, gps_status
from .storage import Writer
from .strava import StravaModel
from .tiles import TileProvider

UI_DIR = Path(__file__).resolve().parent / "ui"
APPLE_DIR = UI_DIR / "carplay" / "apple"  # SF Pro et icônes d'Apple, hors dépôt
ROUTES_DIR = Path(__file__).resolve().parent.parent / "parcours"
MAP_FILE = Path(__file__).resolve().parent.parent / "cartes" / "ile-de-france.mbtiles"
TICK_MS = 1000


def load_routes(folder: Path) -> list[Route]:
    """Les parcours GPX du dossier, par ordre alphabétique. Un fichier inutilisable est ignoré et signalé : il ne doit
    pas empêcher l'appli de démarrer."""
    routes = []
    for path in sorted(folder.glob("*.gpx")):
        try:
            routes.append(Route.load(path))
        except (OSError, ValueError) as error:
            print(f"Parcours ignoré ({path.name}) : {error}", file=sys.stderr)
    return routes


class Compteur(RideFlow, Captures):
    def __init__(self, argv: list[str], software_rendering: bool = False, accel: float = 1.0,
                 intro: bool = True, autoplay: bool = True, rides_dir: Path = history.RIDES_DIR,
                 recovery: bool = False, strava_dir: Path | None = None, strava_sync: bool = False):
        """`rides_dir` : dossier des sorties. `recovery` : la sortie en cours est gardée dans un fichier de reprise, et
        reprend au démarrage après une coupure. C'est le cas de l'appli, pas des captures ni des mesures.
        `strava_dir` : dossier des jetons et des segments Strava (sans lui, pas de segments en favori) ; `strava_sync` :
        synchro au démarrage et records battus gardés, pour l'appli seule."""
        if pi.on_raspberry_pi():
            for name, value in pi.PI_QT_ENV.items():
                os.environ.setdefault(name, value)  # une capture hors écran garde son réglage
        if software_rendering:
            QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
        self.app = QGuiApplication(argv)
        # Barlow, et SF Pro pour la page CarPlay quand ses fichiers sont là (hors dépôt : tools/carplay/ressources.py)
        for path in sorted((UI_DIR / "fonts").glob("*.ttf")) + sorted(APPLE_DIR.glob("*.ttf")):
            QFontDatabase.addApplicationFont(str(path))
        self.app.setFont(QFont("Barlow"))
        # systemctl stop, arrêt du système : l'appli se ferme proprement, et la sortie en cours reste à reprendre. Par la
        # boucle de l'appli : reçu pendant le démarrage (reprise d'une longue sortie), l'arrêt attend qu'elle tourne.
        signal.signal(signal.SIGTERM, lambda *_: QTimer.singleShot(0, self.app.quit))

        self.engine = QQmlApplicationEngine()
        self.engine.quit.connect(self.app.quit)
        # Carte hors ligne (voir tools/carte) : l'interface demande ses tuiles à « image://tiles »
        self.tiles = TileProvider(MAP_FILE)
        self.engine.addImageProvider("tiles", self.tiles)

        # Réglages (FC max, auto-pause, luminosité), gardés d'une mise en route à l'autre.
        # Les modèles appartiennent au moteur QML : ils sont détruits après l'interface qui les utilise.
        self.settings = SettingsModel(parent=self.engine)
        self.settings.changed.connect(lambda: apply_brightness(self.settings.current.brightness))
        apply_brightness(self.settings.current.brightness)

        # Parcours proposés à l'accueil : les GPX du dossier parcours/, par ordre alphabétique
        self.routes = load_routes(ROUTES_DIR)
        if not self.routes:
            raise SystemExit(f"Aucun parcours GPX utilisable dans {ROUTES_DIR} : l'accueil en a besoin")
        # GPS : sur le Pi, le vrai, lu par son propre fil (voir compteur/gps/) ; ailleurs, un GPS simulé
        self.gps = gps.Receiver(find=lambda: i2c.find(gps.ADDRESS)).start() if pi.on_raspberry_pi() else None
        self.clock_check = gps.ClockCheck()
        self.clock_denied = False  # le système refuse de changer l'heure : on ne réessaie plus
        self.rider = self.make_rider()
        self.t = 0.0
        self.boot_t = 0.0  # heure des mesures à la mise en route : l'état du boîtier simulé en part
        self.started_at = datetime.now().astimezone()  # date et heure du départ, pour l'enregistrement
        self.route_name = FREE_RIDE_NAME
        self.finished = None  # sortie terminée, en attendant Enregistrer ou Supprimer
        self.resumed_at = ""  # sortie reprise en cours après une coupure : heure de sa dernière écriture
        # Tout ce qui touche aux fichiers des sorties passe par le fil d'écriture, dans l'ordre (voir storage.py)
        self.relay = Relay()
        self.writer = Writer(self.relay.post)
        self.journal = None
        if recovery:
            history.clean(rides_dir)  # fichiers temporaires d'un enregistrement coupé
            self.journal = Journal(rides_dir / journal.FILE_NAME, self.writer)
        self.history = HistoryModel(rides_dir, parent=self.engine)  # sorties enregistrées, dans sorties/
        # Segments Strava en favori : lus dans leur cache, synchronisés sur leur propre fil (voir compteur/strava/)
        self.strava = StravaModel(strava_dir, self.relay.post, parent=self.engine, writer=self.writer)
        self.model = RideModel(self.new_ride(), None, self.tiles.origin, parent=self.engine)
        # Batterie : sur le Pi, la jauge, lue par son propre fil (voir battery.py) ; ailleurs, une batterie simulée
        self.gauge = battery.Monitor().start() if pi.on_raspberry_pi() else None
        self.gauge_started = time.monotonic()
        self.battery = BatteryModel("MAX17048" if self.gauge is not None else "Simulation", parent=self.engine)
        self.gps_model = GpsModel("PA1010D" if self.gps is not None else "Simulation", parent=self.engine)
        # iPhone : sur le Pi, la vraie liaison Bluetooth (voir compteur/iphone/), si dbus-fast est là ; ailleurs, un iPhone simulé
        self.phone_state = iphone.PhoneState()
        self.phone_sim = None
        self.phone_link = None
        if pi.on_raspberry_pi():
            try:
                import dbus_fast  # noqa: F401
            except ImportError:
                print("Pas de dbus-fast : pas d'iPhone", file=sys.stderr)
            else:
                self.phone_link = iphone.Link(self.phone_state, log=lambda text: print(f"iPhone : {text}", flush=True))
                self.phone_link.start()
        else:
            self.phone_sim = self.phone_link = SimulatedPhone(self.phone_state)
        self.phone = PhoneModel(self.phone_state, self.phone_link, parent=self.engine)
        self.last_sample = None  # dernière mesure : la position du GPS simulé, quand il n'y a pas de vrai GPS
        if strava_sync:  # comme la synchro : l'appli seule, jamais une capture
            self.model.record_beaten = self.strava.keep_record
        self.session = SessionModel(self.routes, self.start_ride, self.finish_ride, self.save_ride,
                                    self.discard_ride, self.power_off, parent=self.engine)
        # Après une coupure, on retrouve la sortie là où elle en était : son résumé, ou la sortie en pause
        screen = self.recover() if self.journal is not None else "home"
        self.tick()

        # accel > 1 : la simulation avance plus vite (ex. 10 = 10 s simulées par seconde)
        tick_ms = round(TICK_MS / accel)
        self.timer = QTimer(self.engine)
        self.timer.timeout.connect(self.tick)
        self.timer.start(tick_ms)

        # La carte glisse d'une position à l'autre en un pas de simulation (sans animation en capture).
        # L'intro se joue au démarrage, sauf sur une sortie reprise ; sans autoplay, elle est pilotée image par image
        # (record_intro).
        self.engine.setInitialProperties({
            "ride": self.model,
            "session": self.session,
            "history": self.history,
            "settings": self.settings,
            "strava": self.strava,
            "battery": self.battery,
            "gps": self.gps_model,
            "phone": self.phone,
            "tickMs": 0 if software_rendering else tick_ms,
            "introEnabled": intro and screen == "home",
            "introAutoplay": autoplay,
            "screen": screen,
            "resumedAt": self.resumed_at,
        })
        self.engine.load(QUrl.fromLocalFile(str(UI_DIR / "Main.qml")))
        if not self.engine.rootObjects():
            raise SystemExit("Impossible de charger l'interface (voir les erreurs QML ci-dessus)")
        self.window = self.engine.rootObjects()[0]
        if strava_sync:
            self.strava.sync_at_start()

    def make_rider(self, route: Route | None = None) -> SimulatedRider | gps.GpsRider:
        """D'où viennent les mesures de la sortie : le vrai GPS quand il est branché (sans ceinture cardio pour
        l'instant), sinon un cycliste simulé qui suit ce parcours, immobile sur l'accueil."""
        return gps.GpsRider(self.gps) if self.gps is not None else SimulatedRider(route or self.routes[0])

    def new_ride(self) -> Ride:
        """Sortie au repos, avec les réglages du moment (auto-pause, FC max)."""
        settings = self.settings.current
        return Ride(auto_pause=settings.auto_pause, max_hr=settings.max_hr)

    def power_off(self) -> str | None:
        """Éteindre : sur le Pi, le système s'arrête proprement (couper le courant sans arrêt peut abîmer la carte SD),
        puis l'appli se ferme. S'il refuse, l'appli reste ouverte, et on renvoie pourquoi en quelques mots. Sur le Mac,
        l'appli se ferme."""
        if pi.on_raspberry_pi():
            error = pi.shutdown()
            if error is not None:
                return error
        self.app.quit()
        return None

    def step(self) -> None:
        """Avance d'une seconde : nouvelle mesure, mise à jour des calculs."""
        self.t += 1.0
        riding = self.model.ride.state is State.RUNNING
        self.last_sample = self.rider.sample(self.t, riding)
        self.model.update(self.last_sample)
        if self.gauge is not None:
            reading, supply = self.gauge.latest()
            self.battery.update(time.monotonic() - self.gauge_started, reading, supply)
        else:
            self.battery.update(self.t - self.boot_t, battery_reading(self.t - self.boot_t), SIMULATED_SUPPLY)
        if self.phone_sim is not None:
            self.phone_sim.step()
        self.sync_clock()

    def sync_clock(self) -> None:
        """Le Pi n'a pas d'horloge sauvegardée : sans réseau, il démarre à l'heure de son dernier arrêt. Dès que le GPS
        a une position, l'horloge du système prend son heure (droit CAP_SYS_TIME, donné par le service : voir
        tools/pi/installer.sh). Une sortie déjà partie décale son heure de départ d'autant ; son fichier de reprise
        garde l'ancienne, qui ne sert qu'après une coupure."""
        if self.gps is None or self.clock_denied:
            return
        offset = self.clock_check.offset(self.gps.fix(), self.gps.clock(), datetime.now(timezone.utc))
        if offset is None or abs(offset) < gps.CLOCK_TOLERANCE_S:
            return
        try:
            time.clock_settime(time.CLOCK_REALTIME, time.time() + offset)
        except OSError as error:
            self.clock_denied = True
            print(f"Heure du GPS : l'horloge du système reste fausse de {offset:+.0f} s ({error})", file=sys.stderr)
            return
        print(f"Horloge mise à l'heure du GPS : {offset:+.0f} s", flush=True)
        if self.model.ride.state is not State.IDLE:
            self.started_at += timedelta(seconds=offset)

    def device_status(self) -> dict:
        """État du boîtier (GPS, ceinture, batterie) : le GPS et la ceinture viennent de la source des mesures
        (vrai GPS ou cycliste simulé), la batterie de la jauge quand elle répond."""
        status = self.rider.device_status(self.t - self.boot_t)
        if self.battery.percent is not None:
            status["batteryPct"] = round(self.battery.percent)
        status["batteryCharging"] = self.battery.state == "charge"
        return status

    def refresh(self) -> None:
        """Met l'écran à jour : la sortie, l'état du boîtier, la batterie, le GPS et l'iPhone."""
        self.battery.refresh()
        self.gps_model.refresh(self.gps.status() if self.gps is not None
                               else gps_status(self.t - self.boot_t, self.last_sample))
        self.model.refresh(self.device_status())
        self.phone.refresh()

    def tick(self) -> None:
        self.step()
        self.refresh()

    def close(self) -> None:
        """Termine les écritures, puis détruit l'interface avant l'application Qt. Laissé à Python en quittant, l'ordre
        est aléatoire, et un moteur QML détruit après l'application peut faire planter l'appli à la fermeture (mémoire
        corrompue)."""
        if self.engine is None:
            return
        self.timer.stop()
        if self.gauge is not None:
            self.gauge.stop()
        if self.gps is not None:
            self.gps.stop()
        if self.journal is not None:
            self.journal.close()  # la sortie en cours reprendra au prochain démarrage
        if not self.writer.close():
            print("Écritures pas terminées à la fermeture", file=sys.stderr)
        self.strava.close()
        shiboken6.delete(self.engine)  # avec l'interface, les modèles et le fournisseur de tuiles
        self.engine = None

    def run(self) -> int:
        code = self.app.exec()
        self.close()
        return code
