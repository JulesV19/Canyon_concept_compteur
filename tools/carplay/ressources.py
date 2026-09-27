"""Prépare, sur le Mac, les ressources Apple de la page CarPlay : la police SF Pro et les icônes de Musique, Téléphone,
Messages et WhatsApp. Les icônes sont celles d'iOS, prises sur l'App Store (celles des applis du Mac en secours, sans
réseau). Leur licence interdit de les distribuer : elles vont dans compteur/ui/carplay/apple/, hors du
dépôt (.gitignore), et partent sur le Pi avec tools/pi/envoyer.sh. Sans elles, la page CarPlay se replie sur Barlow et
des icônes dessinées.

    .venv/bin/python tools/carplay/ressources.py

SF Pro est une police variable de 7,8 Mo (/System/Library/Fonts/SFNS.ttf) : on n'en garde que quatre graisses fixes,
bien plus légères à charger sur le Pi. Il faut fontTools (requirements-dev.txt).
"""

import json
import math
import subprocess
import urllib.request
import sys
import tempfile
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QPainterPath

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "compteur" / "ui" / "carplay" / "apple"
SF = Path("/System/Library/Fonts/SFNS.ttf")
# (fichier, famille, graisse, taille optique) : « Text » pour les petits corps, « Display » pour les titres, comme iOS
# (opsz 17 et 28). Une famille par graisse : sur le Mac, Qt voit toutes ces graisses à 400 et prend l'une pour l'autre
FONTS = [
    ("SFProText-Regular.ttf", "SF Pro Text", 400, 17),
    ("SFProText-Semibold.ttf", "SF Pro Text Semibold", 590, 17),
    ("SFProDisplay-Semibold.ttf", "SF Pro Display Semibold", 590, 28),
    ("SFProDisplay-Bold.ttf", "SF Pro Display Bold", 700, 28),
]
# Applis sur l'App Store : leur icône y est celle de la dernière version d'iOS
APP_STORE = {"musique": 1108187390, "telephone": 1146562108, "messages": 1146560473, "whatsapp": 310633997}
ICONS = {
    "musique": "/System/Applications/Music.app/Contents/Resources/AppIcon.icns",
    "telephone": "/System/Applications/Phone.app/Contents/Resources/AppIcon.icns",
    "messages": "/System/Applications/Messages.app/Contents/Resources/AppIcon.icns",
    "whatsapp": "/Applications/WhatsApp.app/Contents/Resources/AppIcon.icns",
}
ICON_PX = 240    # 60 pt en @2x, doublé pour les captures à l'échelle 2
SQUIRCLE_N = 5   # superellipse |x|^n + |y|^n = 1 : très proche des coins continus d'iOS


def make_font(name: str, family: str, weight: int, optical: int) -> None:
    font = TTFont(SF)
    instantiateVariableFont(font, {"wght": weight, "opsz": optical, "wdth": 100, "GRAD": 400}, inplace=True)
    names = font["name"]
    for record in list(names.names):
        if record.nameID in (1, 2, 4, 6, 16, 17):
            names.removeNames(nameID=record.nameID)
    for name_id, value in ((1, family), (2, "Regular"), (4, family), (6, family.replace(" ", ""))):
        names.setName(value, name_id, 3, 1, 0x409)
        names.setName(value, name_id, 1, 0, 0)
    font["OS/2"].usWeightClass = weight
    font.save(OUT / name)


def squircle(size: float) -> QPainterPath:
    path = QPainterPath()
    steps = 400
    r = size / 2
    for i in range(steps + 1):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        x = r + r * math.copysign(abs(c) ** (2 / SQUIRCLE_N), c)
        y = r + r * math.copysign(abs(s) ** (2 / SQUIRCLE_N), s)
        path.lineTo(x, y) if i else path.moveTo(x, y)
    return path


def app_store_icon(app_id: int) -> QImage | None:
    """Icône en 1024 px, carrée et pleine (iOS la découpe lui-même) ; None sans réseau."""
    try:
        with urllib.request.urlopen(f"https://itunes.apple.com/lookup?id={app_id}&country=fr", timeout=15) as reply:
            artwork = json.load(reply)["results"][0]["artworkUrl512"]
        with urllib.request.urlopen(artwork.rsplit("/", 1)[0] + "/1024x1024bb.png", timeout=30) as reply:
            image = QImage.fromData(reply.read())
    except (OSError, KeyError, IndexError, ValueError):
        return None
    return None if image.isNull() else image


def save_icon(name: str, source: QImage, crop: QRectF) -> None:
    """Découpée en squircle : les quatre icônes ont la même forme, comme sur CarPlay."""
    icon = QImage(ICON_PX, ICON_PX, QImage.Format.Format_ARGB32_Premultiplied)
    icon.fill(Qt.GlobalColor.transparent)
    painter = QPainter(icon)
    painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
    painter.setClipPath(squircle(ICON_PX))
    painter.drawImage(QRectF(0, 0, ICON_PX, ICON_PX), source, crop)
    painter.end()
    icon.save(str(OUT / f"{name}.png"))


def make_icon(name: str, icns: str) -> None:
    """Icône d'une appli du Mac, en secours : sa plus grande image, recadrée sur son dessin (les icônes du Mac ont une
    marge)."""
    with tempfile.TemporaryDirectory() as folder:
        iconset = Path(folder) / "icon.iconset"
        subprocess.run(["iconutil", "-c", "iconset", icns, "-o", str(iconset)], check=True)
        source = max((QImage(str(p)) for p in iconset.glob("*.png")), key=QImage.width)
    source = source.convertToFormat(QImage.Format.Format_ARGB32)
    opaque = [(x, y) for y in range(0, source.height(), 2) for x in range(0, source.width(), 2)
              if source.pixelColor(x, y).alpha() > 200]
    left, right = min(x for x, _ in opaque), max(x for x, _ in opaque)
    top, bottom = min(y for _, y in opaque), max(y for _, y in opaque)
    side = max(right - left, bottom - top)
    # Un rien à l'intérieur du dessin : le bord des icônes du Mac est ombré
    inset = side * 0.02
    save_icon(name, source, QRectF(left + inset, top + inset, side - 2 * inset, side - 2 * inset))


def main() -> None:
    QGuiApplication(sys.argv[:1])
    OUT.mkdir(parents=True, exist_ok=True)
    for spec in FONTS:
        make_font(*spec)
        print(f"Police : {spec[0]}")
    for name, icns in ICONS.items():
        image = app_store_icon(APP_STORE[name])
        if image is not None:
            save_icon(name, image, QRectF(image.rect()))
            print(f"Icône : {name}.png (App Store)")
        elif Path(icns).exists():
            make_icon(name, icns)
            print(f"Icône : {name}.png (Mac)")
        else:
            print(f"Icône {name} absente ({icns}) : la page CarPlay la dessinera", file=sys.stderr)


if __name__ == "__main__":
    main()
