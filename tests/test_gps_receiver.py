"""Le GPS lu par son fil : branché en route, réglage renvoyé, barres, mesures de la sortie, heure."""

import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from compteur import gps
from compteur.gps import OUTPUT, QUERY_FIRMWARE, STALE_S, NmeaReader, Receiver
from nmea_samples import FakeBus, GGA, RMC, sentence


def test_gps_branche_apres_le_demarrage(monkeypatch):
    """Sans GPS au démarrage, le fil le cherche toutes les 10 s ; trouvé, il le lit. L'état dit s'il répond, et quand
    la première position est arrivée."""
    now = [0.0]
    bus = FakeBus(f"{RMC}\r\n{GGA}\r\n")
    found = [None]
    searches = []

    def find():
        searches.append(now[0])
        return found[0]

    receiver = Receiver(clock=lambda: now[0], find=find)
    for t in (0.0, 5.0):
        now[0] = t
        assert not receiver._search()
    found[0] = bus
    now[0] = 10.0
    assert receiver._search()
    assert searches == [0.0, 10.0]  # une recherche toutes les 10 s, pas plus
    assert not receiver.status().present
    monkeypatch.setattr(receiver._stop, "wait", lambda _: receiver._stop.set())  # s'arrête au premier temps mort
    receiver._run()
    status = receiver.status()
    assert status.present and status.fix.valid and status.first_fix_s == 10.0
    now[0] += STALE_S + 1
    assert not receiver.status().present  # plus rien depuis 3 s


def test_message_non_voulu_le_reglage_est_a_renvoyer():
    reader = NmeaReader()
    reader.feed((sentence("GNVTG,0.00,T,,M,0.00,N,0.00,K,N") + "\r\n").encode())
    assert reader.unwanted


def test_le_fil_regle_le_gps_puis_lit_la_position(monkeypatch):
    now = [0.0]
    bus = FakeBus(f"{RMC}\r\n{GGA}\r\n" * 3)
    receiver = Receiver(bus, clock=lambda: now[0])
    monkeypatch.setattr(receiver._stop, "wait", lambda _: receiver._stop.set())  # s'arrête au premier temps mort
    receiver._run()
    assert bus.written == [OUTPUT, QUERY_FIRMWARE]  # la version n'est redemandée que 10 s plus tard
    assert receiver.fix().valid and receiver.fix().altitude_m == 545.4
    assert receiver.take_lines()[:2] == [RMC, GGA]
    now[0] = STALE_S + 1
    assert not receiver.fix().valid  # plus rien depuis 3 s


def test_barres_de_reception():
    assert gps.bars(gps.Status(gps.Fix(), present=False)) == 0            # rien reçu
    assert gps.bars(gps.Status(gps.Fix(), present=True)) == 0             # reçu, mais pas un satellite en vue
    assert gps.bars(gps.Status(gps.Fix(in_view=6), present=True)) == 1    # il cherche
    found = gps.Fix(valid=True, in_view=9, satellites=6, fix_type=3)
    assert gps.bars(gps.Status(found, present=True)) == 2                 # position sans dispersion connue
    assert gps.bars(gps.Status(replace(found, hdop=7.0), present=True)) == 2
    assert gps.bars(gps.Status(replace(found, hdop=3.0), present=True)) == 3
    assert gps.bars(gps.Status(replace(found, hdop=0.9), present=True)) == 4
    assert gps.bars(gps.Status(replace(found, hdop=0.9, fix_type=2), present=True)) == 2  # 2D : pas d'altitude


def test_les_mesures_de_la_sortie_viennent_du_gps(monkeypatch):
    now = [0.0]
    bus = FakeBus(f"{RMC}\r\n{GGA}\r\n")
    receiver = Receiver(bus, clock=lambda: now[0])
    rider = gps.GpsRider(receiver)

    empty = rider.sample(1.0)  # rien lu : aucune mesure inventée
    assert empty.t == 1.0 and empty.speed_mps is None and empty.lat is None
    assert rider.device_status(1.0) == {"gpsBars": 0, "gpsFix": False, "hrConnected": False}

    monkeypatch.setattr(receiver._stop, "wait", lambda _: receiver._stop.set())  # une seule passe
    receiver._run()
    sample = rider.sample(2.0)
    assert sample.lat == pytest.approx(48.1173) and sample.lon == pytest.approx(11.516667)
    assert sample.speed_mps == pytest.approx(22.4 * gps.KNOT_MPS) and sample.altitude_m == 545.4
    assert sample.heading_deg == pytest.approx(84.4)
    assert sample.heart_rate is None  # pas de ceinture branchée
    status = rider.device_status(2.0)
    assert status["gpsFix"] and status["gpsBars"] == 4 and not status["hrConnected"]  # HDOP 0,9

    now[0] = STALE_S + 1  # le GPS s'est tu : les mesures s'arrêtent, rien n'est figé à l'écran
    assert rider.sample(3.0).speed_mps is None
    assert rider.device_status(3.0) == {"gpsBars": 0, "gpsFix": False, "hrConnected": False}


def test_ecart_d_horloge():
    """Horloge du système en avance d'une minute. Écart retenu sur 10 lignes : le plus grand, la ligne lue 3 s en retard
    ne compte pas ; chaque ligne une seule fois ; rien sans position."""
    check = gps.ClockCheck()
    t0 = datetime(2026, 9, 27, 18, 0, 0, tzinfo=timezone.utc)
    lags = [3.0, 0.4, 0.2, 0.3, 0.5, 0.2, 0.3, 0.4, 0.2, 0.3]  # retard de lecture de chaque ligne, en s
    results = []
    for i, lag in enumerate(lags):
        fix = gps.Fix(valid=True, utc=t0 + timedelta(seconds=i), received=100.0 + i + lag)
        system = t0 + timedelta(seconds=60 + i + lag)
        results.append(check.offset(fix, 100.0 + i + lag, system))
        assert check.offset(fix, 100.5 + i + lag, system) is None  # même ligne : déjà comptée
    assert results[:9] == [None] * 9
    assert abs(results[9] - (-60.2)) < 1e-6
    fix = gps.Fix(valid=False, utc=t0 + timedelta(seconds=20), received=120.0)
    assert check.offset(fix, 120.0, t0) is None and check.samples == []


def test_horloge_mise_a_l_heure(monkeypatch):
    """Horloge du système en retard d'une heure : elle prend l'heure du GPS, et le départ de la sortie suit ; à moins
    de 2 s près, on n'y touche pas ; si le système refuse, on ne réessaie plus."""
    from types import SimpleNamespace
    from compteur.app import Compteur
    from compteur.ride import State

    set_to = []
    monkeypatch.setattr(time, "clock_settime", lambda clock, value: set_to.append(value))
    started = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
    offsets = iter([None, 3600.0, 0.5, 3600.0])
    app = SimpleNamespace(gps=SimpleNamespace(fix=lambda: None, clock=lambda: 0.0), clock_denied=False,
                          clock_check=SimpleNamespace(offset=lambda fix, now, system: next(offsets)),
                          model=SimpleNamespace(ride=SimpleNamespace(state=State.RUNNING)), started_at=started)
    Compteur.sync_clock(app)
    assert set_to == []  # pas encore d'estimation
    Compteur.sync_clock(app)
    assert abs(set_to[0] - (time.time() + 3600)) < 1
    assert (app.started_at - started).total_seconds() == 3600
    Compteur.sync_clock(app)
    assert len(set_to) == 1  # déjà à l'heure

    def refuse(clock, value):
        raise PermissionError("Operation not permitted")
    monkeypatch.setattr(time, "clock_settime", refuse)
    Compteur.sync_clock(app)
    assert app.clock_denied
