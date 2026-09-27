"""Strava pour l'écran : temps affichés, moment de la synchro, modèle QML."""

import queue

import pytest

from compteur import strava
from compteur.strava import StravaModel, parse_time, synced_text
from strava_fake import connect, favorite, publish


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
    monkeypatch.setattr(strava.client, "API_URL", fake.url + "/api/v3")
    monkeypatch.setattr(strava.client, "TOKEN_URL", fake.url + "/oauth/token")
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
