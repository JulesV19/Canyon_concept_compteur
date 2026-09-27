"""Dessine le fond d'écran de la page CarPlay (compteur/ui/carplay/fond.png), une création du projet et non d'Apple :
clair et lumineux comme ceux de CarPlay 26, des voiles de couleur très doux, et deux rubans de « verre » qui suivent
l'oblique du logo Canyon. Une image fixe : le Pi la décode une fois, au lieu de dessiner des dégradés.

    .venv/bin/python tools/carplay/fond.py
"""

import random
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient)

OUT = Path(__file__).resolve().parent.parent.parent / "compteur" / "ui" / "carplay" / "fond.png"
WIDTH, HEIGHT = 480, 640  # l'écran du compteur, en portrait


def blob(painter: QPainter, x: float, y: float, radius: float, color: str, alpha: float) -> None:
    gradient = QRadialGradient(QPointF(x, y), radius)
    center = QColor(color)
    center.setAlphaF(alpha)
    edge = QColor(color)
    edge.setAlphaF(0)
    gradient.setColorAt(0, center)
    gradient.setColorAt(0.55, QColor(center.red(), center.green(), center.blue(), round(alpha * 255 * 0.45)))
    gradient.setColorAt(1, edge)
    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QPointF(x, y), radius, radius)


def curve(y0: float, rise: float) -> QPainterPath:
    """Bord d'une vague qui monte de gauche à droite, à la pente de l'oblique du logo."""
    path = QPainterPath(QPointF(-60, y0))
    path.cubicTo(QPointF(WIDTH * 0.35, y0 - 0.2 * rise), QPointF(WIDTH * 0.55, y0 - 0.9 * rise),
                 QPointF(WIDTH + 60, y0 - rise))
    return path


def band(y0: float, rise: float, thickness: float) -> QPainterPath:
    """Ruban entre deux bords, plus épais à gauche : une vague de verre."""
    top = curve(y0, rise)
    bottom = curve(y0 + thickness, rise * 0.8).toReversed()
    path = QPainterPath(top)
    path.connectPath(bottom)
    path.closeSubpath()
    return path


def blurred(image: QImage, levels: int) -> QImage:
    """Flou doux par pyramide : réduire de moitié `levels` fois, puis agrandir de même, en lissant à chaque pas."""
    smooth = Qt.TransformationMode.SmoothTransformation
    sizes = []
    for _ in range(levels):
        sizes.append(image.size())
        image = image.scaled(image.width() // 2, image.height() // 2, Qt.AspectRatioMode.IgnoreAspectRatio, smooth)
    for size in reversed(sizes):
        image = image.scaled(size, Qt.AspectRatioMode.IgnoreAspectRatio, smooth)
    return image


def main() -> None:
    QGuiApplication(sys.argv[:1])
    image = QImage(WIDTH, HEIGHT, QImage.Format.Format_RGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    base = QLinearGradient(0, 0, 0, HEIGHT)
    base.setColorAt(0, QColor("#DCE7F7"))
    base.setColorAt(0.5, QColor("#EAEDF6"))
    base.setColorAt(1, QColor("#F3EAEA"))
    painter.fillRect(image.rect(), base)

    # Voiles : un ciel bleu en haut, du lilas à droite, une lueur pêche en bas
    blob(painter, 30, 40, 380, "#7FAEFF", 0.55)
    blob(painter, 480, 330, 300, "#B7A2FF", 0.40)
    blob(painter, 40, 640, 330, "#FFB894", 0.45)
    blob(painter, 430, 640, 250, "#8FD8FF", 0.35)

    # Vagues de verre : dessinées nettes, puis floutées ; leur liseré de lumière reste net
    layer = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32_Premultiplied)
    layer.fill(Qt.GlobalColor.transparent)
    glass = QPainter(layer)
    glass.setRenderHint(QPainter.RenderHint.Antialiasing)
    glass.setPen(Qt.PenStyle.NoPen)
    waves = ((600, 330, 150, "#5E8DF5", 0.55), (500, 260, 90, "#FFFFFF", 0.85), (440, 230, 46, "#C9B8FF", 0.6))
    for y0, rise, thickness, color, alpha in waves:
        fill = QLinearGradient(0, y0 - rise, 0, y0 + thickness)
        top = QColor(color)
        top.setAlphaF(alpha)
        bottom = QColor(color)
        bottom.setAlphaF(alpha * 0.25)
        fill.setColorAt(0, top)
        fill.setColorAt(1, bottom)
        glass.setBrush(QBrush(fill))
        glass.drawPath(band(y0, rise, thickness))
    glass.end()
    painter.drawImage(0, 0, blurred(layer, 3))
    for y0, rise, _, _, alpha in waves[1:]:
        light = QColor("#FFFFFF")
        light.setAlphaF(0.7)
        painter.setPen(QPen(light, 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(curve(y0, rise))
    painter.end()

    # Grain très léger : pas de bandes dans les dégradés
    rng = random.Random(7)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if rng.random() < 0.5:
                color = QColor(image.pixel(x, y))
                d = rng.choice((-1, 1))
                image.setPixel(x, y, QColor(min(255, max(0, color.red() + d)), min(255, max(0, color.green() + d)),
                                            min(255, max(0, color.blue() + d))).rgb())
    image.save(str(OUT))
    print(f"Fond : {OUT.name}")


if __name__ == "__main__":
    main()
