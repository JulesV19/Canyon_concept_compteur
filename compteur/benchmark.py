"""Mesure de la fluidité et de la charge, pour le Pi : python -m compteur --mesure

Un scénario d'environ 3 minutes passe par l'intro, l'accueil, chaque page d'une sortie sur parcours, la pause, le
résumé, puis la carte d'une sortie libre. Pour chaque phase : images affichées par seconde, processeur (fil de
l'interface, fil de rendu), durée de la mise à jour de chaque seconde, mémoire et, sur le Pi, température.
Rien n'est écrit ni effacé dans sorties/ : la mesure travaille dans un dossier temporaire (voir __main__).
"""

import json
import os
import platform
import resource
import shutil
import statistics
import subprocess
import time
import unicodedata
from pathlib import Path

from PySide6.QtCore import QMetaObject, QObject, QTimer, Slot, qVersion

from .app import PAGES, PI_MODEL_FILE

SETTLE_S = 3  # après chaque changement d'écran (transitions, tuiles) : hors mesure
PHASE_S = 15  # durée mesurée de chaque phase


def thread_cpu() -> dict[int, tuple[str, float]] | None:
    """Temps processeur de chaque fil du processus, en secondes, par identifiant (Linux seulement)."""
    tasks = Path("/proc/self/task")
    if not tasks.is_dir():
        return None
    ticks = os.sysconf("SC_CLK_TCK")
    threads = {}
    for task in tasks.iterdir():
        try:
            name = (task / "comm").read_text().strip()
            fields = (task / "stat").read_text().rsplit(")", 1)[1].split()
            threads[int(task.name)] = (name, (int(fields[11]) + int(fields[12])) / ticks)  # utime + stime
        except (OSError, ValueError, IndexError):
            continue  # fil terminé entre-temps
    return threads


def memory_mb() -> float:
    """Mémoire occupée par le processus, en Mo."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())], capture_output=True, text=True).stdout
    return int(out.strip() or 0) / 1024


def temperature_c() -> float | None:
    """Température du processeur (Pi)."""
    try:
        return int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
    except (OSError, ValueError):
        return None


def throttled() -> str | None:
    """Sous-tension ou bridage du Pi depuis le démarrage (0x0 : aucun)."""
    if not shutil.which("vcgencmd"):
        return None
    out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True).stdout
    return out.strip().split("=", 1)[-1] or None


def machine() -> str:
    try:
        return PI_MODEL_FILE.read_text(errors="ignore").strip("\x00\n ")
    except OSError:
        return f"{platform.system()} {platform.machine()}"


def phase_result(name: str, before: dict, after: dict, update_ms: list[float], main_tid: int) -> dict:
    """Bilan d'une phase entre deux relevés. Processeur en % d'un cœur."""
    wall = after["time"] - before["time"]
    updates = update_ms[before["updates"]:after["updates"]]
    result = {
        "phase": name,
        "fps": round((after["frames"] - before["frames"]) / wall, 1),
        "cpu": round(100 * (after["cpu"] - before["cpu"]) / wall, 1),
        "cpuInterface": None,
        "cpuRender": None,
        "updateMsMean": round(statistics.fmean(updates), 1) if updates else None,
        "updateMsMax": round(max(updates), 1) if updates else None,
        "memoryMb": round(after["memoryMb"]),
        "temperatureC": after["temperatureC"],
    }
    if before["threads"] is not None and after["threads"] is not None:
        interface = render = 0.0
        for tid, (thread, seconds) in after["threads"].items():
            spent = seconds - before["threads"].get(tid, (thread, 0.0))[1]
            if tid == main_tid:
                interface += spent
            elif thread.startswith(("QSGRenderThread", "QSGSoftwareRend")):  # rendu par le GPU ou le processeur
                render += spent
        result["cpuInterface"] = round(100 * interface / wall, 1)
        result["cpuRender"] = round(100 * render / wall, 1)
    return result


HEADER = (f"{'':<22}{'images/s':>9}{'CPU':>8}{'interface':>11}{'rendu':>8}{'mise à jour':>15}{'mémoire':>10}"
          f"{'temp.':>8}")


def format_line(r: dict) -> str:
    def percent(value):
        return "—" if value is None else f"{value:.0f} %"

    update = "—" if r["updateMsMean"] is None else f"{r['updateMsMean']:.0f} / {r['updateMsMax']:.0f} ms"
    temperature = "" if r["temperatureC"] is None else f"{r['temperatureC']:.0f} °C"
    return (f"{r['phase']:<22}{r['fps']:>9.1f}{percent(r['cpu']):>8}{percent(r['cpuInterface']):>11}"
            f"{percent(r['cpuRender']):>8}{update:>15}{r['memoryMb']:>7} Mo{temperature:>8}")


class Benchmark(QObject):
    """Déroule le scénario dans la vraie boucle de l'appli, puis affiche le bilan (et l'enregistre en JSON)."""

    def __init__(self, compteur, json_path: str | None = None, minutes: float = 51, started: float | None = None,
                 phase_s: float = PHASE_S, settle_s: float = SETTLE_S, images_dir: str | None = None):
        super().__init__()
        self.c = compteur
        self.json_path = json_path
        self.images_dir = Path(images_dir) if images_dir else None  # une capture à la fin de chaque phase
        self.minutes = minutes  # sortie simulée avant de mesurer les pages de sortie
        self.started = time.perf_counter() if started is None else started
        self.frames = 0
        self.startup_s = None
        self.update_ms: list[float] = []  # durée de chaque mise à jour (une par seconde)
        self.results: list[dict] = []
        self._before = None

        def page(name):
            return lambda: self.c.window.setProperty("page", PAGES[name])

        intro_s = self.c.window.property("introDuration") / 1000 if self.c.window.property("introRunning") else 0
        self.plan = [(name, setup, duration, settle) for name, setup, duration, settle in [
            ("Intro", None, intro_s, 0),
            ("Accueil", None, phase_s, settle_s),
            ("Principale", lambda: self._ride(0, "principale"), phase_s, settle_s),
            ("Carte", page("carte"), phase_s, settle_s),
            ("Altitude", page("altitude"), phase_s, settle_s),
            ("Cardio", page("cardio"), phase_s, settle_s),
            ("Tours", page("tours"), phase_s, settle_s),
            ("Pause", self._pause, phase_s, settle_s),
            ("Résumé", self._summary, phase_s, settle_s),
            ("Carte, sortie libre", self._free_ride, phase_s, settle_s),
        ] if duration > 0]

    def run(self) -> dict:
        # Les mises à jour de chaque seconde passent par ici pour être chronométrées
        self.c.timer.stop()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update)
        self.timer.start(self.c.timer.interval())
        self.c.window.frameSwapped.connect(self._frame)
        QTimer.singleShot(120_000, self._check_started)
        self.c.app.exec()

        renderer = self.c.window.rendererInterface()
        report = {
            "machine": machine(),
            "cores": os.cpu_count(),
            "qt": qVersion(),
            "graphicsApi": renderer.graphicsApi().name if renderer else None,
            "startupS": None if self.startup_s is None else round(self.startup_s, 1),
            "throttled": throttled(),
            "phases": self.results,
        }
        print()
        print(f"{report['machine']} ({report['cores']} cœurs), Qt {report['qt']}, rendu {report['graphicsApi']}")
        print(f"Première image {report['startupS']} s après le lancement")
        print(HEADER)
        for result in self.results:
            print(format_line(result))
        print("CPU en % d'un cœur. Mise à jour : calcul et affichage des valeurs de chaque seconde, moyenne / max.")
        if report["throttled"] is not None:
            print(f"Sous-tension ou bridage depuis le démarrage : {report['throttled']} (0x0 : aucun)")
        if self.json_path:
            Path(self.json_path).write_text(json.dumps(report, ensure_ascii=False, indent=2))
        return report

    @Slot()
    def _frame(self) -> None:
        self.frames += 1
        if self.frames == 1:
            self.startup_s = time.perf_counter() - self.started
            self._next(0)

    def _check_started(self) -> None:
        if self.frames == 0:
            print("Aucune image affichée en 2 minutes : mesure abandonnée", flush=True)
            self.c.app.quit()

    def _update(self) -> None:
        begin = time.perf_counter()
        self.c.tick()
        self.update_ms.append((time.perf_counter() - begin) * 1000)

    def _sample(self) -> dict:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return {"time": time.perf_counter(), "frames": self.frames, "updates": len(self.update_ms),
                "cpu": usage.ru_utime + usage.ru_stime, "threads": thread_cpu(),
                "memoryMb": memory_mb(), "temperatureC": temperature_c()}

    def _next(self, index: int) -> None:
        if index == len(self.plan):
            self.c.app.quit()
            return
        _, setup, _, settle = self.plan[index]
        if setup:
            setup()
        QTimer.singleShot(round(settle * 1000), lambda: self._begin(index))

    def _begin(self, index: int) -> None:
        self._before = self._sample()
        QTimer.singleShot(round(self.plan[index][2] * 1000), lambda: self._end(index))

    def _end(self, index: int) -> None:
        name = self.plan[index][0]
        result = phase_result(name, self._before, self._sample(), self.update_ms, os.getpid())
        self.results.append(result)
        print(format_line(result), flush=True)
        if self.images_dir:
            self.images_dir.mkdir(parents=True, exist_ok=True)
            slug = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
            self.c.window.grabWindow().save(str(self.images_dir / f"{index + 1:02d}-{slug.replace(', ', '-')}.png"))
        self._next(index + 1)

    def _ride(self, index: int, page: str) -> None:
        """Départ (index du parcours ; −1 : sortie libre), puis une sortie simulée de self.minutes avec un tour
        à mi-chemin, et cette page à l'écran."""
        c = self.c
        c.session.start(index)
        steps = round(self.minutes * 60)
        for i in range(steps):
            if i == steps // 2:
                c.model.ride.lap()
            c.step()
        c.tick()
        c.window.setProperty("page", PAGES[page])
        c.window.setProperty("screen", "ride")

    def _pause(self) -> None:
        self.c.window.setProperty("page", PAGES["principale"])
        self.c.model.startPause()

    def _summary(self) -> None:
        QMetaObject.invokeMethod(self.c.window, "finish")  # comme « Maintenir pour terminer »

    def _free_ride(self) -> None:
        self.c.session.discard()  # la sortie sur parcours n'est pas enregistrée
        self.c.window.setProperty("screen", "home")
        self._ride(-1, "carte")
