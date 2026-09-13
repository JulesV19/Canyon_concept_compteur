import json
from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtCore import QPointF

from compteur.ride import Ride, Sample
from compteur.route import Point, Route
from compteur.session import HistoryModel, SessionModel, route_card
from compteur.summary import ride_summary

START = datetime(2026, 9, 11, 15, 12, tzinfo=timezone(timedelta(hours=2)))


def boucle(name: str) -> Route:
    return Route(name, [Point(48.70, 2.00, 100), Point(48.71, 2.00, 130), Point(48.71, 2.01, 120)])


def une_minute() -> Ride:
    """Une minute vers le nord à 8 m/s."""
    ride = Ride()
    ride.update(Sample(t=0, lat=48.70, lon=2.00, altitude_m=100))
    ride.start_pause()
    for t in range(1, 61):
        ride.update(Sample(t=t, speed_mps=8.0, heart_rate=140, lat=48.70 + t * 7e-5, lon=2.00, altitude_m=100))
    return ride


def test_carte_de_parcours():
    route = boucle("Boucle")
    card = route_card(route)
    assert card["name"] == "Boucle"
    assert card["distanceKm"] == route.length_m / 1000
    assert card["ascentM"] == route.ascent_m
    assert card["outline"][0] == pytest.approx((0.0, 1.0))  # départ en bas à gauche
    assert card["profile"][-1][0] == pytest.approx(route.length_m / 1000)


def test_depart_fin_et_resume():
    routes = [boucle("A"), boucle("B")]
    started, saves, discarded = [], [], []
    summary = {"name": "B", "outline": [(0.0, 1.0), (1.0, 0.0)], "profile": [(0.0, 100.0)], "laps": []}
    session = SessionModel(routes, started.append, lambda: summary, saves.append, lambda: discarded.append(True),
                           lambda: None)
    assert [card["name"] for card in session.routes] == ["A", "B"]

    session.start(1)
    session.start(-1)  # sortie libre
    session.finish()
    assert started == [routes[1], None]
    assert session.summary["name"] == "B"
    assert session.summary["outline"][0] == QPointF(0.0, 1.0)  # des points, pour dessiner le tracé

    session.discard()
    assert discarded == [True]


def test_enregistrement_sans_faire_attendre_l_ecran():
    """Enregistrer rend la main tout de suite ; la suite arrive quand la sortie est écrite, ou refusée."""
    saves, discarded, events = [], [], []
    session = SessionModel([], lambda route: None, lambda: {}, saves.append, lambda: discarded.append(True),
                           lambda: None)
    session.saved.connect(lambda: events.append("saved"))
    session.save()
    assert session.saving
    session.save()      # déjà en cours : ignoré
    session.discard()   # rien ne se supprime pendant l'écriture
    assert len(saves) == 1 and discarded == []

    saves[0]("carte SD pleine")  # refusée : la sortie reste là, avec la raison
    assert not session.saving and session.saveError == "carte SD pleine" and events == []
    session.save()      # on réessaie
    assert session.saveError == ""
    saves[1](None)
    assert not session.saving and events == ["saved"]


def test_arret_refuse():
    refusals = []
    answers = iter(["le système refuse l'arrêt", None])
    session = SessionModel([], lambda route: None, lambda: {}, lambda done: None, lambda: None,
                           lambda: next(answers))
    session.powerOffFailed.connect(refusals.append)
    session.powerOff()
    session.powerOff()  # accepté : rien à signaler, l'appli se ferme
    assert refusals == ["le système refuse l'arrêt"]


def test_historique(tmp_path):
    history = HistoryModel(tmp_path)
    assert history.rides == []
    for name, start in (("Vexin", START), ("Sortie libre", START + timedelta(days=1))):
        ride = une_minute()
        history.add(ride, ride_summary(ride, name, start), start)

    # La plus récente d'abord, avec ce que montre la liste
    assert [ride["name"] for ride in history.rides] == ["Sortie libre", "Vexin"]
    vexin = history.rides[1]
    assert vexin["id"] == "2026-09-11_15-12-00"
    assert vexin["dateText"] == "Vendredi 11 septembre · 15:12"
    assert vexin["distanceKm"] == pytest.approx(0.48)
    assert vexin["timerS"] == 60
    assert 2 <= len(vexin["outline"]) <= 48
    assert isinstance(vexin["outline"][0], QPointF)

    # Rouvrir : le résumé complet, prêt à dessiner ; puis le supprimer
    history.open(1)
    assert history.opened["name"] == "Vexin"
    assert isinstance(history.opened["profile"][0], QPointF)
    history.removeOpened()
    assert [ride["name"] for ride in history.rides] == ["Sortie libre"]
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "2026-09-12_15-12-00.fit", "2026-09-12_15-12-00.json"]


def test_resume_mal_forme_ignore(tmp_path):
    """Un résumé modifié à la main, lisible mais mal formé, ne doit ni empêcher de démarrer, ni cacher les autres."""
    (tmp_path / "2026-09-01_10-00-00.json").write_text(json.dumps({"name": "Abîmée", "outline": "abc"}))
    (tmp_path / "2026-09-02_10-00-00.json").write_text(json.dumps({"name": "Abîmée", "outline": [[1]]}))
    (tmp_path / "2026-09-03_10-00-00.json").write_text(json.dumps({"name": "Profil abîmé", "profile": [[1]]}))
    history = HistoryModel(tmp_path)
    ride = une_minute()
    history.add(ride, ride_summary(ride, "Vexin", START), START)
    assert [ride["name"] for ride in history.rides] == ["Vexin", "Profil abîmé"]
    history.open(1)  # profil illisible : la sortie ne s'ouvre pas, sans erreur
    assert history.opened == {}
    history.open(0)
    assert history.opened["name"] == "Vexin"
