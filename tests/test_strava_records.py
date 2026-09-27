"""Records Strava : celui du compteur, et le record battu gardé sur la carte SD."""

import json
import queue
from datetime import date

from compteur.segments import Best, Result, StarredSegment
from compteur.strava import CACHE_FILE, RECORDS_FILE, StravaModel, starred_segments
from strava_fake import NOW


def test_record_du_compteur_tant_que_strava_n_en_donne_pas_d_autre():
    entry = {"id": 1, "name": "A", "points": [[48.6 + i * 0.0001, 1.8, 100.0] for i in range(101)],
             "pr": {"elapsed_s": 300.0, "date": "2026-06-03", "activity_id": 501},
             "ghost": {"activity_id": 501, "splits": [[0, 0], [556, 100], [1112, 300]]}}
    cache = {"segments": [entry]}
    kept = {"elapsed_s": 280.0, "date": "2026-09-14", "strava_pr_s": 300.0, "splits": [[0, 0], [1112, 280]]}
    assert starred_segments(cache)[0].pr == Best(300.0, ((0, 0), (556, 100), (1112, 300)), "2026-06-03")
    assert starred_segments(cache, {"1": kept})[0].pr == Best(280.0, ((0, 0), (1112, 280)), "2026-09-14")
    # La sortie envoyée : Strava donne le nouveau record, avec son temps à lui (son fantôme viendra à la synchro)
    entry["pr"] = {"elapsed_s": 282.0, "date": "2026-09-14", "activity_id": 900}
    assert starred_segments(cache, {"1": kept})[0].pr == Best(282.0, date="2026-09-14")
    # Premier temps sur un segment jamais roulé
    entry["pr"] = None
    assert starred_segments(cache, {"1": kept | {"strava_pr_s": None}})[0].pr.elapsed_s == 280.0
    assert starred_segments(cache, {"1": kept})[0].pr is None


def test_record_battu_garde_sur_le_compteur(tmp_path):
    """Un record battu en route est gardé sur la carte SD, avec ses temps de passage : il sert dès la sortie suivante,
    même sans réseau. La côte d'essai du simulateur, elle, n'est pas gardée."""
    (tmp_path / CACHE_FILE).write_text(json.dumps({"athlete": {"id": 7, "sex": "M"}, "synced_at": NOW, "segments": [
        {"id": 1, "name": "A", "points": [[48.6 + i * 0.0001, 1.8, 100.0] for i in range(101)],
         "pr": {"elapsed_s": 300.0, "date": "2026-06-03"}, "kom_s": 200.0}]}))
    posted = queue.SimpleQueue()
    model = StravaModel(tmp_path, posted.put)
    splits = ((0.0, 0.0), (556.0, 120.0), (1112.0, 280.0))
    try:
        [segment] = model.starred()
        demo = StarredSegment(0, "Côte d'essai", segment.route)
        model.keep_record(Result(demo, 250.0, None, None, True, 4.4, None, None, None, splits))
        model.keep_record(Result(segment, 310.0, 10.0, 110.0, False, 3.6, None, None, segment.pr, splits))
        assert posted.empty() and not (tmp_path / RECORDS_FILE).exists()
        model.keep_record(Result(segment, 280.04, -20.0, 80.0, True, 4.0, None, None, segment.pr, splits))
        assert model.property("segments")[0]["prS"] == 280.0
        posted.get(timeout=10)()  # écrit par le fil de la synchro
    finally:
        model.close()
    today = date.today().isoformat()
    assert json.loads((tmp_path / RECORDS_FILE).read_text()) == {
        "1": {"elapsed_s": 280.0, "date": today, "strava_pr_s": 300.0, "splits": [list(split) for split in splits]}}
    again = StravaModel(tmp_path, posted.put)
    assert again.starred()[0].pr == Best(280.0, splits, today)
    again.close()
