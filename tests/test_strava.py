"""Synchro Strava contre un faux serveur : favoris, tracés, jetons renouvelés, limite de lectures, réseau absent."""

import json
import queue
import stat
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from compteur import strava
from compteur.segments import Best, Result, StarredSegment
from compteur.strava import (CACHE_FILE, RECORDS_FILE, TOKENS_FILE, Client, StravaModel, SyncError, kom_label,
                             load_cache, parse_time, save_tokens, starred_segments, sync, synced_text)

NOW = 1_789_000_000.0  # heure des essais (septembre 2026)


class FakeStrava:
    """Faux Strava sur un port local. `routes[chemin]` : la réponse (code, corps JSON), ou une fonction qui la donne
    à partir de la requête. Chaque requête reçue est notée dans `requests`."""

    def __init__(self):
        self.routes = {}
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                url = urlparse(self.path)
                request = {"path": url.path, "query": parse_qs(url.query), "auth": self.headers.get("Authorization"),
                           "form": parse_qs(self.rfile.read(length).decode()) if length else {}}
                fake.requests.append(request)
                route = fake.routes.get(url.path, (404, {"message": "Record Not Found"}))
                status, data = route(request) if callable(route) else route
                payload = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = answer

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def paths(self):
        return [request["path"] for request in self.requests]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def fake():
    server = FakeStrava()
    yield server
    server.close()


def line(offset):
    """Tracé tout droit vers le nord, un point tous les 11 m sur 1,1 km, qui monte de 5 %."""
    return {"latlng": {"data": [[48.6 + i * 0.0001, 1.8 + offset] for i in range(101)]},
            "altitude": {"data": [100 + i * 0.556 for i in range(101)]},
            "distance": {"data": [i * 11.1 for i in range(101)]}}


def record_ride(offset):
    """Flux de la sortie du record sur le tracé de line(offset) : 300 m avant, la première moitié à 5 m/s, la seconde
    à 3,35 m/s (277 s en tout), puis 200 m après. Une mesure par seconde."""
    times, positions, t, d = [], [], 0, -300.0
    while d <= 1312:
        times.append(t)
        positions.append([48.6 + d / 111_195, 1.8 + offset])
        d += 5.0 if d < 556 else 556 / 166
        t += 1
    return {"time": {"data": times}, "latlng": {"data": positions}}


def favorite(segment_id, name, activity="Ride", pr_s=None):
    data = {"id": segment_id, "name": name, "activity_type": activity, "distance": 1112.0, "average_grade": 5.0}
    if pr_s is not None:
        data["athlete_pr_effort"] = {"id": 900 + segment_id, "activity_id": 500 + segment_id, "elapsed_time": pr_s,
                                     "start_date_local": "2026-06-03T07:12:45Z", "distance": 1112.0}
    return data


def publish(fake, favorites, kom="3:12", qom="4:01"):
    """Le faux Strava sert ces favoris, avec leur détail et leur tracé, et renouvelle les jetons."""
    fake.routes["/api/v3/segments/starred"] = (200, favorites)
    for i, segment in enumerate(favorites):
        fake.routes[f"/api/v3/segments/{segment['id']}"] = (200, segment | {"xoms": {"kom": kom, "qom": qom}})
        fake.routes[f"/api/v3/segments/{segment['id']}/streams"] = (200, line(i * 0.01))
    fake.routes["/oauth/token"] = (200, {"access_token": "a2", "refresh_token": "r2", "expires_at": NOW + 21600})


def connect(tmp_path, fake, expires_at=NOW + 30 * 86400, sex="M", clock=None):
    """Appareil relié : ses jetons, et un client qui parle au faux Strava."""
    save_tokens(tmp_path / TOKENS_FILE, {"client_id": "1", "client_secret": "s", "access_token": "a1",
                                         "refresh_token": "r1", "expires_at": expires_at,
                                         "athlete": {"id": 7, "firstname": "Jules", "sex": sex}})
    return Client(tmp_path / TOKENS_FILE, api_url=fake.url + "/api/v3", token_url=fake.url + "/oauth/token",
                  clock=clock or (lambda: NOW))


def test_synchro_des_favoris(tmp_path, fake):
    publish(fake, [favorite(1, "Côte de Senlisse", pr_s=277), favorite(2, "Footing", activity="Run"),
                   favorite(3, "Mur de Cernay")])
    cache = sync(connect(tmp_path, fake), tmp_path / CACHE_FILE)

    assert load_cache(tmp_path / CACHE_FILE) == cache
    assert fake.paths() == ["/api/v3/segments/starred", "/api/v3/segments/1/streams", "/api/v3/segments/1",
                            "/api/v3/segments/3/streams", "/api/v3/segments/3",  # la course à pied est laissée
                            "/api/v3/activities/501/streams"]  # sortie du record, introuvable ici : pas de fantôme
    assert fake.requests[1]["query"] == {"keys": ["latlng,altitude"], "key_by_type": ["true"]}
    assert {request["auth"] for request in fake.requests} == {"Bearer a1"}
    senlisse, cernay = starred_segments(cache)
    assert (senlisse.id, senlisse.name) == (1, "Côte de Senlisse")
    assert senlisse.length_m == pytest.approx(1112, abs=5)
    assert senlisse.route.points[-1].ele == pytest.approx(155.6)
    assert senlisse.pr == Best(277.0, date="2026-06-03")
    assert senlisse.kom == Best(192.0)
    assert cernay.pr is None  # jamais roulé
    assert kom_label(cache) == "KOM"
    assert cache["synced_at"] == NOW


def test_fantome_tire_de_la_sortie_du_record(tmp_path, fake):
    """Ton record vient d'une sortie : ses temps de passage en sont tirés, et le fantôme roule à ton allure d'alors."""
    publish(fake, [favorite(1, "Côte de Senlisse", pr_s=277)])
    fake.routes["/api/v3/activities/501/streams"] = (200, record_ride(0))
    cache = sync(connect(tmp_path, fake), tmp_path / CACHE_FILE)
    assert fake.paths()[-1] == "/api/v3/activities/501/streams"
    assert fake.requests[-1]["query"] == {"keys": ["time,latlng"], "key_by_type": ["true"]}
    assert cache["segments"][0]["ghost"]["activity_id"] == 501
    [segment] = starred_segments(cache)
    assert (segment.pr.elapsed_s, segment.pr.date) == (277, "2026-06-03")
    assert segment.pr.time_at(556, segment.length_m) == pytest.approx(111, abs=3)  # à allure régulière : 138 s


def test_fantome_lu_une_fois_puis_quand_le_record_change(tmp_path, fake):
    now = [NOW]
    client = connect(tmp_path, fake, clock=lambda: now[0])
    publish(fake, [favorite(1, "A", pr_s=277)])
    fake.routes["/api/v3/activities/501/streams"] = (200, record_ride(0))
    sync(client, tmp_path / CACHE_FILE)
    fake.requests.clear()
    now[0] += 86400
    sync(client, tmp_path / CACHE_FILE)
    assert fake.paths() == ["/api/v3/segments/starred"]

    # Nouveau record, dans une sortie supprimée depuis : pas de fantôme, et elle n'est pas relue à chaque synchro
    newer = favorite(1, "A", pr_s=270)
    newer["athlete_pr_effort"]["activity_id"] = 777
    publish(fake, [newer])
    fake.routes["/api/v3/activities/777/streams"] = (404, {"message": "Record Not Found"})
    fake.requests.clear()
    cache = sync(client, tmp_path / CACHE_FILE)
    assert fake.paths() == ["/api/v3/segments/starred", "/api/v3/activities/777/streams"]
    assert starred_segments(cache)[0].pr == Best(270.0, date="2026-06-03")  # allure régulière
    fake.requests.clear()
    sync(client, tmp_path / CACHE_FILE)
    assert fake.paths() == ["/api/v3/segments/starred"]


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


def test_la_synchro_suivante_ne_relit_que_ce_qui_manque(tmp_path, fake):
    now = [NOW]
    client = connect(tmp_path, fake, clock=lambda: now[0])
    publish(fake, [favorite(1, "A"), favorite(3, "B")])
    sync(client, tmp_path / CACHE_FILE)

    # Le lendemain : un favori de plus, un de moins. Seul le nouveau est lu en entier.
    fake.requests.clear()
    now[0] += 86400
    publish(fake, [favorite(3, "B"), favorite(4, "C")])
    cache = sync(client, tmp_path / CACHE_FILE)
    assert fake.paths() == ["/api/v3/segments/starred", "/api/v3/segments/4/streams", "/api/v3/segments/4"]
    assert [entry["id"] for entry in cache["segments"]] == [3, 4]

    # Une semaine plus tard : KOM et record relus, pas les tracés
    fake.requests.clear()
    now[0] += 8 * 86400
    sync(client, tmp_path / CACHE_FILE)
    assert fake.paths() == ["/api/v3/segments/starred", "/api/v3/segments/3", "/api/v3/segments/4"]


def test_jeton_expire_renouvele_et_garde(tmp_path, fake):
    publish(fake, [favorite(1, "A")])
    sync(connect(tmp_path, fake, expires_at=NOW - 60), tmp_path / CACHE_FILE)

    renewal = fake.requests[0]
    assert renewal["path"] == "/oauth/token"
    assert renewal["form"] == {"client_id": ["1"], "client_secret": ["s"], "grant_type": ["refresh_token"],
                               "refresh_token": ["r1"]}
    assert {request["auth"] for request in fake.requests[1:]} == {"Bearer a2"}
    saved = json.loads((tmp_path / TOKENS_FILE).read_text())
    assert (saved["refresh_token"], saved["expires_at"], saved["client_secret"]) == ("r2", NOW + 21600, "s")
    assert stat.S_IMODE((tmp_path / TOKENS_FILE).stat().st_mode) == 0o600


def test_jeton_refuse_renouvele_une_fois(tmp_path, fake):
    """Le Pi sans horloge croit son jeton encore bon : Strava le refuse, il est renouvelé, et la lecture repart."""
    publish(fake, [favorite(1, "A")])
    starred = fake.routes["/api/v3/segments/starred"]
    fake.routes["/api/v3/segments/starred"] = \
        lambda request: starred if request["auth"] == "Bearer a2" else (401, {"message": "Authorization Error"})
    sync(connect(tmp_path, fake), tmp_path / CACHE_FILE)
    assert fake.paths()[:3] == ["/api/v3/segments/starred", "/oauth/token", "/api/v3/segments/starred"]


def test_acces_retire(tmp_path, fake):
    publish(fake, [favorite(1, "A")])
    fake.routes["/api/v3/segments/starred"] = (401, {"message": "Authorization Error"})
    fake.routes["/oauth/token"] = (400, {"message": "Bad Request"})
    with pytest.raises(SyncError, match="connecter.py"):
        sync(connect(tmp_path, fake), tmp_path / CACHE_FILE)
    assert not (tmp_path / CACHE_FILE).exists()


def test_limite_de_lectures_garde_ce_qui_est_arrive(tmp_path, fake):
    favorites = [favorite(1, "A"), favorite(3, "B"), favorite(4, "C")]
    publish(fake, favorites)
    fake.routes["/api/v3/segments/3"] = (429, {"message": "Rate Limit Exceeded"})
    client = connect(tmp_path, fake)
    with pytest.raises(SyncError, match="limite") as caught:
        sync(client, tmp_path / CACHE_FILE)
    assert not caught.value.offline

    # A et le tracé de B sont arrivés avant la limite : ils servent déjà
    cache = load_cache(tmp_path / CACHE_FILE)
    assert [segment.id for segment in starred_segments(cache)] == [1, 3]
    assert cache["synced_at"] is None

    # Un quart d'heure plus tard, la synchro reprend là : le tracé qui manque, puis le détail de B
    publish(fake, favorites)
    fake.requests.clear()
    sync(client, tmp_path / CACHE_FILE)
    assert fake.paths() == ["/api/v3/segments/starred", "/api/v3/segments/4/streams", "/api/v3/segments/4",
                            "/api/v3/segments/3"]


def test_sans_reseau_le_cache_reste(tmp_path, fake):
    publish(fake, [favorite(1, "A")])
    sync(connect(tmp_path, fake), tmp_path / CACHE_FILE)
    before = (tmp_path / CACHE_FILE).read_bytes()
    fake.close()

    client = Client(tmp_path / TOKENS_FILE, api_url=fake.url + "/api/v3", token_url=fake.url + "/oauth/token",
                    clock=lambda: NOW)
    with pytest.raises(SyncError, match="pas de réseau") as caught:
        sync(client, tmp_path / CACHE_FILE)
    assert caught.value.offline
    assert (tmp_path / CACHE_FILE).read_bytes() == before


def test_sans_record_et_qom(tmp_path, fake):
    """Sans abonnement, Strava ne donne peut-être pas le record : le segment sert quand même, sans fantôme."""
    publish(fake, [favorite(1, "A")], kom="3:12", qom="58s")
    cache = sync(connect(tmp_path, fake, sex="F"), tmp_path / CACHE_FILE)
    [segment] = starred_segments(cache)
    assert segment.pr is None
    assert segment.kom == Best(58.0)
    assert kom_label(cache) == "QOM"


def test_segment_supprime_laisse_de_cote(tmp_path, fake):
    publish(fake, [favorite(1, "A"), favorite(3, "B")])
    del fake.routes["/api/v3/segments/1/streams"]
    cache = sync(connect(tmp_path, fake), tmp_path / CACHE_FILE)
    assert [entry["id"] for entry in cache["segments"]] == [3]


def test_autre_compte_repart_de_zero(tmp_path, fake):
    publish(fake, [favorite(1, "A", pr_s=300)])
    sync(connect(tmp_path, fake), tmp_path / CACHE_FILE)
    cache = load_cache(tmp_path / CACHE_FILE)
    cache["athlete"]["id"] = 8  # le cache vient d'un autre compte
    (tmp_path / CACHE_FILE).write_text(json.dumps(cache))
    publish(fake, [favorite(1, "A")])
    fake.requests.clear()
    cache = sync(connect(tmp_path, fake), tmp_path / CACHE_FILE)
    assert "/api/v3/segments/1/streams" in fake.paths()
    assert cache["segments"][0]["pr"] is None


@pytest.mark.parametrize("text, seconds", [("58s", 58), ("4:37", 277), ("1:02:03", 3723), (" 3:12 ", 192),
                                           ("", None), ("0:00", None), ("abc", None), (None, None), ("1:2:3:4", None)])
def test_temps_affiches_par_strava(text, seconds):
    assert parse_time(text) == seconds


def test_moment_de_la_synchro():
    from datetime import datetime

    now = datetime(2026, 9, 14, 20, 0)
    assert synced_text(datetime(2026, 9, 14, 9, 41).timestamp(), now) == "aujourd'hui à 09:41"
    assert synced_text(datetime(2026, 9, 13, 18, 2).timestamp(), now) == "hier à 18:02"
    assert synced_text(datetime(2026, 6, 3, 7, 0).timestamp(), now) == "le 3 juin"
    assert synced_text(None, now) == ""


def test_modele_pour_l_ecran(tmp_path, fake, monkeypatch):
    """La synchro passe par son fil ; l'écran reçoit les segments, avec leur profil en vignette."""
    publish(fake, [favorite(1, "Côte de Senlisse", pr_s=277)])
    connect(tmp_path, fake)
    monkeypatch.setattr(strava, "API_URL", fake.url + "/api/v3")
    monkeypatch.setattr(strava, "TOKEN_URL", fake.url + "/oauth/token")
    posted = queue.SimpleQueue()
    model = StravaModel(tmp_path, posted.put)
    try:
        assert model.property("connected")
        assert model.property("segments") == []
        model.sync()
        assert model.property("syncing")
        posted.get(timeout=10)()  # le résultat, sur le fil de l'interface
        assert not model.property("syncing")
        assert model.property("error") == ""
        [card] = model.property("segments")
        assert (card["name"], card["prS"], card["komS"], card["komLabel"]) == ("Côte de Senlisse", 277, 192, "KOM")
        assert card["prDate"] == "2026-06-03"
        assert card["gradePct"] == pytest.approx(5.0, abs=0.1)
        assert len(card["profile"]) == strava.ROW_PROFILE_POINTS
        assert model.property("syncedText").startswith("aujourd'hui")
        assert [segment.name for segment in model.starred()] == ["Côte de Senlisse"]
    finally:
        model.close()


def test_modele_sans_dossier_ni_jetons(tmp_path):
    posted = queue.SimpleQueue()
    for folder in (None, tmp_path):
        model = StravaModel(folder, posted.put)
        model.sync()
        assert not model.property("connected")
        assert not model.property("syncing")
        assert model.starred() == []
        model.close()
    assert posted.empty()
