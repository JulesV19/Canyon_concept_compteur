import math
import sqlite3

import pytest
from PySide6.QtCore import QSize

from compteur.tiles import DEFAULT_CENTER, LAND, TILE_PX, WORLD_PX, TileProvider, world


def test_origine_du_monde():
    assert world(0, 0) == pytest.approx((WORLD_PX / 2, WORLD_PX / 2))
    assert world(85.05112878, -180) == pytest.approx((0, 0), abs=1)


def test_memes_tuiles_qu_openstreetmap():
    lat, lon = 48.85837, 2.294481  # tour Eiffel
    n = 2**16
    expected = (
        int((lon + 180) / 360 * n),
        int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n),
    )
    x, y = world(lat, lon)
    assert (int(x // TILE_PX), int(y // TILE_PX)) == expected


@pytest.mark.parametrize("content", [b"", b"pas une base SQLite" * 100])
def test_carte_abimee_l_appli_demarre_sans_elle(tmp_path, content, capsys):
    path = tmp_path / "carte.mbtiles"
    path.write_bytes(content)
    provider = TileProvider(path)
    assert provider.origin == world(*DEFAULT_CENTER)
    image = provider.requestImage("12/2074/1409", QSize(), QSize())
    assert image.width() == TILE_PX and image.pixelColor(0, 0) == LAND  # des terres, comme hors de la carte
    assert "Carte ignorée" in capsys.readouterr().err


def test_base_sans_tuiles(tmp_path, capsys):
    path = tmp_path / "carte.mbtiles"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
        db.execute("INSERT INTO metadata VALUES ('bounds', '1.4,48.1,3.5,49.2')")
    TileProvider(path)
    assert "Carte ignorée" in capsys.readouterr().err


def test_tuile_illisible_en_cours_de_route(tmp_path):
    """Une page abîmée du fichier, découverte en roulant : la tuile manque, comme hors de la carte."""
    path = tmp_path / "carte.mbtiles"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
        db.execute("CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)")
    provider = TileProvider(path)
    provider._db = sqlite3.connect(":memory:", check_same_thread=False)  # plus de table tiles
    assert provider.requestImage("12/2074/1409", QSize(), QSize()).pixelColor(0, 0) == LAND
