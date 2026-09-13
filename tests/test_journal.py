import errno
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from compteur import journal
from compteur.journal import FLUSH_EVERY, Header, Journal
from compteur.ride import Ride, Sample, State
from compteur.storage import Writer

START = datetime(2026, 9, 13, 9, 30, 12, tzinfo=timezone(timedelta(hours=2)))
HEADER = Header(START, "vexin.gpx", "Vexin", True, 185.0)


class Direct:
    """Fil d'écriture sans fil : chaque tâche passe tout de suite. Ses erreurs sont gardées, comme le vrai les signale
    sans s'arrêter."""

    def __init__(self):
        self.errors = []

    def submit(self, task, done=None):
        try:
            result, error = task(), None
        except Exception as exc:
            result, error = None, exc
            self.errors.append(exc)
        if done is not None:
            done(result, error)


def sample(t: int) -> Sample:
    """Vers le nord-est à 8 m/s, avec un arrêt au feu de t = 100 à 120 (auto-pause)."""
    return Sample(t=t, speed_mps=0.0 if 100 <= t < 120 else 8.0, heart_rate=120 + t % 40, lat=48.7 + t * 7e-5,
                  lon=2.0 + t * 1e-5, altitude_m=100 + (t % 50) * 0.3, heading_deg=12.5)


def ride_on(recorder: Journal | None, until: int, start: int = 1, ride: Ride | None = None) -> Ride:
    """Départ (sauf sortie donnée), puis une mesure par seconde de `start` à `until` ; Lap à t = 150, pause de t = 200
    à 230."""
    if ride is None:
        ride = Ride(auto_pause=HEADER.auto_pause, max_hr=HEADER.max_hr)
        if recorder is not None:
            recorder.start(HEADER, ride)
        ride.update(Sample(t=0, lat=48.7, lon=2.0, altitude_m=100))
        ride.start_pause()
    for t in range(start, until + 1):
        if t == 150:
            ride.lap()
        if t in (200, 230):
            ride.start_pause()
        ride.update(sample(t))
    return ride


def state(ride: Ride) -> tuple:
    """Tout ce que la sortie a compté."""
    return (ride.state, ride.auto_paused, ride.total, ride.laps, ride.elapsed_s, ride.hr_zone_s, list(ride.hr_history),
            ride.hr_count, ride.track, ride.profile, ride.records, ride.timer_events, ride.grade_pct, ride.current)


def lines(path) -> list[bytes]:
    return path.read_bytes().split(b"\n")[:-1]


def test_la_sortie_rejouee_est_identique(tmp_path):
    path = tmp_path / journal.FILE_NAME
    recorder = Journal(path, Direct())
    ride = ride_on(recorder, 400)
    recorder.flush()
    found = journal.load(path)
    assert found.header == HEADER
    assert not found.finished
    assert found.size == path.stat().st_size
    assert state(found.ride) == state(ride)
    # Tout y est passé : arrêt au feu (auto-pause), tour, pause manuelle
    assert len(ride.laps) == 2 and ride.state is State.RUNNING
    assert [running for _, running in ride.timer_events] == [True, False, True, False, True]


def test_mesures_par_paquets_de_30_le_reste_tout_de_suite(tmp_path):
    path = tmp_path / journal.FILE_NAME
    recorder = Journal(path, Direct())
    ride = ride_on(recorder, 0)  # départ : en-tête, première mesure et Start, écrits aussitôt
    assert len(lines(path)) == 3
    ride_on(recorder, FLUSH_EVERY - 1, ride=ride)
    assert len(lines(path)) == 3  # 29 mesures : encore en mémoire
    ride_on(recorder, FLUSH_EVERY, start=FLUSH_EVERY, ride=ride)
    assert len(lines(path)) == 3 + FLUSH_EVERY
    ride.update(sample(FLUSH_EVERY + 1))
    ride.lap()  # Lap part tout de suite, avec la mesure qui attendait
    assert [json.loads(line)[0] for line in lines(path)[-2:]] == ["u", "l"]


def test_ligne_coupee_par_une_coupure(tmp_path):
    path = tmp_path / journal.FILE_NAME
    recorder = Journal(path, Direct())
    ride = ride_on(recorder, 90)
    recorder.flush()
    whole = path.stat().st_size
    with open(path, "ab") as file:
        file.write(b'["u",91,8.0,1')  # le courant coupe en pleine écriture
    found = journal.load(path)
    assert state(found.ride) == state(ride)
    assert found.size == whole


def test_ligne_illisible_la_sortie_s_arrete_a_la_derniere_ligne_complete(tmp_path):
    path = tmp_path / journal.FILE_NAME
    recorder = Journal(path, Direct())
    ride_on(recorder, 90)
    recorder.flush()
    content = lines(path)
    content[50] = b'["u",48,"illisible"]'  # ligne 50 : la mesure t = 48 (après l'en-tête, t = 0 et Start)
    path.write_bytes(b"\n".join(content) + b"\n")
    found = journal.load(path)
    assert state(found.ride) == state(ride_on(None, 47))  # la suite est ignorée : l'état reste cohérent


@pytest.mark.parametrize("content", [b"", b'{"v": 99}\n', b'["u",1]\n', b"{pas du json\n",
                                     b'{"v":1,"startedAt":"2026-09-13T09:30:12","routeFile":null,"routeName":"x",'
                                     b'"autoPause":true,"maxHr":190}\n'])
def test_en_tete_illisible(tmp_path, content):
    """Rien à reprendre (la dernière : date sans fuseau, inutilisable pour le fichier FIT)."""
    path = tmp_path / journal.FILE_NAME
    path.write_bytes(content)
    with pytest.raises(ValueError):
        journal.load(path)


def test_sans_fichier():
    assert journal.load(journal.Path("/nulle/part/reprise.jsonl")) is None


def test_fin_de_sortie(tmp_path):
    path = tmp_path / journal.FILE_NAME
    recorder = Journal(path, Direct())
    ride = ride_on(recorder, 60)
    ride.start_pause()
    recorder.finish(ride)
    assert ride.on_input is None  # la sortie terminée ne s'écrit plus
    assert json.loads(lines(path)[-1]) == ["f"]
    with open(path, "ab") as file:
        file.write(b'["u",61,8.0,140,48.7,2.0,100.0,0.0]\n')  # rien ne compte après la fin
    found = journal.load(path)
    assert found.finished
    assert state(found.ride) == state(ride)


def test_sortie_reprise_dans_le_meme_fichier(tmp_path):
    """Après une coupure en pleine écriture, la sortie reprend dans le même fichier : la ligne coupée disparaît, et le
    fichier redonne la sortie comme si rien ne s'était passé."""
    path = tmp_path / journal.FILE_NAME
    recorder = Journal(path, Direct())
    ride_on(recorder, 90)
    recorder.flush()
    with open(path, "ab") as file:
        file.write(b'["u",91,8')
    found = journal.load(path)
    again = Journal(path, Direct())
    again.resume(found)
    ride = ride_on(None, 250, start=91, ride=found.ride)
    again.flush()
    assert all(json.loads(line) for line in lines(path))
    assert state(journal.load(path).ride) == state(ride) == state(ride_on(None, 250))


def test_carte_qui_refuse_puis_accepte(tmp_path, monkeypatch):
    """Écriture refusée : la sortie continue, et ce qui n'a pas pu s'écrire repart ensuite, dans l'ordre, sans
    doublon."""
    path = tmp_path / journal.FILE_NAME
    writer = Direct()
    recorder = Journal(path, writer)
    ride = ride_on(recorder, 30)
    real_fsync = os.fsync

    def full(descriptor):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(os, "fsync", full)
    ride_on(recorder, 60, start=31, ride=ride)
    assert [error.errno for error in writer.errors] == [errno.ENOSPC]
    monkeypatch.setattr(os, "fsync", real_fsync)
    ride_on(recorder, 90, start=61, ride=ride)
    assert state(journal.load(path).ride) == state(ride)


def test_nouvelle_sortie_nouveau_fichier(tmp_path):
    path = tmp_path / journal.FILE_NAME
    recorder = Journal(path, Direct())
    ride_on(recorder, 90)
    recorder.flush()
    ride = ride_on(recorder, 10)
    recorder.flush()
    assert state(journal.load(path).ride) == state(ride)


def test_suppression(tmp_path):
    path = tmp_path / journal.FILE_NAME
    recorder = Journal(path, Direct())
    ride_on(recorder, 10)
    recorder.discard()
    assert not path.exists()
    recorder.discard()  # déjà effacé : rien à faire


def test_avec_le_vrai_fil_d_ecriture(tmp_path):
    writer = Writer(lambda call: call())
    recorder = Journal(tmp_path / "sorties" / journal.FILE_NAME, writer)  # dossier créé au besoin
    ride = ride_on(recorder, 400)
    recorder.close()
    assert writer.close()
    assert state(journal.load(recorder.path).ride) == state(ride)
