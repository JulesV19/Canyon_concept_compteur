"""Application : démarre Qt, charge l'interface QML et la relie aux données."""

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import shiboken6
from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

from . import battery, gps, history, i2c, journal
from .journal import Header, Journal
from .model import BatteryModel, GpsModel, RideModel
from .ride import Ride, State
from .route import Route
from .session import HistoryModel, SessionModel
from .settings import SettingsModel, apply_brightness
from .sim import GPS_FIX_S, SIMULATED_SUPPLY, SimulatedRider, battery_reading, demo_segments, gps_status
from .storage import Writer, describe
from .strava import StravaModel
from .summary import ride_summary
from .tiles import TileProvider

UI_DIR = Path(__file__).resolve().parent / "ui"
ROUTES_DIR = Path(__file__).resolve().parent.parent / "parcours"
MAP_FILE = Path(__file__).resolve().parent.parent / "cartes" / "ile-de-france.mbtiles"
PI_MODEL_FILE = Path("/proc/device-tree/model")  # modèle de la carte électronique, sur le Pi
TICK_MS = 1000
PAGES = {"principale": 0, "carte": 1, "altitude": 2, "cardio": 3, "tours": 4}  # pages de la sortie, dans l'ordre
SCREENS = {"reglages": "settings", "menu": "menu", "sorties": "rides",
           "segments": "segments", "batterie": "battery", "gps": "gps"}  # écrans du menu, pour les captures
SEGMENT_PAGES = ("annonce", "segment", "segment-fin")  # la côte d'essai, pour les captures
FREE_RIDE_NAME = "Sortie libre"
# Sur le Pi, sans bureau : l'interface va droit à l'écran (linuxfb, par DRM), sans curseur, et c'est le processeur qui
# dessine : le pilote du GPU des Pi 0 à 3 (vc4) corrompt la mémoire avec cette appli (voir le README)
PI_QT_ENV = {
    "QT_QPA_PLATFORM": "linuxfb",
    "QT_QPA_FB_DRM": "1",
    "QT_QPA_FB_HIDECURSOR": "1",
    "QT_QUICK_BACKEND": "software",
}
# Éteindre : l'arrêt du système, sans jamais attendre de mot de passe (le droit est donné par tools/pi/installer.sh)
POWER_OFF = ["systemctl", "--no-ask-password", "poweroff"]
# Sortie reprise : la coupure compte comme une pause, de 12 h au plus (au-delà, l'horloge du système est douteuse)
MAX_RESUME_GAP_S = 12 * 3600


def on_raspberry_pi(model_file: Path = PI_MODEL_FILE) -> bool:
    """Vrai sur le Pi, faux sur le Mac."""
    try:
        return model_file.read_text(errors="ignore").startswith("Raspberry Pi")
    except OSError:
        return False


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


class Relay(QObject):
    """Fait passer des fonctions d'un autre fil au fil de l'interface (résultats du fil d'écriture)."""

    _call = Signal(object)

    def __init__(self):
        super().__init__()
        self._call.connect(self._run)

    @Slot(object)
    def _run(self, function: Callable[[], None]) -> None:
        function()

    def post(self, function: Callable[[], None]) -> None:
        self._call.emit(function)


class Compteur:
    def __init__(self, argv: list[str], software_rendering: bool = False, accel: float = 1.0,
                 intro: bool = True, autoplay: bool = True, rides_dir: Path = history.RIDES_DIR,
                 recovery: bool = False, strava_dir: Path | None = None, strava_sync: bool = False):
        """`rides_dir` : dossier des sorties. `recovery` : la sortie en cours est gardée dans un fichier de reprise, et
        reprend au démarrage après une coupure. C'est le cas de l'appli, pas des captures ni des mesures.
        `strava_dir` : dossier des jetons et des segments Strava (sans lui, pas de segments en favori) ; `strava_sync` :
        synchro au démarrage et records battus gardés, pour l'appli seule."""
        if on_raspberry_pi():
            for name, value in PI_QT_ENV.items():
                os.environ.setdefault(name, value)  # une capture hors écran garde son réglage
        if software_rendering:
            QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
        self.app = QGuiApplication(argv)
        for path in sorted((UI_DIR / "fonts").glob("*.ttf")):
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
            raise SystemExit(f"Aucun parcours GPX utilisable dans {ROUTES_DIR} : le cycliste simulé en a besoin")
        # En attendant les vrais capteurs, un cycliste simulé : immobile sur l'accueil, il roule une fois parti
        self.rider = SimulatedRider(self.routes[0])
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
        # Segments Strava en favori : lus dans leur cache, synchronisés sur leur propre fil (voir strava.py)
        self.strava = StravaModel(strava_dir, self.relay.post, parent=self.engine, writer=self.writer)
        self.model = RideModel(self.new_ride(), None, self.tiles.origin, parent=self.engine)
        # Batterie : sur le Pi, la jauge, lue par son propre fil (voir battery.py) ; ailleurs, une batterie simulée
        self.gauge = battery.Monitor().start() if on_raspberry_pi() else None
        self.gauge_started = time.monotonic()
        self.battery = BatteryModel("MAX17048" if self.gauge is not None else "Simulation", parent=self.engine)
        # GPS : sur le Pi, le vrai, lu par son propre fil, pour son écran d'état (la sortie suit encore le cycliste
        # simulé) ; ailleurs, un GPS simulé
        self.gps = gps.Receiver(find=lambda: i2c.find(gps.ADDRESS)).start() if on_raspberry_pi() else None
        self.gps_model = GpsModel("PA1010D" if self.gps is not None else "Simulation", parent=self.engine)
        self.last_sample = None  # dernière mesure du cycliste simulé : la position du GPS simulé
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

    def new_ride(self) -> Ride:
        """Sortie au repos, avec les réglages du moment (auto-pause, FC max)."""
        settings = self.settings.current
        return Ride(auto_pause=settings.auto_pause, max_hr=settings.max_hr)

    def follow_segments(self, route: Route) -> None:
        """Segments suivis pendant la sortie : les favoris Strava, et la côte d'essai tant que le cycliste est simulé."""
        starred = self.strava.starred()
        self.model.segments = starred + demo_segments(route, starred)
        self.model.kom_label = self.strava.kom_label

    def start_ride(self, route: Route | None) -> None:
        """Départ sur ce parcours, ou en sortie libre (le cycliste simulé roule alors sur le premier)."""
        self.rider = SimulatedRider(route or self.routes[0])
        ride = self.new_ride()
        self.started_at = datetime.now().astimezone()
        self.route_name = route.name if route else FREE_RIDE_NAME
        if self.journal is not None:
            route_file = route.path.name if route is not None and route.path is not None else None
            self.journal.start(Header(self.started_at, route_file, self.route_name, ride.auto_pause, ride.max_hr), ride)
        self.follow_segments(self.rider.route)
        self.model.reset(ride, route)
        self.model.update(self.rider.sample(self.t, riding=False))  # des valeurs tout de suite, sans « -- »
        self.model.startPause()

    def finish_ride(self) -> dict:
        """Fin de la sortie : elle est gardée jusqu'au choix Enregistrer ou Supprimer, et le compteur
        revient au repos, sans parcours. Renvoie son résumé."""
        ride = self.model.ride
        summary = ride_summary(ride, self.route_name, self.started_at)
        self.finished = (ride, summary, self.started_at)
        if self.journal is not None:
            self.journal.finish(ride)
        self.model.reset(self.new_ride(), None)
        self.model.update(self.rider.sample(self.t, riding=False))
        self.model.refresh()
        return summary

    def save_ride(self, done: Callable[[str | None], None]) -> None:
        """Enregistre la sortie terminée (fichier FIT et résumé, dans sorties/) sur le fil d'écriture : l'écran ne se
        fige pas, même pour une longue sortie. Une fois les deux fichiers forcés sur la carte, le fichier de reprise
        s'efface. Puis `done(None)`, ou `done(message)` si la carte refuse : la sortie reste alors là, pour réessayer
        ou la supprimer."""
        if self.finished is None:
            done(None)
            return
        ride, summary, started_at = self.finished
        folder, recovery = self.history.folder, self.journal

        def task():
            path = history.save(ride, summary, started_at, folder)
            if recovery is not None:
                try:
                    recovery.delete()
                except OSError as error:  # la sortie est à l'abri : au prochain démarrage, on la verra enregistrée
                    print(f"Fichier de reprise pas effacé : {error}", file=sys.stderr)
            return path, history.load(folder)

        def finished(result, error):
            if error is not None:
                print(f"Sortie non enregistrée : {error!r}", file=sys.stderr, flush=True)
                done(describe(error))
                return
            path, summaries = result
            self.finished = None
            print(f"Sortie enregistrée : {path}", flush=True)
            try:
                self.history.show(summaries)
            finally:
                done(None)  # la sortie est à l'abri : l'écran la quitte, même si Mes sorties n'a pas pu se relire

        self.writer.submit(task, finished)

    def discard_ride(self) -> None:
        """Supprime la sortie terminée : son fichier de reprise, et le fichier FIT qu'un enregistrement raté aurait laissé
        sans son résumé."""
        if self.finished is None:
            return
        started_at, folder = self.finished[2], self.history.folder
        self.finished = None
        self.writer.submit(lambda: history.remove_orphans(started_at, folder))
        if self.journal is not None:
            self.journal.discard()

    def recover(self) -> str:
        """Au démarrage, la sortie laissée dans le fichier de reprise : terminée, son résumé revient ; en cours, elle
        reprend en pause, là où elle en était. Renvoie l'écran où démarrer."""
        path = self.journal.path
        try:
            found = journal.load(path)
        except (OSError, ValueError) as error:
            # Rien de lisible à reprendre : le fichier est mis de côté, jamais effacé
            aside = path.with_name(f"reprise-illisible-{datetime.now():%Y-%m-%d_%H-%M-%S}.jsonl")
            print(f"Fichier de reprise illisible ({error}) : gardé sous {aside.name}", file=sys.stderr)
            try:
                path.replace(aside)
            except OSError:
                pass
            return "home"
        if found is None:
            return "home"
        header, ride = found.header, found.ride
        # Une sortie terminée peut avoir été enregistrée juste avant la coupure : reconnue à son contenu
        summary = ride_summary(ride, header.route_name, header.started_at) if found.finished else None
        if ride.state is State.IDLE or (summary is not None and history.find_saved(summary, self.history.folder)):
            self.journal.discard()  # rien de roulé, ou déjà enregistrée
            return "home"
        self.journal.resume(found)
        self.started_at, self.route_name = header.started_at, header.route_name
        # L'horloge des mesures repart d'où elle s'était arrêtée, plus le temps passé depuis : la sortie garde des
        # heures justes, et la coupure compte comme une pause, dans le temps total comme dans le fichier FIT
        gap = min(max(time.time() - found.written_at, 0.0), MAX_RESUME_GAP_S)
        self.t = self.boot_t = ride.last_t + round(gap)
        print(f"Sortie reprise : {header.route_name}, {ride.total.distance_m / 1000:.1f} km", flush=True)
        if summary is not None:
            self.finished = (ride, summary, header.started_at)
            self.session.show(summary)
            return "summary"
        route = next((r for r in self.routes if r.path is not None and r.path.name == header.route_file), None)
        self.follow_segments(route or self.routes[0])
        self.model.resume(ride, route)
        if ride.state is State.RUNNING:
            self.model.startPause()  # elle attend Start pour repartir
        self.rider = self._rider_after(ride, route)
        self.resumed_at = f"{datetime.fromtimestamp(found.written_at):%H:%M}"  # pour le bandeau « Sortie reprise »
        return "ride"

    def _rider_after(self, ride: Ride, route: Route | None) -> SimulatedRider:
        """Le cycliste simulé, reparti de la dernière position de la sortie reprise."""
        rider = SimulatedRider(route or self.routes[0])
        last = ride.current
        if route is not None and self.model.position is not None:
            rider.distance_m = self.model.position.along_m
        elif last is not None and last.lat is not None and last.lon is not None:
            rider.route.rewind()
            rider.distance_m = rider.route.locate(last.lat, last.lon).along_m
            rider.route.rewind()
        return rider

    def power_off(self) -> str | None:
        """Éteindre : sur le Pi, le système s'arrête proprement (couper le courant sans arrêt peut abîmer la carte SD),
        puis l'appli se ferme. S'il refuse, l'appli reste ouverte, et on renvoie pourquoi en quelques mots. Sur le Mac,
        l'appli se ferme."""
        if on_raspberry_pi():
            try:
                result = subprocess.run(POWER_OFF, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                        timeout=30)
            except (OSError, subprocess.TimeoutExpired) as error:
                print(f"Arrêt impossible : {error}", file=sys.stderr)
                return "arrêt impossible"
            if result.returncode != 0:
                print(f"Arrêt refusé ({result.returncode}) : {result.stderr.strip()}", file=sys.stderr)
                return "le système refuse l'arrêt"
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

    def device_status(self) -> dict:
        """État du boîtier (GPS, ceinture, batterie) : simulé, sauf la batterie quand la jauge répond."""
        status = self.rider.device_status(self.t - self.boot_t)
        if self.battery.percent is not None:
            status["batteryPct"] = round(self.battery.percent)
        status["batteryCharging"] = self.battery.state == "charge"
        return status

    def refresh(self) -> None:
        """Met l'écran à jour : la sortie, l'état du boîtier, la batterie et le GPS."""
        self.battery.refresh()
        self.gps_model.refresh(self.gps.status() if self.gps is not None
                               else gps_status(self.t - self.boot_t, self.last_sample))
        self.model.refresh(self.device_status())

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

    def screenshot(self, path: str, page: str = "principale", minutes: float = 51) -> None:
        if page in SEGMENT_PAGES:
            self._ride_to_segment(page)
        elif page in PAGES or page == "resume":
            # Sortie de démo sur le premier parcours, avec un tour à mi-chemin.
            # 51 min par défaut : ni à l'arrêt, ni sur le plat.
            self.session.start(0)
            ride = self.model.ride
            steps = round(minutes * 60)
            for i in range(steps):
                if i == steps // 2:
                    ride.lap()
                # Les dernières secondes passent par l'interface, comme en vrai : la carte a le temps de s'orienter
                if i >= steps - 10:
                    self.tick()
                else:
                    self.step()
            if page == "resume":
                # En pause, puis Terminer : le résumé de la sortie
                self.model.startPause()
                self.session.finish()
                self.window.setProperty("screen", "summary")
            else:
                self.window.setProperty("screen", "ride")
                self.window.setProperty("page", PAGES[page])
        else:
            # Accueil ou écrans du menu, une fois le GPS prêt ; « libre » : l'accueil sur la carte Sortie libre ;
            # « batterie » : après `minutes` de mise en route, pour voir la batterie descendre
            ready_s = minutes * 60 if page == "batterie" else GPS_FIX_S
            while self.t - self.boot_t < ready_s:
                self.step()
            if page == "libre":
                self.window.setProperty("homeIndex", len(self.routes))
            elif page in SCREENS:
                self.window.setProperty("screen", SCREENS[page])
        self.refresh()

        def grab():
            self.window.grabWindow().save(path)
            self.app.quit()

        # Laisse le temps au changement d'écran et au chargement des tuiles
        QTimer.singleShot(1500, grab)
        self.app.exec()

    def _ride_to_segment(self, page: str) -> None:
        """Sortie de démo jusqu'à la côte d'essai : son annonce, le passage aux deux tiers, ou son arrivée."""
        self.session.start(0)
        self.window.setProperty("screen", "ride")
        tracker = self.model.tracker
        reached = {
            "annonce": lambda: tracker.approach is not None and tracker.approach.distance_m < 200,
            "segment": lambda: any(effort.along_m > 0.65 * effort.segment.length_m for effort in tracker.active),
            "segment-fin": lambda: bool(tracker.results),
        }[page]
        for _ in range(4 * 3600):
            if reached():
                break
            self.step()
        self.tick()

    def record_intro(self, path: str, frames_dir: str | None = None, fps: int = 25, hold_s: float = 1.5) -> None:
        """Enregistre l'intro en GIF : elle avance image par image, puis ffmpeg assemble les captures."""
        frames = Path(frames_dir) if frames_dir else Path(tempfile.mkdtemp(prefix="intro-"))
        frames.mkdir(parents=True, exist_ok=True)

        def record():
            try:
                duration = self.window.property("introDuration")
                count = round(duration / 1000 * fps) + round(hold_s * fps)
                for i in range(count + 1):
                    self.window.setProperty("introTime", min(duration, i * 1000 / fps))
                    self.window.grabWindow().save(str(frames / f"{i:04d}.png"))
                palette = "split[a][b];[a]palettegen=stats_mode=full[p];[b][p]paletteuse=dither=sierra2_4a"
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
                                "-i", str(frames / "%04d.png"), "-vf", f"scale=480:-1:flags=lanczos,{palette}",
                                "-loop", "0", path], check=True)
            finally:
                if not frames_dir:
                    shutil.rmtree(frames, ignore_errors=True)
                self.app.quit()

        QTimer.singleShot(500, record)
        self.app.exec()
