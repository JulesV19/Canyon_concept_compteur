import math
from pathlib import Path

import pytest

from compteur.ride import Sample
from compteur.route import Point, Route
from compteur.segments import (APPROACH_M, Abandon, Approach, Best, Finish, SegmentTracker, Start, StarredSegment,
                               record_splits)
from compteur.sim import demo_segments

ROUTE = Route.load(Path(__file__).resolve().parent.parent / "parcours" / "foret-de-rambouillet.gpx")


def carve(start_m: float, end_m: float, segment_id: int = 1, name: str = "Côte d'essai") -> StarredSegment:
    """Segment découpé dans le parcours de démo, un point tous les 10 m."""
    count = int((end_m - start_m) // 10)
    points = [ROUTE.point_at(start_m + i * 10) for i in range(count + 1)] + [ROUTE.point_at(end_m)]
    return StarredSegment(segment_id, name, Route(name, points))


def ride(tracker: SegmentTracker, from_m: float, to_m: float, t0: float = 0.0, speed: float = 5.0,
         heart_rate: float = 150, offset_m: float = 0.0) -> tuple[list, float]:
    """Une mesure par seconde le long du parcours de démo, de from_m à to_m (à rebours si to_m < from_m), à `offset_m`
    à l'est du tracé. Renvoie les évènements et l'heure suivante."""
    events, t = [], t0
    step = speed if to_m >= from_m else -speed
    for i in range(int(abs(to_m - from_m) / speed) + 1):
        d = from_m + i * step
        point = ROUTE.point_at(d)
        heading = ROUTE.heading_at(d) if step > 0 else (ROUTE.heading_at(d) + 180) % 360
        lon = point.lon + offset_m / (111_320 * math.cos(math.radians(point.lat)))
        events += tracker.update(Sample(t=t, speed_mps=speed, heart_rate=heart_rate, lat=point.lat, lon=lon,
                                        altitude_m=point.ele, heading_deg=heading))
        t += 1
    return events, t


def wait(tracker: SegmentTracker, at_m: float, t0: float, seconds: int) -> tuple[list, float]:
    """Arrêt sur place : la vitesse tombe à zéro, les mesures continuent."""
    point = ROUTE.point_at(at_m)
    events = []
    for t in range(int(t0), int(t0) + seconds):
        events += tracker.update(Sample(t=t, speed_mps=0.0, lat=point.lat, lon=point.lon))
    return events, t0 + seconds


def test_annonce_depart_puis_arrivee():
    segment = carve(5000, 6500)
    tracker = SegmentTracker([segment])
    events, _ = ride(tracker, 4000, 7000)
    assert [type(event) for event in events] == [Approach, Start, Finish]
    assert events[0].distance_m <= APPROACH_M
    # Au départ, à 5000 m : t = 200 s ; à l'arrivée, à 6500 m : t = 500 s
    assert events[1].effort.start_t == pytest.approx(200, abs=0.5)
    result = events[2].result
    assert result.elapsed_s == pytest.approx(300, abs=0.5)
    assert result.avg_speed_mps == pytest.approx(5, rel=0.02)
    assert result.avg_heart_rate == pytest.approx(150)
    assert result.new_record and result.pr_gap_s is None  # premier temps
    assert segment.pr.elapsed_s == result.elapsed_s
    assert segment.pr.splits[-1] == (segment.length_m, result.elapsed_s)
    assert tracker.approach is None and tracker.active == []


def test_arrivee_precise_a_grande_vitesse():
    tracker = SegmentTracker([carve(5000, 6500)])
    events, _ = ride(tracker, 4000, 7000, speed=12.0)
    finish = next(event for event in events if isinstance(event, Finish))
    assert finish.result.elapsed_s == pytest.approx(1500 / 12, abs=0.5)


def test_ecart_au_record_a_allure_reguliere():
    segment = carve(5000, 6500)
    segment.pr = Best(250.0)  # plus rapide : on est en retard
    segment.kom = Best(200.0)
    tracker = SegmentTracker([segment])
    ride(tracker, 4000, 5750)
    effort = tracker.active[0]
    assert effort.along_m == pytest.approx(750, rel=0.02)
    assert effort.pr_gap_s == pytest.approx(effort.elapsed_s - 250 * effort.along_m / segment.length_m)
    assert effort.pr_gap_s == pytest.approx(150 - 125, abs=3)
    assert effort.kom_gap_s == pytest.approx(150 - 100, abs=3)
    assert effort.remaining_m == pytest.approx(750, rel=0.02)


def test_fantome_suit_les_temps_de_passage():
    best = Best(100.0, splits=((0, 0), (500, 80), (1000, 100)))
    assert best.time_at(500, 1000) == pytest.approx(80)
    assert best.time_at(750, 1000) == pytest.approx(90)
    # Distances et temps ramenés au segment et au temps du record
    assert Best(120.0, splits=((0, 0), (510, 80), (1020, 100))).time_at(500, 1000) == pytest.approx(96)
    assert Best(200.0).time_at(250, 1000) == pytest.approx(50)
    assert Best(200.0).time_at(2000, 1000) == pytest.approx(200)


def test_record_battu_devient_la_reference():
    segment = carve(5000, 6500)
    segment.pr = Best(400.0)
    tracker = SegmentTracker([segment])
    events, t = ride(tracker, 4000, 7000)
    first = next(event for event in events if isinstance(event, Finish)).result
    assert first.new_record and first.pr_gap_s == pytest.approx(-100, abs=0.5)
    assert segment.pr.elapsed_s == pytest.approx(300, abs=0.5)
    # Second passage, plus lent : comparé au nouveau record, fantôme compris
    events, _ = ride(tracker, 4000, 7000, t0=t + 60, speed=4.0)
    second = next(event for event in events if isinstance(event, Finish)).result
    assert not second.new_record
    assert second.pr_gap_s == pytest.approx(375 - 300, abs=0.5)
    assert segment.pr.elapsed_s == pytest.approx(300, abs=0.5)


def test_chrono_compte_les_arrets():
    tracker = SegmentTracker([carve(5000, 6500)])
    events, t = ride(tracker, 4000, 5700)
    more, t = wait(tracker, 5700, t, 30)
    events += more
    more, _ = ride(tracker, 5700, 7000, t0=t)
    events += more
    finish = next(event for event in events if isinstance(event, Finish))
    assert finish.result.elapsed_s == pytest.approx(300 + 30, abs=1)


def test_abandon_hors_du_segment():
    tracker = SegmentTracker([carve(5000, 6500)])
    events, t = ride(tracker, 4000, 5600)
    assert [type(event) for event in events] == [Approach, Start]
    events, _ = ride(tracker, 5600, 5660, t0=t, offset_m=200)  # 13 s à 200 m du tracé
    assert [type(event) for event in events] == [Abandon]
    assert tracker.active == []


def test_abandon_sur_demi_tour():
    tracker = SegmentTracker([carve(5000, 6500)])
    events, t = ride(tracker, 4000, 5600)
    events, _ = ride(tracker, 5600, 5400, t0=t)
    assert [type(event) for event in events] == [Abandon]


def test_segment_a_rebours_ne_compte_pas():
    tracker = SegmentTracker([carve(5000, 6500)])
    events, _ = ride(tracker, 7000, 4000)
    assert events == []
    assert tracker.efforts == []


def test_segments_qui_se_chevauchent():
    long, short = carve(5000, 6500, 1, "Longue"), carve(5000, 5800, 2, "Courte")
    tracker = SegmentTracker([long, short])
    events, t = ride(tracker, 4000, 5300)
    assert sorted(event.effort.segment.name for event in events if isinstance(event, Start)) == ["Courte", "Longue"]
    assert [effort.segment.name for effort in tracker.active] == ["Courte", "Longue"]  # celui qui finit le premier
    events, _ = ride(tracker, 5300, 7000, t0=t)
    assert [event.result.segment.name for event in events if isinstance(event, Finish)] == ["Courte", "Longue"]


def test_sans_position_le_chrono_tourne():
    tracker = SegmentTracker([carve(5000, 6500)])
    _, t = ride(tracker, 4000, 5500)
    effort = tracker.active[0]
    elapsed = effort.elapsed_s
    assert tracker.update(Sample(t=t + 5)) == []
    assert effort.elapsed_s == pytest.approx(elapsed + 6)


def test_cote_d_essai_du_simulateur():
    [segment] = demo_segments(ROUTE)
    assert segment.length_m == pytest.approx(1000, rel=0.02)
    assert segment.route.points[-1].ele - segment.route.points[0].ele > 50  # le kilomètre le plus raide : 69 m
    assert segment.pr.elapsed_s > segment.kom.elapsed_s


def test_pas_de_cote_d_essai_sur_un_parcours_qui_passe_par_un_favori():
    assert demo_segments(ROUTE, [carve(5000, 6500)]) == []
    elsewhere = StarredSegment(9, "Ailleurs", Route("Ailleurs", [Point(49.0, 2.0), Point(49.01, 2.0)]))
    assert len(demo_segments(ROUTE, [elsewhere])) == 1


def circle(length_m: float = 1200.0) -> Route:
    """Boucle qui finit sur son départ, un point tous les 10 m, dans le sens des aiguilles d'une montre."""
    radius, count = length_m / (2 * math.pi), int(length_m // 10)
    kx = 111_195 * math.cos(math.radians(48.85))
    return Route("Boucle", [Point(48.85 + radius * math.cos(2 * math.pi * i / count) / 111_195,
                                  2.23 + radius * math.sin(2 * math.pi * i / count) / kx) for i in range(count + 1)])


def test_tours_enchaines_sur_une_boucle():
    """Longchamp : on rejoint la boucle en route, puis les tours s'enchaînent, chacun avec son temps."""
    loop = circle()
    segment = StarredSegment(1, "Boucle", loop)
    assert segment.loop and not carve(5000, 6500).loop
    tracker, events, speed = SegmentTracker([segment]), [], 8.0
    for i in range(int(2.5 * loop.length_m / speed)):
        d = (0.75 * loop.length_m + i * speed) % loop.length_m
        point = loop.point_at(d)
        events += tracker.update(Sample(t=float(i), speed_mps=speed, lat=point.lat, lon=point.lon,
                                        heading_deg=loop.heading_at(d)))
    assert [type(event) for event in events] == [Start, Finish, Start, Finish, Start]
    for finish in events[1::2][:2]:
        assert finish.result.elapsed_s == pytest.approx(loop.length_m / speed, abs=1.5)


def trace(from_m: float, to_m: float, t0: float, speed: float) -> tuple[list[Sample], float]:
    """Une sortie enregistrée, comme dans les flux Strava : l'heure et la position, une mesure par seconde."""
    samples, t = [], t0
    step = speed if to_m >= from_m else -speed
    for i in range(int(abs(to_m - from_m) / speed) + 1):
        point = ROUTE.point_at(from_m + i * step)
        samples.append(Sample(t=t, lat=point.lat, lon=point.lon))
        t += 1
    return samples, t


def test_fantome_retrouve_dans_la_sortie_du_record():
    """Une sortie qui passe deux fois sur le segment : le fantôme vient du passage au temps du record."""
    segment = carve(5000, 6500)
    steady, t = trace(4000, 7000, 0, 5.0)  # 300 s sur le segment
    back, t = trace(7000, 4000, t, 10.0)   # retour à rebours : ne compte pas
    fast, t = trace(4000, 5750, t, 6.0)    # la première moitié vite (125 s)...
    slow, t = trace(5750, 7000, t, 3.75)   # ... la seconde lentement (200 s)
    samples = steady + back + fast + slow
    splits = record_splits(segment.route, samples, 326.0)  # Strava ne coupe pas la ligne pile au même endroit
    assert splits[-1][1] == pytest.approx(325, abs=1.5)
    assert Best(326.0, splits).time_at(750, segment.length_m) == pytest.approx(125, abs=2)
    assert record_splits(segment.route, samples, 300.0)[-1][1] == pytest.approx(300, abs=1)
    assert record_splits(segment.route, samples, 250.0) == ()  # aucun passage à ce temps-là
