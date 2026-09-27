"""Pour les essais de l'appli entière : elle tourne hors écran dans un processus à part, pilotée par un bout de code.
Ce code rend ses résultats par `report(...)` (une ligne « @@ » en JSON)."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PRELUDE = '''
import json, math, os, signal, sys, threading, traceback
from pathlib import Path
from PySide6.QtCore import QEventLoop, QMetaObject, QObject, QPoint, Qt, QTimer
from PySide6.QtTest import QTest
import compteur.app as app
import compteur.pi as pi
from compteur.app import Compteur
from compteur.captures import PAGES

def open_app(**options):
    """L'appli, sortie protégée par le fichier de reprise, dans le dossier des sorties de l'essai. Le temps avance à la
    main (step, tick)."""
    options = {"software_rendering": True, "recovery": True} | options
    c = Compteur(["essai"], intro=False, rides_dir=Path(os.environ["SORTIES"]), **options)
    c.timer.stop()
    c.quit_requested = []
    c.engine.quit.connect(lambda: c.quit_requested.append(True))  # Qt.quit() depuis l'interface
    return c

def barrier(c):
    """Attend que le fil d'écriture ait fini ce qu'on lui a confié."""
    done = threading.Event()
    c.writer.submit(done.set)
    assert done.wait(10)

def wait(ms):
    """Laisse tourner l'appli `ms` millisecondes. Surtout pas QTest.qWait : il garde Python pour lui (GIL) pendant
    l'attente, et le fil qui charge les tuiles de la carte, qui passe par Python, reste bloqué, et l'appli avec lui."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()

def wait_for(condition, timeout=10.0):
    for _ in range(int(timeout / 0.05)):
        if condition():
            return True
        wait(50)
    return condition()

def activate(c):
    """Sans fenêtre active, les raccourcis clavier sont ignorés."""
    c.window.requestActivate()
    assert wait_for(c.window.isActive)

def ride_state(c):
    ride = c.model.ride
    return {"state": ride.state.value, "distance": ride.total.distance_m, "timer": ride.total.timer_s,
            "laps": len(ride.laps), "track": len(ride.track), "records": len(ride.records), "lastT": ride.last_t}

def report(values):
    print("@@" + json.dumps(values), flush=True)

def run(c, flow):
    """Déroule `flow` dans la boucle de l'appli."""
    def wrapped():
        try:
            flow()
        except BaseException:
            traceback.print_exc()
            os._exit(3)
        c.app.quit()
    QTimer.singleShot(0, wrapped)
    c.app.exec()
    c.close()
'''


def launch(code: str, rides: Path, **env: str) -> tuple[subprocess.CompletedProcess, dict]:
    """Lance l'appli avec ce code ; renvoie le processus et le dernier `report`."""
    process = subprocess.run([sys.executable, "-c", PRELUDE + textwrap.dedent(code)], cwd=ROOT, capture_output=True,
                             text=True, timeout=180,
                             env=os.environ | {"QT_QPA_PLATFORM": "offscreen", "SORTIES": str(rides)} | env)
    reports = [line[2:] for line in process.stdout.splitlines() if line.startswith("@@")]
    assert reports, f"code {process.returncode}\n{process.stdout}\n{process.stderr}"
    return process, json.loads(reports[-1])
