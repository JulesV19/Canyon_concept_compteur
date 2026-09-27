import math

import pytest

from PySide6.QtCore import QPointF

from compteur.model import RideModel, route_progress, simplified, snapshot
from compteur.ride import Ride, Sample
from compteur.route import Point, Position, Route
from compteur.segments import Best, StarredSegment


def test_snapshot_unites_ecran():
    ride = Ride()
    ride.update(Sample(t=0))
    ride.start_pause()
    for t in range(1, 3601):
        ride.update(Sample(t=t, speed_mps=10, heart_rate=140, altitude_m=100 + t * 0.1))
    ride.lap()

    values = snapshot(ride)
    assert values["state"] == "running"
    assert values["speedKmh"] == pytest.approx(36)
    assert values["distanceKm"] == pytest.approx(36)
    assert values["avgSpeedKmh"] == pytest.approx(36)
    assert values["hrZone"] == 3  # 140 bpm = 74 % de 190
    assert values["ascentM"] == pytest.approx(360, abs=2)
    assert values["gradePct"] == pytest.approx(1)  # 0,1 m tous les 10 m
    assert values["lap"]["number"] == 2
    assert values["lap"]["avgSpeedKmh"] is None  # tour tout juste commencé


def test_segment_en_direct_dans_les_valeurs():
    points = [Point(48.7 + i * 0.0001, 2.0, 100 + i * 0.5) for i in range(300)]  # vers le nord, 4,5 %
    route = Route("Route", points)
    segment = StarredSegment(7, "Côte", Route("Côte", points[100:201]), pr=Best(200.0), kom=Best(150.0))
    model = RideModel(Ride(), segments=[segment])
    events = {"approached": [], "started": [], "finished": []}
    model.segmentApproached.connect(events["approached"].append)
    model.segmentStarted.connect(events["started"].append)
    model.segmentFinished.connect(events["finished"].append)

    def ride_to(t_end, t_start):
        for t in range(t_start, t_end):
            p = route.point_at(5.0 * t)
            model.update(Sample(t=t, speed_mps=5.0, heart_rate=140, lat=p.lat, lon=p.lon, altitude_m=p.ele,
                                heading_deg=0))
            model.refresh()

    ride_to(1, 0)
    model.startPause()
    ride_to(330, 1)  # départ du segment à 1112 m (t ≈ 222 s), mi-segment à t = 330 s
    assert len(events["approached"]) == 1 and events["approached"][0]["distanceM"] <= 300
    assert [card["name"] for card in events["started"]] == ["Côte"]
    live = model.values["segment"]
    assert live["doneKm"] == pytest.approx(0.54, abs=0.02)
    assert live["gapS"] == pytest.approx(live["elapsedS"] - 200 * live["progress"], abs=0.01)
    assert live["gapS"] == pytest.approx(11, abs=1.5)  # plus lent que le record (200 s pour 1112 m)
    assert live["komLabel"] == "KOM" and live["gradePct"] == pytest.approx(4.5, rel=0.02)
    assert len(model.segmentProfile) >= 10

    ride_to(500, 330)
    [result] = events["finished"]
    assert not result["newRecord"]
    assert result["elapsedS"] == pytest.approx(222, abs=1) and result["gapS"] == pytest.approx(22, abs=1)
    assert result["prS"] == 200 and result["avgHeartRate"] == pytest.approx(140)
    assert "segment" not in model.values
    assert len(model.segmentProfile) >= 10  # le profil du segment fini reste pour l'écran d'arrivée


def test_record_battu_confie_a_garder():
    points = [Point(48.7 + i * 0.0001, 2.0, 100.0) for i in range(300)]
    route = Route("Route", points)
    beaten, kept = [StarredSegment(i, name, Route(name, points[100:201]), pr=Best(pr_s))
                    for i, name, pr_s in ((1, "Battu", 300.0), (2, "Tenu", 100.0))]
    model = RideModel(Ride(), segments=[beaten, kept])
    records = []
    model.record_beaten = records.append
    for t in range(500):
        p = route.point_at(5.0 * t)
        model.update(Sample(t=t, speed_mps=5.0, lat=p.lat, lon=p.lon, heading_deg=0))
        if t == 0:
            model.startPause()
    assert [result.segment.name for result in records] == ["Battu"]
    assert records[0].elapsed_s == pytest.approx(222, abs=1) and records[0].splits[-1][1] == records[0].elapsed_s


def test_snapshot_sans_mesure():
    values = snapshot(Ride())
    assert values["state"] == "idle"
    assert values["speedKmh"] is None
    assert values["gradePct"] is None


def test_avancement_sur_le_parcours():
    route = Route("Boucle", [Point(48.70, 2.0), Point(48.71, 2.0)])
    progress = route_progress(route, Position(along_m=route.length_m / 4, offset_m=5))
    assert progress["routeName"] == "Boucle"
    assert progress["routeAscentM"] == route.ascent_m
    assert progress["routeRemainingKm"] == pytest.approx(route.length_m * 0.75 / 1000)
    assert progress["routeProgress"] == pytest.approx(0.25)
    assert not progress["offRoute"]
    assert route_progress(None, None) == {}


def test_avancement_dessine_sur_la_carte():
    # 1 km vers le nord, puis 1 km vers l'est : au milieu du deuxième segment, le creux du parcours
    # s'arrête au milieu de ce segment tel qu'il est dessiné (et pas à la même fraction de tout le tracé)
    route = Route("Coude", [Point(48.70, 2.0), Point(48.709, 2.0), Point(48.709, 2.0137)])
    model = RideModel(Ride(), route)
    assert model.values["routeDoneLength"] == 0
    model.update(Sample(t=0, lat=48.709, lon=2.00685))
    model.refresh()
    a, b, c = model.routePath
    first = math.hypot(b.x() - a.x(), b.y() - a.y())
    second = math.hypot(c.x() - b.x(), c.y() - b.y())
    assert model.values["routeDoneLength"] == pytest.approx(first + second / 2)


def test_trace_par_troncons(monkeypatch):
    monkeypatch.setattr("compteur.model.ride.TRACK_CHUNK", 10)
    monkeypatch.setattr("compteur.model.ride.TRACK_TOLERANCE", 0)  # tous les points (voir test_trace_allegee)
    model = RideModel(Ride())
    finished = []
    model.trackChunksChanged.connect(lambda: finished.append(model.trackChunkCount))
    model.startPause()
    for t in range(1, 40):  # 10 m par seconde : un point de trace à chaque mesure
        model.update(Sample(t=t, speed_mps=10, lat=48.70 + t * 0.00009, lon=2.0))
        model.refresh()

    chunks = [model.trackChunk(i) for i in range(model.trackChunkCount)]
    recent = model.trackRecent
    assert model.trackChunk(3) == [] and model.trackChunk(-1) == []
    assert finished == [1, 2, 3]  # chaque tronçon n'est envoyé qu'une fois, quand il est fini
    assert [len(chunk) for chunk in chunks] == [11, 11, 11]
    # Les tronçons se raccordent, et le tronçon en cours part de la fin du dernier
    assert all(a[-1] == b[0] for a, b in zip(chunks, chunks[1:] + [recent]))
    # Toute la trace, chaque point une fois ; le dernier point reçu est encore dans le tronçon en cours
    assert sum(len(chunk) - 1 for chunk in chunks) + len(recent) == len(model.ride.track) == 39

    model.reset(Ride(), None)
    assert model.trackChunkCount == 0
    assert model.trackRecent == []


def test_nouvelle_sortie_remise_a_zero():
    route = Route("Nord", [Point(48.70, 2.0), Point(48.72, 2.0)])
    model = RideModel(Ride(), route)
    model.startPause()
    for t in range(1, 200):
        model.update(Sample(t=t, speed_mps=8, lat=48.70 + t * 0.00007, lon=2.0))
    model.refresh()
    assert model.values["state"] == "running"
    assert model.trackRecent and model.routePath

    model.reset(Ride(), None)
    assert model.values["state"] == "idle"
    assert model.routePath == []
    assert model.trackRecent == []
    assert "routeName" not in model.values


def test_valeurs_des_pages_altitude_cardio_tours():
    # 2,2 km vers le nord, 10 m de montée tous les 556 m
    route = Route("Nord", [Point(48.70 + i * 0.005, 2.0, 100 + i * 10) for i in range(5)])
    model = RideModel(Ride(max_hr=200), route)
    profile = model.routeProfile  # tous les 50 m, en km
    assert (profile[0].x(), profile[0].y()) == (0, 100)
    assert profile[1].x() == pytest.approx(0.05, rel=0.02)
    assert profile[-1].x() == pytest.approx(route.length_m / 1000)

    model.startPause()
    for t in range(1, 121):
        if t == 60:
            model.lap()
        model.update(Sample(t=t, speed_mps=8, heart_rate=150, altitude_m=100 + t * 0.2,
                            lat=48.70 + t * 0.00007, lon=2.0))
        model.refresh()
    values = model.values
    assert values["routeDoneKm"] == pytest.approx(values["routeKm"] - values["routeRemainingKm"])
    assert values["routeAscentLeftM"] == pytest.approx(30)  # le premier palier est passé
    assert values["hrZoneBounds"] == pytest.approx([120, 140, 160, 180])
    assert values["hrZonesS"][2] == pytest.approx(119)  # 150 bpm : zone 3 (FC max 200)
    curve = model.heartRateCurve  # 24 tranches de 5 s, puis la dernière mesure
    assert len(curve) == 25
    assert all(p.y() == 150 for p in curve)
    assert [lap["number"] for lap in model.laps] == [1]  # tours finis
    assert model.rideProfile[-1].x() == pytest.approx(values["distanceKm"], abs=0.06)


def test_courbe_cardio_par_tranches_de_5_s():
    """Moyennes calées sur le numéro des mesures : la courbe glisse sans changer de forme. La tranche en cours et
    celle que l'historique de 10 minutes a entamée sont laissées de côté ; la dernière mesure finit la courbe."""
    model = RideModel(Ride())
    for t in range(1, 608):  # 607 mesures : les 7 premières sont sorties de l'historique
        model.update(Sample(t=t, heart_rate=t))
    curve = [(p.x(), p.y()) for p in model.heartRateCurve]
    assert len(curve) == 120
    assert curve[0] == (594, 13)    # mesures 11 à 15 : moyenne 13, il y a 594 s (au milieu de la tranche)
    assert curve[1] == (589, 18)
    assert curve[-2] == (4, 603)    # mesures 601 à 605 ; la 606e et la 607e forment la tranche en cours
    assert curve[-1] == (0, 607)    # la dernière mesure


def test_numero_de_mise_a_jour():
    """Ce qui clignote suit ce numéro : une mise à jour de plus, un clignotement de plus, aucune animation."""
    model = RideModel(Ride())
    before = model.values["tick"]
    model.refresh()
    assert model.values["tick"] == before + 1


def test_sortie_reprise_retrouve_sa_position_sur_un_aller_retour():
    """Reprise au retour d'un aller-retour : la position est au retour, pas au même endroit de l'aller."""
    out = [Point(48.70 + i * 0.001, 2.0) for i in range(11)]
    route = Route("Aller-retour", out + out[-2::-1])
    ride = Ride()
    ride.update(Sample(t=0, lat=48.70, lon=2.0))
    ride.start_pause()
    for t, distance in enumerate(range(8, 2000, 8), start=1):
        point = route.point_at(distance)
        ride.update(Sample(t=t, speed_mps=8, lat=point.lat, lon=point.lon))
    model = RideModel(Ride(), None)
    model.resume(ride, route)
    assert model.position.along_m == pytest.approx(1992, abs=5)
    assert model.values["routeDoneKm"] == pytest.approx(1.992, abs=0.005)
    assert model.values["distanceKm"] == pytest.approx(ride.total.distance_m / 1000)


def test_trace_allegee_sans_que_ca_se_voie():
    """Les points qui s'écartent de moins d'un pixel disparaissent ; les bouts et un demi-tour restent."""
    line = [QPointF(x, 0.3 * (x % 2)) for x in range(20)]  # tout droit, à 0,3 pixel près
    assert simplified(line, 1.0) == [line[0], line[-1]]
    corner = [QPointF(x, 0) for x in range(10)] + [QPointF(9, y) for y in range(1, 10)]
    assert simplified(corner, 1.0) == [corner[0], corner[9], corner[-1]]
    # Aller-retour dans le même tronçon : le bout du demi-tour est au-delà du segment départ-arrivée, il reste
    u_turn = [QPointF(x, 0) for x in range(10)] + [QPointF(x, 0.5) for x in range(8, 2, -1)]
    assert QPointF(9, 0) in simplified(u_turn, 1.0)
    assert simplified(line, 0) == line
    assert simplified(line[:2], 1.0) == line[:2]


def test_troncons_allegés_et_raccordes(monkeypatch):
    monkeypatch.setattr("compteur.model.ride.TRACK_CHUNK", 10)
    model = RideModel(Ride())
    model.startPause()
    for t in range(1, 40):  # tout droit vers le nord : chaque tronçon fini se réduit à ses deux bouts
        model.update(Sample(t=t, speed_mps=10, lat=48.70 + t * 0.00009, lon=2.0))
        model.refresh()
    chunks = [model.trackChunk(i) for i in range(model.trackChunkCount)]
    assert [len(chunk) for chunk in chunks] == [2, 2, 2]
    assert all(a[-1] == b[0] for a, b in zip(chunks, chunks[1:] + [model.trackRecent]))
