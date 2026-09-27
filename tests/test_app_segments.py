"""L'appli entière, hors écran : segments Strava au menu et pendant la sortie."""

import json

from compteur.route import Route
from compteur.strava import CACHE_FILE, TOKENS_FILE, save_tokens
from pilote import ROOT, launch


def test_page_segment_ouverte_au_depart_puis_retiree(tmp_path):
    """La page segment arrive toujours en deuxième, quelle que soit la page affichée, puis s'en va en y revenant."""
    process, result = launch("""
        c = open_app()
        c.window.setProperty("segmentResultMs", 300)
        def flow():
            c.session.start(0)
            c.window.setProperty("screen", "ride")
            c.window.setProperty("page", 3)  # page cardio
            tracker = c.model.tracker
            for _ in range(4 * 3600):  # jusqu'au départ de la côte d'essai
                if tracker.active:
                    break
                c.step()
            c.tick()
            wait(800)  # les bandes orange passent, la page segment arrive
            opened = {"count": c.window.property("pageCount"), "open": c.window.property("segmentOpen"),
                      "page": c.window.property("page")}
            for _ in range(3600):  # jusqu'à l'arrivée
                if tracker.results:
                    break
                c.step()
            c.tick()
            wait(100)
            page = c.window.findChild(QObject, "segmentPage")
            finished = {"result": page.property("finished"), "page": c.window.property("page")}
            wait(700)  # le résultat s'en va, et la page avec lui
            closed = {"count": c.window.property("pageCount"), "open": c.window.property("segmentOpen"),
                      "page": c.window.property("page")}
            report({"opened": opened, "finished": finished, "closed": closed})
        run(c, flow)
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert result["opened"] == {"count": 7, "open": True, "page": 1}
    assert result["finished"] == {"result": True, "page": 1}
    assert result["closed"] == {"count": 6, "open": False, "page": 3}  # de retour sur la page cardio


def test_segments_strava_au_menu_puis_suivis_en_sortie(tmp_path):
    """Les favoris du cache Strava : au menu (↓ puis Entrée), puis suivis pendant la sortie. Sans synchro : rien ne
    part sur le réseau."""
    folder = tmp_path / "strava"
    route = Route.load(ROOT / "parcours" / "foret-de-rambouillet.gpx")
    save_tokens(folder / TOKENS_FILE, {"client_id": "0", "client_secret": "x", "access_token": "x",
                                       "refresh_token": "x", "expires_at": 0, "athlete": {"id": 1, "sex": "F"}})
    (folder / CACHE_FILE).write_text(json.dumps({
        "athlete": {"id": 1, "sex": "F"}, "synced_at": 1,
        "segments": [{"id": 5, "name": "Côte test", "points": [[p.lat, p.lon, p.ele] for p in route.points[40:120]],
                      "pr": {"elapsed_s": 300, "date": "2026-06-03"}, "kom_s": 200, "qom_s": 240, "detail_at": 1}],
    }))
    process, result = launch(f"""
        c = open_app(strava_dir=Path({str(folder)!r}))
        def flow():
            activate(c)
            c.window.setProperty("screen", "menu")
            wait(400)
            QTest.keyClick(c.window, Qt.Key.Key_Down)    # Segments Strava
            QTest.keyClick(c.window, Qt.Key.Key_Return)
            wait(400)
            page = c.window.findChild(QObject, "segmentsPage")
            opened = {{"screen": c.window.property("screen"), "listed": [s["name"] for s in page.property("segments")],
                       "syncing": c.strava.property("syncing")}}
            QTest.keyClick(c.window, Qt.Key.Key_Escape)  # retour au menu
            wait(400)
            back = c.window.property("screen")
            c.window.setProperty("screen", "home")
            c.session.start(0)
            report({{"opened": opened, "back": back, "followed": [s.name for s in c.model.segments],
                     "label": c.model.kom_label, "crown": c.model.segments[0].kom.elapsed_s}})
        run(c, flow)
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert result["opened"] == {"screen": "segments", "listed": ["Côte test"], "syncing": False}
    assert result["back"] == "menu"
    assert result["followed"] == ["Côte test"]  # pas de côte d'essai : le parcours passe par un favori
    assert (result["label"], result["crown"]) == ("QOM", 240)
