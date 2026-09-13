import math

import pytest

from compteur.ride import AUTO_PAUSE_DELAY_S, MAX_GAP_S, Climb, Ride, Sample, State


def started_ride(**options) -> Ride:
    ride = Ride(**options)
    ride.update(Sample(t=0))
    ride.start_pause()
    return ride


def feed(ride: Ride, start: float, seconds: int, **values) -> float:
    """Une mesure par seconde, de start+1 à start+seconds. Renvoie le dernier t.
    `climb_mps` fait monter (ou descendre) l'altitude à chaque seconde."""
    climb = values.pop("climb_mps", 0.0)
    altitude = values.pop("altitude_m", None)
    for i in range(1, seconds + 1):
        if altitude is not None:
            altitude += climb
        ride.update(Sample(t=start + i, altitude_m=altitude, **values))
    return start + seconds


def test_rien_ne_compte_avant_start():
    ride = Ride()
    feed(ride, 0, 30, speed_mps=10)
    assert ride.state is State.IDLE
    assert ride.total.timer_s == 0
    assert ride.total.distance_m == 0
    assert ride.current.speed_mps == 10  # la vitesse s'affiche quand même


def test_distance_temps_moyenne():
    ride = started_ride()
    feed(ride, 0, 60, speed_mps=10)
    assert ride.total.timer_s == 60
    assert ride.total.distance_m == pytest.approx(600)
    assert ride.total.avg_speed_mps == pytest.approx(10)


def test_pause_manuelle():
    ride = started_ride()
    t = feed(ride, 0, 30, speed_mps=8)
    ride.start_pause()
    t = feed(ride, t, 20, speed_mps=8)  # on pousse le vélo en pause : ne compte pas
    assert ride.state is State.PAUSED
    ride.start_pause()
    feed(ride, t, 30, speed_mps=8)
    assert ride.total.timer_s == 60
    assert ride.total.distance_m == pytest.approx(480)
    assert ride.elapsed_s == 80


def test_auto_pause_au_feu_rouge():
    ride = started_ride()
    t = feed(ride, 0, 60, speed_mps=8)
    t = feed(ride, t, 30, speed_mps=0)
    assert ride.auto_paused
    # Seules les secondes avant le déclenchement comptent
    assert ride.total.timer_s == 60 + AUTO_PAUSE_DELAY_S
    assert ride.elapsed_s == 90

    feed(ride, t, 10, speed_mps=8)
    assert not ride.auto_paused
    assert ride.total.timer_s == 70 + AUTO_PAUSE_DELAY_S


def test_vitesse_inconnue_ne_declenche_pas_l_auto_pause():
    ride = started_ride()
    t = feed(ride, 0, 10, speed_mps=8)
    feed(ride, t, 10)  # plus de vitesse (GPS perdu dans un tunnel)
    assert not ride.auto_paused
    assert ride.total.timer_s == 20
    assert ride.total.distance_m == pytest.approx(80)


def test_tours():
    ride = started_ride()
    t = feed(ride, 0, 100, speed_mps=10)
    done = ride.lap()
    assert done.number == 1
    assert done.distance_m == pytest.approx(1000)

    feed(ride, t, 50, speed_mps=5)
    lap = ride.current_lap
    assert lap.number == 2
    assert lap.timer_s == 50
    assert lap.distance_m == pytest.approx(250)
    assert lap.avg_speed_mps == pytest.approx(5)
    assert ride.total.distance_m == pytest.approx(1250)


def test_lap_ignore_avant_start():
    ride = Ride()
    assert ride.lap() is None
    assert len(ride.laps) == 1


def test_debut_des_tours():
    ride = started_ride()
    t = feed(ride, 0, 100, speed_mps=10)
    ride.lap()
    feed(ride, t, 20, speed_mps=10)
    assert [lap.start_t for lap in ride.laps] == [0, 100]
    assert ride.last_t == 120


def test_departs_et_arrets_du_chrono():
    ride = started_ride()                  # départ à t = 0
    t = feed(ride, 0, 30, speed_mps=8)
    ride.start_pause()                     # pause à t = 30
    t = feed(ride, t, 20, speed_mps=0)
    ride.start_pause()                     # reprise à t = 50
    t = feed(ride, t, 10, speed_mps=0)     # arrêté : auto-pause à t = 53
    feed(ride, t, 5, speed_mps=8)          # on repart à t = 61
    assert ride.timer_events == [(0, True), (30, False), (50, True), (53, False), (61, True)]


def test_mesures_enregistrees_avec_la_distance():
    ride = started_ride()
    feed(ride, 0, 10, speed_mps=5)
    assert [record.sample.t for record in ride.records] == list(range(1, 11))
    assert ride.records[-1].distance_m == pytest.approx(50)


def test_cardio_moyenne_et_max():
    ride = started_ride()
    t = feed(ride, 0, 30, speed_mps=10, heart_rate=150)
    feed(ride, t, 30, speed_mps=10, heart_rate=130)
    assert ride.total.heart_rate.mean == pytest.approx(140)
    assert ride.total.heart_rate.max == 150


def test_zones_cardio():
    ride = started_ride(max_hr=200)
    assert [ride.hr_zone(hr) for hr in (100, 120, 150, 170, 185)] == [1, 2, 3, 4, 5]
    t = feed(ride, 0, 20, speed_mps=8, heart_rate=110)
    feed(ride, t, 10, speed_mps=8, heart_rate=185)
    assert ride.hr_zone_s == [20, 0, 0, 0, 10]


def test_denivele_positif_et_negatif():
    ride = started_ride()
    t = feed(ride, 0, 100, speed_mps=5, altitude_m=100, climb_mps=0.2)   # +20 m
    feed(ride, t, 50, speed_mps=10, altitude_m=120, climb_mps=-0.3)      # -15 m
    assert ride.total.ascent_m == pytest.approx(20, abs=2)
    assert ride.total.descent_m == pytest.approx(15, abs=2)


def test_le_bruit_d_altitude_ne_fait_pas_de_denivele():
    climb = Climb()
    for altitude in [100, 101.5, 99.5, 101, 100, 98.5, 100.5] * 20:
        assert climb.add(altitude) == (0, 0)


def test_pente():
    ride = started_ride()
    feed(ride, 0, 30, speed_mps=10, altitude_m=100, climb_mps=0.5)  # 0,5 m tous les 10 m
    assert ride.grade_pct == pytest.approx(5)


def test_pente_gardee_a_l_arret():
    ride = started_ride()
    t = feed(ride, 0, 30, speed_mps=10, altitude_m=100, climb_mps=0.5)
    feed(ride, t, 10, speed_mps=0, altitude_m=115)
    assert ride.grade_pct == pytest.approx(5)


def test_trace_un_point_tous_les_10_m():
    ride = started_ride()
    feed(ride, 0, 60, speed_mps=5, lat=48.7, lon=2.0)  # 300 m
    assert len(ride.track) == 30


def test_trou_dans_les_mesures_est_plafonne():
    ride = started_ride()
    ride.update(Sample(t=1, speed_mps=10))
    ride.update(Sample(t=61, speed_mps=10))  # 60 s sans mesure
    assert ride.total.timer_s == 1 + MAX_GAP_S
    assert ride.elapsed_s == 61  # le temps total, lui, compte tout : c'est l'heure qui passe


def test_valeur_impossible_d_un_capteur_comptee_absente():
    ride = started_ride()
    t = feed(ride, 0, 10, speed_mps=8, heart_rate=140, altitude_m=100, lat=48.7, lon=2.0)
    ride.update(Sample(t=t + 1, speed_mps=math.nan, heart_rate=math.inf, lat=math.nan, lon=2.0, altitude_m=math.nan,
                       heading_deg=-math.inf))
    now = ride.current
    assert (now.speed_mps, now.heart_rate, now.lat, now.altitude_m, now.heading_deg) == (None, None, None, None, None)
    assert now.lon == 2.0
    assert ride.total.distance_m == pytest.approx(80)  # la mesure illisible n'ajoute pas de distance
    assert ride.total.heart_rate.max == 140
    assert ride.records[-1].sample is now


def test_chaque_entree_signalee_une_fois_comptee():
    """Mesures, Start/Pause et Lap, dans l'ordre : de quoi refaire la sortie (voir journal.py)."""
    ride = Ride()
    entries = []
    ride.on_input = entries.append
    ride.lap()  # avant le départ, Lap ne fait rien : rien n'est signalé
    ride.update(Sample(t=0))
    ride.start_pause()
    ride.update(Sample(t=1, speed_mps=5, heart_rate=math.nan))
    ride.lap()
    assert [entry[0] for entry in entries] == ["u", "p", "u", "l"]
    assert entries[2][1].heart_rate is None  # la mesure signalée est celle qui a compté
