"""Composants du boîtier avant, placés dans le repère local de la coque.

Repère local : X vers la droite du cycliste, Y vers l'avant, Z vers le haut ;
X = 0 au milieu, Y = 0 au bord arrière de la vitre, Z = 0 sur la vitre.

Les modèles viennent des fabricants (voir modeles/telecharger.sh) ; les boutons C&K,
sans modèle libre, sont dessinés d'après leur fiche.
"""

from pathlib import Path

from build123d import Box, Compound, Cylinder, Pos, Rot, import_step

BRUT = Path(__file__).parent / "modeles" / "brut"

# Écran Waveshare 2,8" DPI : bloc vitre + dalle + carte de 66,4 × 48 × 7,6 mm dans le modèle.
ECRAN = (48.0, 66.4)            # vitre, en portrait (X, Y)
ECRAN_BLOC = 7.6                # vitre → dos de la carte
ECRAN_ACTIF = (-21.6, 21.6, 2.1, 59.7)   # zone affichée (x min, x max, y min, y max), plan Waveshare
BARRETTE_X = 20.0               # axe de la barrette 2 × 20, sous le bord droit de l'écran
BARRETTE_Y = 32.65              # milieu de la barrette

PI = (30.0, 65.0, 1.6)
GPS = (25.4, 25.4)
GPS_HAUT = 7.97                 # du dessous de la carte au dessus de l'antenne
GPS_BAS = 4.04                  # support de pile, sous la carte
POLOLU = (15.24, 17.78, 2.97)
BOUTON = (6.2, 6.2, 3.5)        # C&K KSC241J


def ecran():
    """Vitre en haut, carte en bas, nappe à l'avant, barrette à droite."""
    s = import_step(BRUT / "ecran28dpi.step")
    s = Rot(Z=90) * (Rot(X=-90) * s)
    return Pos(0, 33.2, -3.73) * s


def pi(empilement):
    """Pi Zero 2 W, composants vers le haut, barrette sous celle de l'écran.
    empilement : du dos de la carte de l'écran au dessus de la carte du Pi."""
    s = import_step(BRUT / "pizero2w.step")
    s = Rot(Z=-90) * (Rot(X=90) * s)
    z_dessus = -ECRAN_BLOC - empilement
    return Pos(BARRETTE_X - 11.5, BARRETTE_Y, z_dessus - 0.8) * s


def pi_trous(empilement):
    """Centres des 4 trous M2,5 du Pi (entraxe 58 × 23), et le dessous de sa carte."""
    z = -ECRAN_BLOC - empilement - PI[2]
    return [(x, BARRETTE_Y + y, z) for x in (BARRETTE_X - 23, BARRETTE_X) for y in (-29, 29)]


def barrettes(empilement):
    """Barrette femelle de l'écran et mâle du Pi, en un bloc."""
    return Pos(BARRETTE_X, BARRETTE_Y, -ECRAN_BLOC - empilement / 2) * Box(5.1, 50.8, empilement)


def gps(y0, z_antenne):
    """GPS PA1010D, antenne vers le ciel ; y0 = son bord arrière, z_antenne = dessus de l'antenne."""
    s = import_step(BRUT / "gps_pa1010d.step")
    return Pos(-GPS[0] / 2, y0, z_antenne - GPS_HAUT) * s


def gps_trous(y0):
    """Centres (x, y) des 4 trous M2,5 du GPS, dans ses coins (entraxe 20,32 × 20,32)."""
    return [(-GPS[0] / 2 + a, y0 + b) for a in (2.54, 22.86) for b in (2.54, 22.86)]


def pololu(x0, y0, z0):
    return Pos(x0, y0, z0) * import_step(BRUT / "pololu2808.step")


def bouton(x, y, z_face):
    """Bouton C&K KSC241J retourné (poussoir vers le bas) sur sa plaquette de 7 × 10 ;
    z_face = bout du poussoir."""
    corps = Pos(x, y, z_face + 0.6 + BOUTON[2] / 2) * Box(*BOUTON)
    poussoir = Pos(x, y, z_face + 0.6 / 2) * Cylinder(1.6, 0.6)
    plaquette = Pos(x, y, z_face + 0.6 + BOUTON[2] + 0.8) * Box(7, 10, 1.6)
    return Compound([corps, poussoir, plaquette])
