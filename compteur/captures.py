"""Captures d'écran (--screenshot) et GIF de l'intro (--intro-gif).

`Captures` est une partie de `Compteur` (app.py)."""

import shutil
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QTimer

from .sim import GPS_FIX_S

PAGES = {"principale": 0, "carte": 1, "altitude": 2, "cardio": 3, "tours": 4, "carplay-sortie": 5}  # pages de la sortie, dans l'ordre
SCREENS = {"reglages": "settings", "menu": "menu", "sorties": "rides",
           "segments": "segments", "batterie": "battery", "gps": "gps", "carplay": "carplay"}  # écrans du menu, pour les captures
# Applis de la page CarPlay, et conversation ouverte, pour les captures
CARPLAY_APPS = {"carplay-musique": ("music", ""), "carplay-telephone": ("phone", ""),
                "carplay-messages": ("messages", ""), "carplay-whatsapp": ("whatsapp", ""),
                "carplay-conversation": ("messages", "Léa"), "carplay-groupe": ("whatsapp", "Sortie du dimanche")}
PHONE_BANNERS = ("carplay-appel", "carplay-message")  # bandeaux de l'iPhone sur la page principale, pour les captures
SEGMENT_PAGES = ("annonce", "segment", "segment-fin")  # la côte d'essai, pour les captures


class Captures:
    def screenshot(self, path: str, page: str = "principale", minutes: float = 51) -> None:
        # Les pages d'une sortie ont besoin d'une sortie qui avance : sur le Pi, le vrai GPS est posé sur la table et
        # ne bouge pas, donc on prend le cycliste simulé. La page GPS, elle, garde le vrai GPS : c'est son sujet.
        banner = page if page in PHONE_BANNERS else None
        if banner:
            page = "principale"
        if page in SEGMENT_PAGES or page in PAGES or page == "resume":
            self.gps = None
            self.rider = self.make_rider()
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
            elif page in CARPLAY_APPS:
                self.window.setProperty("screen", "carplay")
                self.window.findChild(QObject, "menuCarPlay").setProperty("app", CARPLAY_APPS[page][0])
                self.window.findChild(QObject, "menuCarPlay").setProperty("conversation", CARPLAY_APPS[page][1])
        if banner == "carplay-appel" and self.phone_sim:
            self.phone_sim.ring("Léa Martin")
        elif banner == "carplay-message" and self.phone_sim:
            self.phone_sim.message("whatsapp", "Sortie du dimanche", "On t'attend au rond-point, on repart dans 5 min")
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
