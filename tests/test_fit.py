import math
from datetime import datetime, timedelta, timezone

import pytest
from garmin_fit_sdk import Decoder, Stream

from compteur.fit import FIT_EPOCH, SINT32, UINT8, UINT16, UINT32Z, encode_activity
from compteur.ride import Record, Ride, Sample

START = datetime(2026, 9, 11, 15, 12, tzinfo=timezone(timedelta(hours=2)))
START_FIT = int((START - FIT_EPOCH).total_seconds())


def demo_ride() -> Ride:
    """Deux tours, un arrêt au feu (auto-pause) et une pause manuelle, avec GPS, altitude et cardio."""
    ride = Ride()
    t = 0

    def feed(seconds: int, speed: float) -> None:
        nonlocal t
        for _ in range(seconds):
            t += 1
            ride.update(Sample(t=t, speed_mps=speed, heart_rate=120 + t % 30, lat=48.70 + t * 1e-5,
                               lon=2.00 + t * 1e-5, altitude_m=100 + t * 0.1))

    ride.update(Sample(t=0, lat=48.70, lon=2.00, altitude_m=100))
    ride.start_pause()
    feed(120, 8.0)
    ride.lap()
    feed(30, 0.0)   # feu rouge : auto-pause à t = 123
    feed(60, 9.0)   # on repart à t = 151
    ride.start_pause()
    feed(20, 0.0)   # en pause à t = 210, fin à t = 230
    return ride


def decode(data: bytes) -> dict:
    """Relit le fichier avec le lecteur officiel de Garmin (dates laissées en secondes FIT)."""
    assert Decoder(Stream.from_byte_array(bytearray(data))).check_integrity()
    messages, errors = Decoder(Stream.from_byte_array(bytearray(data))).read(convert_datetimes_to_dates=False)
    assert errors == []
    return messages


def test_mesures():
    ride = demo_ride()
    records = decode(encode_activity(ride, START))["record_mesgs"]
    assert len(records) == len(ride.records)
    first, last = ride.records[0], ride.records[-1]
    assert records[0]["timestamp"] == START_FIT + 1
    assert records[0]["position_lat"] * 180 / 2**31 == pytest.approx(first.sample.lat, abs=1e-6)
    assert records[0]["position_long"] * 180 / 2**31 == pytest.approx(first.sample.lon, abs=1e-6)
    assert records[0]["altitude"] == pytest.approx(first.sample.altitude_m, abs=0.2)
    assert records[0]["heart_rate"] == first.sample.heart_rate
    assert records[0]["speed"] == pytest.approx(8.0)
    assert records[-1]["distance"] == pytest.approx(last.distance_m, abs=0.01)


def test_chrono_tours_et_seance():
    ride = demo_ride()
    messages = decode(encode_activity(ride, START))

    events = [(e["timestamp"] - START_FIT, e["event"], e["event_type"]) for e in messages["event_mesgs"]]
    assert events == [(0, "timer", "start"), (123, "timer", "stop_all"),
                      (151, "timer", "start"), (210, "timer", "stop_all")]

    laps = messages["lap_mesgs"]
    assert len(laps) == 2
    assert [lap["start_time"] - START_FIT for lap in laps] == [0, 120]
    assert laps[1]["timestamp"] == START_FIT + 230
    assert laps[0]["total_timer_time"] == pytest.approx(ride.laps[0].timer_s)
    assert laps[1]["total_distance"] == pytest.approx(ride.laps[1].distance_m, abs=0.01)

    session = messages["session_mesgs"][0]
    assert session["sport"] == "cycling"
    assert session["sub_sport"] == "road"
    assert session["total_elapsed_time"] == pytest.approx(230)
    assert session["total_timer_time"] == pytest.approx(ride.total.timer_s)
    assert session["total_distance"] == pytest.approx(ride.total.distance_m, abs=0.01)
    assert session["num_laps"] == 2
    assert session["max_heart_rate"] == ride.total.heart_rate.max
    assert messages["activity_mesgs"][0]["num_sessions"] == 1
    assert messages["file_id_mesgs"][0]["type"] == "activity"


def test_plage_de_chaque_type():
    assert UINT8.valid(254) and not UINT8.valid(255) and not UINT8.valid(-1)  # 255 : « absente »
    assert UINT16.valid(65534) and not UINT16.valid(70000)
    assert SINT32.valid(-2**31) and not SINT32.valid(2**31 - 1) and not SINT32.valid(2**31)
    assert not UINT32Z.valid(0)


def short_ride(**aberrant) -> Ride:
    """Dix secondes vers le nord ; à t = 5, les valeurs données (pic GPS, défaut d'un capteur)."""
    ride = Ride()
    ride.update(Sample(t=0, lat=48.70, lon=2.00, altitude_m=100))
    ride.start_pause()
    for t in range(1, 11):
        values = {"speed_mps": 8.0, "heart_rate": 140, "lat": 48.70 + t * 1e-4, "lon": 2.00, "altitude_m": 100.0}
        ride.update(Sample(t=t, **(values | aberrant if t == 5 else values)))
    return ride


@pytest.mark.parametrize("aberrant, field", [
    ({"speed_mps": 70.0}, "speed"),          # pic GPS : 252 km/h, au-delà de ce que le champ sait écrire
    ({"altitude_m": -600.0}, "altitude"),    # GPS pas encore calé
    ({"heart_rate": 300}, "heart_rate"),     # défaut de la ceinture
    ({"lon": 180.0}, "position_long"),       # 2^31 semicercles : un de trop
])
def test_valeur_aberrante_ecrite_absente(aberrant, field):
    """Une seule valeur aberrante ne doit pas empêcher d'enregistrer la sortie : elle est écrite « absente »."""
    records = decode(encode_activity(short_ride(**aberrant), START))["record_mesgs"]
    assert len(records) == 10
    assert field not in records[4]
    assert field in records[3] and field in records[5]


def test_maximums_aberrants_des_tours_et_de_la_seance():
    messages = decode(encode_activity(short_ride(speed_mps=70.0, heart_rate=300), START))
    for summary in messages["lap_mesgs"] + messages["session_mesgs"]:
        assert "max_speed" not in summary and "max_heart_rate" not in summary
        assert summary["avg_speed"] > 8  # les moyennes restent dans leur plage : elles sont écrites


def test_nombres_non_finis_ecrits_absents():
    """Le moteur écarte déjà les valeurs non finies ; le fichier FIT ne leur fait pas confiance pour autant."""
    ride = short_ride()
    record = ride.records[4]
    ride.records[4] = Record(Sample(t=record.sample.t, speed_mps=math.inf, heart_rate=math.nan, lat=math.nan,
                                    lon=2.0, altitude_m=math.nan), math.nan)
    records = decode(encode_activity(ride, START))["record_mesgs"]
    assert not {"speed", "heart_rate", "position_lat", "altitude", "distance"} & records[4].keys()
    assert records[4]["position_long"] * 180 / 2**31 == pytest.approx(2.0)


def test_temps_total_identique_a_l_ecran_et_dans_le_fichier():
    """Dix minutes sans mesure en pause (une coupure, par exemple) comptent dans le temps total, partout."""
    ride = short_ride()
    ride.start_pause()
    ride.update(Sample(t=610, lat=48.70, lon=2.00))
    ride.start_pause()
    for t in range(611, 621):
        ride.update(Sample(t=t, speed_mps=8.0, lat=48.70 + t * 1e-4, lon=2.00))
    session = decode(encode_activity(ride, START))["session_mesgs"][0]
    assert ride.elapsed_s == 620
    assert session["total_elapsed_time"] == pytest.approx(ride.elapsed_s)
