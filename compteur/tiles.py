"""Carte hors ligne : tuiles images pré-rendues (fichier MBTiles, voir tools/carte), servies à QML."""

import math
import sqlite3
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtQuick import QQuickImageProvider

TILE_PX = 512    # tuiles dessinées en x2, affichées pixel pour pixel
WORLD_ZOOM = 16  # zoom de référence des coordonnées « monde » passées à l'interface
WORLD_PX = TILE_PX * 2**WORLD_ZOOM
MAX_UPSCALE = 6  # sans tuile à ce zoom, on agrandit celle d'un zoom plus faible (jusqu'à 6 crans)
LAND = QColor("#242427")
DEFAULT_CENTER = (48.8566, 2.3522)  # Paris, s'il n'y a pas de carte


def world(lat: float, lon: float) -> tuple[float, float]:
    """Position Web Mercator en pixels au zoom de référence (tuiles de 512 px)."""
    sin = math.sin(math.radians(lat))
    x = (lon + 180) / 360
    y = 0.5 - math.log((1 + sin) / (1 - sin)) / (4 * math.pi)
    return x * WORLD_PX, y * WORLD_PX


class TileProvider(QQuickImageProvider):
    """Répond aux demandes « image://tiles/z/x/y » de la carte."""

    def __init__(self, path: Path):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._lock = threading.Lock()  # les tuiles sont chargées par plusieurs fils en parallèle
        self._db = None
        center = DEFAULT_CENTER
        if path.exists():
            try:
                self._db, center = self._open(path)
            except (sqlite3.Error, ValueError) as error:  # carte abîmée : l'appli démarre sans elle
                print(f"Carte ignorée ({path.name}) : {error}", file=sys.stderr)
        # Origine des coordonnées carte : le centre de la carte, pour garder des nombres petits
        self.origin = world(*center)

    @staticmethod
    def _open(path: Path) -> tuple[sqlite3.Connection, tuple[float, float]]:
        """Ouvre la carte et lit son centre. sqlite3.Error ou ValueError si le fichier n'est pas une carte lisible."""
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        try:
            center = DEFAULT_CENTER
            row = db.execute("SELECT value FROM metadata WHERE name = 'bounds'").fetchone()
            if row:
                west, south, east, north = (float(v) for v in str(row[0]).split(","))
                center = ((south + north) / 2, (west + east) / 2)
            db.execute("SELECT 1 FROM tiles LIMIT 1").fetchone()  # une carte sans tuiles n'en est pas une
            return db, center
        except BaseException:
            db.close()
            raise

    def requestImage(self, id: str, size: QSize, requested_size: QSize) -> QImage:
        z, x, y = (int(v) for v in id.split("/"))
        for up in range(min(MAX_UPSCALE, z) + 1):
            image = self._read(z - up, x >> up, y >> up)
            if image is not None:
                if up:
                    # Morceau de la tuile parente qui couvre la tuile demandée, agrandi
                    part = TILE_PX >> up
                    mask = (1 << up) - 1
                    image = image.copy(QRect((x & mask) * part, (y & mask) * part, part, part)).scaled(
                        TILE_PX, TILE_PX, Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)
                return image
        image = QImage(TILE_PX, TILE_PX, QImage.Format.Format_RGB32)
        image.fill(LAND)
        return image

    def _read(self, z: int, x: int, y: int) -> QImage | None:
        if self._db is None:
            return None
        try:
            with self._lock:
                row = self._db.execute(
                    "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                    (z, x, (1 << z) - 1 - y),  # MBTiles compte les rangées depuis le bas
                ).fetchone()
        except sqlite3.Error:
            return None  # page abîmée du fichier : la tuile manque, comme hors de la carte
        if row is None:
            return None
        image = QImage.fromData(row[0])
        return None if image.isNull() else image
