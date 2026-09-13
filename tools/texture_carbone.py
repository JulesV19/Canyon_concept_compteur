"""Trame carbone des panneaux : compteur/ui/textures/carbone.png.

Sergé 2/2, comme le carbone tissé d'un cadre : du blanc presque transparent, posé en mosaïque sur les panneaux.
Lancer : python tools/texture_carbone.py
"""

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "compteur" / "ui" / "textures" / "carbone.png"
CELL = 6          # largeur d'une mèche, en pixels
SIZE = 4 * CELL   # le motif se répète toutes les 4 mèches
MAX_ALPHA = 17    # opacité du reflet au milieu d'une mèche (sur 255)


def alpha(x: int, y: int) -> int:
    """Chaque mèche brille en son milieu, dans le sens de ses fibres ; le motif se décale d'une mèche à chaque rang."""
    horizontal = (x // CELL + y // CELL) % 4 < 2
    u = (y % CELL if horizontal else x % CELL) + 0.5
    light = math.sin(math.pi * u / CELL)
    return round(MAX_ALPHA * light * (1.0 if horizontal else 0.6))


def chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))


def main() -> None:
    rows = b"".join(b"\x00" + b"".join(bytes((255, 255, 255, alpha(x, y))) for x in range(SIZE))
                    for y in range(SIZE))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows, 9))
           + chunk(b"IEND", b""))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(png)
    print(f"{OUT} ({SIZE} × {SIZE} px)")


if __name__ == "__main__":
    main()
