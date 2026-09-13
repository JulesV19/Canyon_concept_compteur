import errno
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from compteur import history
from compteur.ride import Ride, Sample
from compteur.summary import date_text, ride_summary

START = datetime(2026, 9, 11, 15, 12, tzinfo=timezone(timedelta(hours=2)))


def two_laps() -> Ride:
    """5 minutes vers le nord à 8 m/s, en montée, avec un tour à t = 200, puis Lap juste avant la fin."""
    ride = Ride(max_hr=200)
    ride.update(Sample(t=0, lat=48.70, lon=2.00, altitude_m=100))
    ride.start_pause()
    for t in range(1, 301):
        if t == 200:
            ride.lap()
        ride.update(Sample(t=t, speed_mps=8.0, heart_rate=130 if t <= 100 else 165,
                           lat=48.70 + t * 1e-4, lon=2.00, altitude_m=100 + t * 0.2))
    ride.lap()
    return ride


def test_date_en_francais():
    assert date_text(START) == "Vendredi 11 septembre · 15:12"


def test_resume_de_sortie():
    summary = ride_summary(two_laps(), "Sortie libre", START)
    assert summary["name"] == "Sortie libre"
    assert summary["dateText"] == "Vendredi 11 septembre · 15:12"
    assert summary["distanceKm"] == pytest.approx(2.4)
    assert summary["timerS"] == 300
    assert summary["maxSpeedKmh"] == pytest.approx(28.8)
    assert summary["maxHeartRate"] == 165
    assert summary["hrZonesS"] == [0, 100, 0, 200, 0]  # 130 bpm : zone 2 ; 165 bpm : zone 4 (FC max 200)
    assert summary["outline"][0] == pytest.approx((0.0, 1.0))  # départ en bas : on roule vers le nord
    assert summary["profile"][-1][1] == pytest.approx(160, abs=2)
    # Le tour vide de la fin n'est pas montré
    assert [(lap["number"], lap["timerS"]) for lap in summary["laps"]] == [(1, 199), (2, 101)]
    assert summary["laps"][1]["distanceKm"] == pytest.approx(0.808)


def test_enregistrement(tmp_path):
    ride = two_laps()
    fit_path = history.save(ride, ride_summary(ride, "Sortie libre", START), START, tmp_path)
    assert fit_path == tmp_path / "2026-09-11_15-12-00.fit"
    assert fit_path.read_bytes()[8:12] == b".FIT"
    saved = json.loads((tmp_path / "2026-09-11_15-12-00.json").read_text(encoding="utf-8"))
    assert saved["name"] == "Sortie libre"
    assert saved["file"] == "2026-09-11_15-12-00.fit"
    assert not list(tmp_path.glob("*.tmp"))


def test_gps_fige_pas_de_trace_mais_un_resume():
    """Positions toutes identiques : le tracé ne se dessine pas, mais la sortie se termine et s'enregistre."""
    ride = Ride()
    ride.update(Sample(t=0, lat=48.70, lon=2.00))
    ride.start_pause()
    for t in range(1, 61):
        ride.update(Sample(t=t, speed_mps=8.0, lat=48.70, lon=2.00))
    summary = ride_summary(ride, "Sortie libre", START)
    assert summary["outline"] == []
    assert summary["distanceKm"] == pytest.approx(0.48)


def test_carte_pleine_pendant_l_enregistrement(tmp_path, monkeypatch):
    """Le résumé ne s'écrit pas : l'erreur remonte, sans fichier temporaire, et la sortie ne passe pas pour
    enregistrée."""
    ride = two_laps()
    real_fsync = os.fsync
    calls = []

    def fsync(descriptor):
        calls.append(descriptor)
        if len(calls) == 3:  # le fichier FIT, son dossier, puis le résumé : carte pleine
            raise OSError(errno.ENOSPC, "No space left on device")
        real_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", fsync)
    summary = ride_summary(ride, "Sortie libre", START)
    with pytest.raises(OSError):
        history.save(ride, summary, START, tmp_path)
    assert [path.name for path in tmp_path.iterdir()] == ["2026-09-11_15-12-00.fit"]
    assert history.find_saved(summary, tmp_path) is None
    history.remove_orphans(START, tmp_path)  # Supprimer : le fichier FIT resté seul part aussi
    assert list(tmp_path.iterdir()) == []


def test_jamais_une_sortie_ecrasee(tmp_path):
    """Deux sorties parties à la même seconde (horloge qui a reculé, sans réseau) : la seconde ne remplace pas la
    première."""
    first = two_laps()
    history.save(first, ride_summary(first, "Vexin", START), START, tmp_path)
    second = Ride()
    second.update(Sample(t=0, lat=48.70, lon=2.00))
    second.start_pause()
    for t in range(1, 61):
        second.update(Sample(t=t, speed_mps=5.0, lat=48.70 + t * 1e-4, lon=2.00))
    path = history.save(second, ride_summary(second, "Sortie libre", START), START, tmp_path)
    assert path.name == "2026-09-11_15-12-00-2.fit"
    assert sorted(ride["name"] for ride in history.load(tmp_path)) == ["Sortie libre", "Vexin"]


def test_sortie_deja_enregistree_reconnue(tmp_path):
    """Au contenu, pas seulement à la seconde du départ."""
    ride = two_laps()
    summary = ride_summary(ride, "Sortie libre", START)
    assert history.find_saved(summary, tmp_path) is None
    history.save(ride, summary, START, tmp_path)
    assert history.find_saved(summary, tmp_path) == "2026-09-11_15-12-00"
    assert history.find_saved(ride_summary(Ride(), "Autre", START), tmp_path) is None  # même seconde, autre sortie
