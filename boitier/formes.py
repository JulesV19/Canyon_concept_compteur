"""Formes de base du boîtier : contour aux coins coupés, prisme, bloc à la base rabattue."""

from build123d import Plane, Polygon, extrude, fillet


def plan(w, y0, y1, c_ar, c_av, r=1.6):
    """Contour en plan aux coins coupés (l'oblique du logo), arêtes adoucies."""
    h = w / 2
    arriere = [(-h + c_ar, y0), (h - c_ar, y0), (h, y0 + c_ar)] if c_ar > 0 else [(-h, y0), (h, y0)]
    avant = [(h, y1 - c_av), (h - c_av, y1), (-h + c_av, y1), (-h, y1 - c_av)]
    p = Polygon(*arriere, *avant, *([(-h, y0 + c_ar)] if c_ar > 0 else []), align=None)
    return fillet(p.vertices(), r)


def prisme_yz(points, largeur=200):
    """Prisme extrudé suivant X à partir d'un profil (y, z)."""
    return extrude(Plane.YZ * Polygon(*points, align=None), amount=largeur / 2, both=True)


def bloc(contour, z0, z1, biais):
    """Bloc droit de z0 à z1, dont la base est rabattue à 45° sur la hauteur « biais »."""
    haut = extrude(Plane.XY.offset(z0 + biais) * contour, z1 - z0 - biais)
    bas = extrude(Plane.XY.offset(z0 + biais) * contour, amount=-biais, taper=45)
    return haut + bas
