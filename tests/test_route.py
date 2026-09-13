import math

import pytest

from compteur.route import Point, Route

STEP = 0.001  # ~111 m de latitude


def north(count: int, lat: float = 48.7) -> list[Point]:
    return [Point(lat + i * STEP, 2.0, 100 + i) for i in range(count)]


def test_longueur_et_denivele():
    route = Route("test", north(11))
    assert route.length_m == pytest.approx(1112, rel=0.01)
    assert route.ascent_m == pytest.approx(10)


def test_position_le_long_du_trace():
    route = Route("test", north(11))
    # 500 m après le départ, 20 m à l'est du tracé
    position = route.locate(48.7 + 4.5 * STEP, 2.0 + 20 / 73_500)
    assert position.along_m == pytest.approx(500, rel=0.01)
    assert position.offset_m == pytest.approx(20, rel=0.05)


def test_aller_retour_ne_confond_pas_les_deux_passages():
    out = north(11)
    route = Route("aller-retour", out + out[-2::-1])
    for i in range(11):  # aller
        route.locate(out[i].lat, out[i].lon)
    for i in range(9, -1, -1):  # retour
        position = route.locate(out[i].lat + STEP / 10, out[i].lon)
    # Revenu à 11 m du départ : presque tout le parcours est fait
    assert position.along_m == pytest.approx(route.length_m - 11, abs=1)


def test_point_cap_et_pente():
    route = Route("test", north(11))
    point = route.point_at(route.length_m / 2)
    assert point.lat == pytest.approx(48.705)
    assert point.ele == pytest.approx(105)
    assert route.heading_at(300) == pytest.approx(0, abs=0.1)  # plein nord
    assert route.grade_at(300) == pytest.approx(0.9, rel=0.05)  # 1 m tous les 111 m


def test_lecture_gpx(tmp_path):
    gpx = tmp_path / "boucle.gpx"
    gpx.write_text(
        '<?xml version="1.0"?>'
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">'
        "<trk><name>Ma boucle</name><trkseg>"
        '<trkpt lat="48.70" lon="2.00"><ele>100</ele></trkpt>'
        '<trkpt lat="48.71" lon="2.00"><ele>130</ele></trkpt>'
        '<trkpt lat="48.72" lon="2.00"><ele>110</ele></trkpt>'
        "</trkseg></trk></gpx>",
        encoding="utf-8",
    )
    route = Route.load(gpx)
    assert route.name == "Ma boucle"
    assert len(route.points) == 3
    assert route.length_m == pytest.approx(2224, rel=0.01)
    assert route.ascent_m == pytest.approx(30)
    assert len(route.profile(50)) == 50


def test_nom_par_defaut_et_itineraire(tmp_path):
    gpx = tmp_path / "sortie-du-dimanche.gpx"
    gpx.write_text(
        '<gpx><rte><rtept lat="48.7" lon="2.0"/><rtept lat="48.8" lon="2.0"/></rte></gpx>',
        encoding="utf-8",
    )
    route = Route.load(gpx)
    assert route.name == "sortie-du-dimanche"
    assert route.profile() == []  # pas d'altitude dans le fichier


def test_trace_miniature_entre_0_et_1():
    outline = Route("Nord", north(11)).outline(21)
    assert len(outline) == 21
    assert outline[0] == pytest.approx((0.0, 1.0))  # départ en bas : le nord est en haut
    assert outline[-1] == pytest.approx((0.0, 0.0))
    assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in outline)


def test_nouvelle_sortie_sur_une_boucle_repart_du_debut():
    carre = [Point(48.70, 2.000), Point(48.71, 2.000), Point(48.71, 2.015), Point(48.70, 2.015), Point(48.70, 2.000)]
    route = Route("Carré", carre)
    for point in carre:
        position = route.locate(point.lat, point.lon)
    assert position.along_m == pytest.approx(route.length_m)  # arrivé : l'arrivée est au départ
    route.rewind()
    assert route.locate(48.70, 2.000).along_m == pytest.approx(0)


def test_denivele_restant():
    # 100 → 130 → 120 → 150 : 30 m de montée, une descente, puis encore 30 m
    route = Route("Bosses", [Point(48.70 + i * STEP, 2.0, ele) for i, ele in enumerate((100, 130, 120, 150))])
    assert route.ascent_m == pytest.approx(60)
    assert route.ascent_after(0) == pytest.approx(60)
    assert route.ascent_after(route.cumulative[1]) == pytest.approx(30)
    assert route.ascent_after(route.cumulative[1] + 10) == pytest.approx(30)
    assert route.ascent_after(route.length_m) == pytest.approx(0)


def test_parcours_de_longueur_nulle_refuse():
    """Tous les points au même endroit : la distance faite se diviserait par zéro."""
    with pytest.raises(ValueError, match="longueur nulle"):
        Route("Sur place", [Point(48.7, 2.0, 100)] * 3)


@pytest.mark.parametrize("points", [
    [Point(math.nan, 2.0), Point(48.7, 2.0)],
    [Point(48.7, math.inf), Point(48.7, 2.0)],
    [Point(48.7, 2.0), Point(90.0, 2.0)],   # hors de la carte (Web Mercator)
    [Point(48.7, 2.0), Point(48.7, 200.0)],
])
def test_point_hors_de_la_carte_refuse(points):
    with pytest.raises(ValueError):
        Route("Ailleurs", points)


@pytest.mark.parametrize("content", [
    '<gpx><trk><trkseg><trkpt lat="48.7" lon="2.0"/>',                                  # tronqué
    '<gpx><trk><trkseg><trkpt lat="48.7" lon="2.0"/></trkseg></trk></gpx>',             # un seul point
    '<gpx><rte><rtept lon="2.0"/><rtept lat="48.8" lon="2.0"/></rte></gpx>',            # point sans latitude
    '<gpx><rte><rtept lat="48.7" lon="2.0"/><rtept lat="48.7" lon="2.0"/></rte></gpx>',  # longueur nulle
    '<gpx><rte><rtept lat="48.7" lon="2.0"><ele>haut</ele></rtept><rtept lat="48.8" lon="2.0"/></rte></gpx>',
    '<gpx/>',                                                                            # sans trace
])
def test_gpx_inutilisable(tmp_path, content):
    """ValueError, que l'appli sait ignorer au démarrage."""
    gpx = tmp_path / "abime.gpx"
    gpx.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        Route.load(gpx)


def test_altitude_non_finie_comptee_absente(tmp_path):
    gpx = tmp_path / "boucle.gpx"
    gpx.write_text('<gpx><rte><rtept lat="48.7" lon="2.0"><ele>nan</ele></rtept>'
                   '<rtept lat="48.8" lon="2.0"><ele>120</ele></rtept></rte></gpx>', encoding="utf-8")
    route = Route.load(gpx)
    assert route.points[0].ele is None
    assert route.profile() == []
    assert route.path == gpx
