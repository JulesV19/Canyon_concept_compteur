"""Le bras du boîtier avant, sous le cockpit, et le passage du câble (repère vélo)."""

from build123d import Box, Cylinder, Plane, Polygon, Pos, Rot, Spline, Circle, extrude, loft
from cotes import (BIAIS, BRAS, CABLE_D, CABLE_X, ENTRAXE, HAUTEUR, PLAN_JOINT, RECUL, SEMELLE_ARRIERE, TETE_D, TETE_H,
                   VIS_D, W, Y_DROIT, Y_EXT, Z_BAS)


# --- Bras (repère vélo) ---
def y_dos():
    """Dos du boîtier (repère vélo)."""
    return RECUL


def chemin(x=0.0):
    """Ligne du câble : au milieu du bras, sous le cockpit, puis remontée jusque dans le boîtier."""
    import math
    h, yd = BRAS[1], y_dos()
    z_joint = HAUTEUR + (PLAN_JOINT - Z_BAS)
    pts = [(x, SEMELLE_ARRIERE, -h / 2), (x, (SEMELLE_ARRIERE + Y_DROIT) / 2, -h / 2)]
    for i in range(0, 11):                      # milieu de la remontée, même courbe en cosinus que le bras
        t = i / 10
        e = (1 - math.cos(math.pi * t)) / 2
        pts.append((x, Y_DROIT + t * (yd - Y_DROIT), (-h + e * (HAUTEUR + h) + e * z_joint) / 2))
    pts.append((x, yd + 5, pts[-1][2]))
    return Spline(*pts, tangents=[(0, 1, 0), (0, 1, 0)])


def section(w, z0, z1, c_haut, c_bas, y):
    """Section du bras dans le plan XZ à l'ordonnée y : rectangle aux coins coupés (8 sommets)."""
    h = w / 2
    pts = [(-h + c_bas, z0), (h - c_bas, z0), (h, z0 + c_bas), (h, z1 - c_haut),
           (h - c_haut, z1), (-h + c_haut, z1), (-h, z1 - c_haut), (-h, z0 + c_bas)]
    return Plane(origin=(0, y, 0), x_dir=(1, 0, 0), z_dir=(0, 1, 0)) * Polygon(*[(x, -z) for x, z in pts[::-1]], align=None)


def bras():
    """Le bras et la base du boîtier ne font qu'un : plaqué sous le cockpit, il s'élargit et remonte
    jusqu'à la pleine section du boîtier ; son dessus finit sur le joint du capot."""
    a, h, yd = SEMELLE_ARRIERE, BRAS[1], y_dos()
    z_joint = HAUTEUR + (PLAN_JOINT - Z_BAS)        # joint du capot, repère vélo
    arm = lambda y: section(BRAS[0], -h, 0, 2.5, 2.5, y)
    plein = lambda y: section(W, HAUTEUR, z_joint, 0.4, BIAIS, y)
    import math
    semelle = extrude(arm(a), amount=Y_DROIT - a)
    r = BRAS[0] / 2
    bout_rond = Pos(0, a + r, 0) * Cylinder(r, 60) + Pos(0, (a + r + Y_DROIT) / 2, 0) * Box(BRAS[0] + 2, Y_DROIT - a - r, 60)
    semelle &= bout_rond
    # remontée : largeur, hauteurs et biseaux suivent une même courbe en cosinus, sans dépassement
    # sections serrées reliées en ligne droite : elles suivent la courbe sans l'arrondir ni la dépasser
    sections = []
    for i in range(0, 25):
        t = i / 24
        e = (1 - math.cos(math.pi * t)) / 2
        m = lambda u, v: u + (v - u) * e
        sections.append(section(m(BRAS[0], W), m(-h, HAUTEUR), m(0, z_joint), m(2.5, 0.4), m(2.5, BIAIS),
                                Y_DROIT + t * (yd - Y_DROIT)))
    sections.append(plein(yd + 10))
    evase = loft(sections, ruled=True)
    b = semelle + evase
    # vis M4, têtes noyées par-dessous ; la vis arrière dans une lumière de ±3 mm
    for y, lumiere in ((0, 0), (-ENTRAXE, 3)):
        for d, hh, z in ((VIS_D, 30, -15), (TETE_D, TETE_H, -h + TETE_H / 2 - 0.01)):
            if lumiere:
                b -= Pos(0, y, z) * Box(d, lumiere * 2, hh)
                for dy in (-lumiere, lumiere):
                    b -= Pos(0, y + dy, z) * Cylinder(d / 2, hh)
            else:
                b -= Pos(0, y, z) * Cylinder(d / 2, hh)
    return b


def canal():
    """Canal du câble, en trois morceaux à retirer un par un (leur fusion perd le balayage)."""
    trajet = chemin(CABLE_X)
    fin = trajet @ 1
    cercles = [Plane(origin=trajet @ (i / 40), x_dir=(1, 0, 0), z_dir=trajet % (i / 40)) * Circle(CABLE_D / 2)
               for i in range(41)]
    return [loft(cercles, ruled=True),
            Pos(CABLE_X, SEMELLE_ARRIERE - 5, -BRAS[1] / 2) * Rot(X=90) * Cylinder(CABLE_D / 2, 12),  # sortie arrière
            Pos(CABLE_X, fin.Y, fin.Z + 3) * Cylinder(CABLE_D / 2, 7)]                               # entrée dans la coque


def vers_velo(shape):
    """Repère coque → repère vélo."""
    return Pos(0, RECUL - Y_EXT[0], HAUTEUR - Z_BAS) * shape
