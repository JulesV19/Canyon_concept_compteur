"""Synchro des segments Strava en favori : tracés, détails, fantômes, reprise après une synchro inachevée."""

import json

import pytest

from compteur.segments import Best
from compteur.strava import (CACHE_FILE, TOKENS_FILE, Client, SyncError, kom_label, load_cache, starred_segments,
                             sync)
from strava_fake import NOW, connect, favorite, publish, record_ride


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
