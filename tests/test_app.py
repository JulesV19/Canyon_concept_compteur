"""L'appli entière, hors écran, dans un processus à part : coupure en pleine sortie ou sur le résumé, enregistrement
refusé, fichiers abîmés, touches qui quittent, Éteindre."""

import os
import shutil
import signal
from pathlib import Path

import pytest
from garmin_fit_sdk import Decoder, Stream

from pilote import ROOT, launch


def test_coupure_en_pleine_sortie_elle_reprend_en_pause(tmp_path):
    process, before = launch("""
        c = open_app()
        def flow():
            c.session.start(0)
            c.window.setProperty("screen", "ride")
            for i in range(600):
                if i == 300:
                    c.model.lap()
                c.step()
            c.tick()
            c.journal.flush()
            barrier(c)
            state = ride_state(c)
            for _ in range(20):  # moins de 30 mesures : encore en mémoire au moment de la coupure
                c.step()
            barrier(c)
            report(state)
            os.kill(os.getpid(), signal.SIGKILL)  # coupure : ni fermeture, ni dernière écriture
        run(c, flow)
    """, tmp_path)
    assert process.returncode == -signal.SIGKILL
    assert before["state"] == "running" and before["laps"] == 2

    process, after = launch("""
        c = open_app()
        banner = c.window.findChild(QObject, "lapBanner")
        def flow():
            wait(800)  # premières images : le bandeau de reprise arrive
            resumed = ride_state(c) | {"screen": c.window.property("screen"), "t": c.t,
                                       "route": c.model.values.get("routeName"),
                                       "resumedAt": c.window.property("resumedAt"),
                                       "banner": banner.property("shown"), "bannerTitle": banner.property("title")}
            last = c.model.ride.track[-1]
            c.model.startPause()  # Start : la sortie repart
            for _ in range(120):
                c.step()
            c.tick()
            lat, lon = c.model.ride.track[resumed["track"]]
            resumed["jumpM"] = math.hypot((lat - last[0]) * 111_320, (lon - last[1]) * 73_500)
            resumed["after"] = ride_state(c)
            report(resumed)
        run(c, flow)
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert after["screen"] == "ride" and after["state"] == "paused"
    assert after["route"] is not None and after["resumedAt"]
    assert after["banner"] and after["bannerTitle"].startswith("Sortie reprise · coupée à ")
    for key in ("distance", "timer", "laps", "track", "records"):
        assert after[key] == before[key], key  # tout ce qui était écrit avant la coupure, rien de plus
    assert after["t"] > before["lastT"]  # l'horloge des mesures ne revient pas en arrière
    assert after["after"]["state"] == "running" and after["after"]["distance"] > after["distance"] + 500
    assert after["jumpM"] < 150  # le cycliste simulé repart d'où il était
    assert "Sortie reprise" in process.stdout


def test_coupure_sur_le_resume_puis_enregistrement(tmp_path):
    process, before = launch("""
        c = open_app()
        def flow():
            c.session.start(1)
            for _ in range(300):
                c.step()
            c.model.startPause()
            c.session.finish()
            barrier(c)
            report({"name": c.session.summary["name"], "distanceKm": c.session.summary["distanceKm"]})
            os.kill(os.getpid(), signal.SIGKILL)
        run(c, flow)
    """, tmp_path)
    assert process.returncode == -signal.SIGKILL

    process, after = launch("""
        c = open_app()
        def flow():
            activate(c)
            state = {"screen": c.window.property("screen"), "name": c.session.summary["name"],
                     "distanceKm": c.session.summary["distanceKm"]}
            QTest.keyClick(c.window, Qt.Key.Key_Return)  # Enregistrer
            state["home"] = wait_for(lambda: c.window.property("screen") == "home")
            state["rides"] = len(c.history.rides)
            report(state)
        run(c, flow)
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert after["screen"] == "summary"
    assert (after["name"], after["distanceKm"]) == (before["name"], before["distanceKm"])
    assert after["home"] and after["rides"] == 1
    files = sorted(tmp_path.iterdir())
    assert [path.suffix for path in files] == [".fit", ".json"]  # le fichier de reprise est effacé
    decoder = Decoder(Stream.from_byte_array(bytearray(files[0].read_bytes())))
    assert decoder.check_integrity()
    messages, errors = Decoder(Stream.from_byte_array(bytearray(files[0].read_bytes()))).read()
    assert errors == [] and len(messages["record_mesgs"]) > 250


def test_bandeau_de_reprise_jamais_sur_une_nouvelle_sortie(tmp_path):
    """Coupure sur le résumé : il revient au démarrage, sans bandeau. La sortie suivante est neuve : pas de « Sortie
    reprise » sur elle."""
    launch("""
        c = open_app()
        def flow():
            c.session.start(0)
            for _ in range(120):
                c.step()
            c.model.startPause()
            c.session.finish()
            barrier(c)
            report({})
            os.kill(os.getpid(), signal.SIGKILL)
        run(c, flow)
    """, tmp_path)
    process, state = launch("""
        c = open_app()
        banner = c.window.findChild(QObject, "lapBanner")
        def flow():
            activate(c)
            state = {"resumedAt": c.window.property("resumedAt")}
            QTest.keyClick(c.window, Qt.Key.Key_Return)  # Enregistrer le résumé revenu
            state["home"] = wait_for(lambda: c.window.property("screen") == "home")
            for _ in range(6):  # le GPS capte
                c.tick()
            QTest.keyClick(c.window, Qt.Key.Key_Return)  # Démarrer une nouvelle sortie
            state["ride"] = wait_for(lambda: c.window.property("screen") == "ride")
            wait(1000)
            state["banner"] = banner.property("shown")
            report(state)
        run(c, flow)
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert state == {"resumedAt": "", "home": True, "ride": True, "banner": False}


def test_arret_du_systeme_pendant_le_demarrage(tmp_path):
    """SIGTERM avant même que l'appli tourne (pendant la reprise d'une longue sortie, par exemple) : elle se ferme
    proprement, et tout ce qui attendait est écrit dans le fichier de reprise."""
    process, state = launch("""
        from compteur import journal
        c = open_app()
        c.session.start(0)
        for _ in range(40):  # moins de 30 mesures depuis la dernière écriture
            c.step()
        os.kill(os.getpid(), signal.SIGTERM)
        QTimer.singleShot(20000, lambda: os._exit(4))  # SIGTERM resté sans effet : l'essai échoue
        c.app.exec()
        c.close()
        found = journal.load(c.journal.path)
        report({"distance": c.model.ride.total.distance_m, "journal": found.ride.total.distance_m})
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert state["journal"] == state["distance"] > 0


@pytest.mark.skipif(os.geteuid() == 0, reason="root écrit partout")
def test_enregistrement_refuse_le_resume_reste_et_on_reessaie(tmp_path):
    rides = tmp_path / "sorties"
    rides.mkdir()
    process, state = launch("""
        c = open_app()
        folder = Path(os.environ["SORTIES"])
        def flow():
            activate(c)
            c.session.start(0)
            c.window.setProperty("screen", "ride")
            for _ in range(120):
                c.step()
            c.model.startPause()
            QTest.keyClick(c.window, Qt.Key.Key_E)  # Terminer : le résumé
            barrier(c)
            os.chmod(folder, 0o555)  # la carte refuse d'écrire
            QTest.keyClick(c.window, Qt.Key.Key_Return)
            wait_for(lambda: c.session.saveError != "")
            wait(1000)  # « Enregistrée » ne vient pas : on reste sur le résumé
            state = {"screen": c.window.property("screen"), "error": c.session.saveError,
                     "files": sorted(p.name for p in folder.iterdir())}
            os.chmod(folder, 0o755)
            QTest.keyClick(c.window, Qt.Key.Key_Return)  # on réessaie
            state["home"] = wait_for(lambda: c.window.property("screen") == "home")
            state["filesAfter"] = sorted(Path(p).suffix for p in os.listdir(folder))
            report(state)
        run(c, flow)
    """, rides)
    assert process.returncode == 0, process.stderr
    assert state["screen"] == "summary" and state["error"] == "écriture refusée"
    assert state["files"] == ["reprise.jsonl"]  # ni fichier temporaire, ni fichier à moitié écrit
    assert state["home"] and state["filesAfter"] == [".fit", ".json"]
    assert "Sortie non enregistrée : PermissionError" in process.stderr


def test_fichiers_abimes_l_appli_demarre_quand_meme(tmp_path):
    routes = tmp_path / "parcours"
    routes.mkdir()
    shutil.copy(ROOT / "parcours" / "vexin.gpx", routes / "vexin.gpx")
    (routes / "a-tronque.gpx").write_text('<gpx><trk><trkseg><trkpt lat="48.7" lon="2.0"/>', encoding="utf-8")
    (routes / "b-un-point.gpx").write_text('<gpx><rte><rtept lat="48.7" lon="2.0"/></rte></gpx>', encoding="utf-8")
    (routes / "c-sur-place.gpx").write_text('<gpx><rte><rtept lat="48.7" lon="2.0"/><rtept lat="48.7" lon="2.0"/>'
                                            '</rte></gpx>', encoding="utf-8")
    map_file = tmp_path / "carte.mbtiles"
    map_file.write_bytes(b"\x00" * 4096)
    rides = tmp_path / "sorties"
    rides.mkdir()
    leftover = rides / "2026-09-01_10-00-00.fit.tmp"  # laissé par une coupure en plein enregistrement
    leftover.write_bytes(b"a moitie")
    process, state = launch("""
        app.ROUTES_DIR = Path(os.environ["PARCOURS"])
        app.MAP_FILE = Path(os.environ["CARTE"])
        c = open_app()
        def flow():
            c.session.start(0)
            for _ in range(60):
                c.step()
            c.tick()
            report({"routes": [route.name for route in c.routes], "distance": c.model.ride.total.distance_m})
        run(c, flow)
    """, rides, PARCOURS=str(routes), CARTE=str(map_file))
    assert process.returncode == 0, process.stderr
    assert not leftover.exists()
    assert len(state["routes"]) == 1 and state["distance"] > 0
    for name in ("a-tronque.gpx", "b-un-point.gpx", "c-sur-place.gpx"):
        assert f"Parcours ignoré ({name})" in process.stderr
    assert "Carte ignorée (carte.mbtiles)" in process.stderr


def test_echap_et_q_ne_quittent_qu_a_l_accueil(tmp_path):
    process, state = launch("""
        c = open_app()
        def flow():
            activate(c)
            state = {}
            c.session.start(0)
            c.window.setProperty("screen", "ride")
            for key in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
                QTest.keyClick(c.window, key)
            wait(100)
            state["ride"] = [c.quit_requested == [], c.window.property("screen")]
            c.model.startPause()
            QTest.keyClick(c.window, Qt.Key.Key_E)  # Terminer : le résumé
            for key in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
                QTest.keyClick(c.window, key)
            wait(100)
            state["summary"] = [c.quit_requested == [], c.window.property("screen")]
            QTest.keyClick(c.window, Qt.Key.Key_Backspace)  # Supprimer : retour à l'accueil
            QTest.keyClick(c.window, Qt.Key.Key_Q)
            wait(100)
            state["home"] = [c.quit_requested == [True], c.window.property("screen")]
            report(state)
        run(c, flow)
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert state == {"ride": [True, "ride"], "summary": [True, "summary"], "home": [True, "home"]}


def test_eteindre_refuse_puis_accepte(tmp_path):
    process, state = launch("""
        c = open_app()
        refusals, quits = [], []
        c.session.powerOffFailed.connect(refusals.append)
        def flow():
            app.on_raspberry_pi = lambda *args: True  # comme sur le Pi
            c.app.quit = lambda: quits.append(True)
            c.window.setProperty("screen", "menu")
            app.POWER_OFF = [sys.executable, "-c", "import sys; sys.exit(1)"]  # polkit refuse
            c.session.powerOff()
            state = {"refusals": list(refusals), "quits": list(quits)}
            app.POWER_OFF = [sys.executable, "-c", "pass"]  # le système accepte : il s'arrête, l'appli se ferme
            c.session.powerOff()
            state["quitsAfter"] = list(quits)
            del c.app.quit
            report(state)
        run(c, flow)
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert state == {"refusals": ["le système refuse l'arrêt"], "quits": [], "quitsAfter": [True]}
    assert "Arrêt refusé (1)" in process.stderr
