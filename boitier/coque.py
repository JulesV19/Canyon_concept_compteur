"""La coque du boîtier avant et son capot, dans le repère de la coque (voir avant.py)."""

from build123d import Axis, Box, Cylinder, Plane, Pos, Rot, extrude, chamfer, Compound, Cone, offset
import composants as C
from cotes import (BIAIS, BOUTONS, COUPE_ARRIERE, COUPE_AVANT, DESSUS, EMPILEMENT, FOND, INSERT, JEU, JEU_LEVRE, LEVRE,
                   OBLIQUE, PLAN_JOINT, POLOLU_XY, PROUE, PROUE_Y, VIS_CAPOT, W, W_INT, Y_EXT, Y_GPS, Y_INT, Z_BAS,
                   Z_FOND, Z_GPS_CARTE, Z_HAUT, Z_NEZ, Z_VITRE, z_proue)
from formes import bloc, plan, prisme_yz


def proue(abaisse=0.0):
    """Ce que le nez perd au-dessus : il plonge de PROUE mm entre la vitre et la pointe."""
    y0, y1 = PROUE_Y, Y_EXT[1] + 1
    z1 = Z_HAUT - PROUE * (y1 - y0) / (Y_EXT[1] - y0)
    return prisme_yz([(y0 - 50, Z_HAUT + 10), (y0 - 50, Z_HAUT - abaisse), (y0, Z_HAUT - abaisse),
                      (y1, z1 - abaisse), (y1, Z_HAUT + 10)]) & Pos(0, y0, 0) * Box(300, 2 * (y1 - y0 + 60), 300)


def talon():
    """Arrière du capot coupé à 45° : il prolonge la remontée du bras."""
    y0 = Y_EXT[0]
    return prisme_yz([(y0 - 5, PLAN_JOINT - 5), (y0 - 5, Z_HAUT + 5), (y0 + (Z_HAUT + 5 - PLAN_JOINT), Z_HAUT + 5)])


def aretes_du_dessus(v):
    """Arêtes entre le dessus plongeant du nez et les flancs."""
    dessus = [f for f in v.faces() if 0.5 < f.normal_at().Z < 0.999]
    flancs = [f for f in v.faces() if abs(f.normal_at().Z) < 0.3]
    cles = lambda f: {tuple(round(c, 4) for c in e.center()) for e in f.edges()}
    d = set().union(*(cles(f) for f in dessus))
    fl = set().union(*(cles(f) for f in flancs))
    return [e for e in v.edges() if tuple(round(c, 4) for c in e.center()) in d & fl]


def volume_exterieur():
    v = bloc(plan(W, *Y_EXT, COUPE_ARRIERE, COUPE_AVANT), Z_BAS, Z_HAUT, BIAIS)
    v = chamfer(v.edges().group_by(Axis.Z)[-1], 1.0)
    v -= proue()
    v -= talon()
    try:
        v = chamfer(aretes_du_dessus(v), 0.8)
    except ValueError:
        print("chanfrein du nez impossible")
    return v


def volume_interieur():
    v = bloc(plan(W_INT, *Y_INT, COUPE_ARRIERE - 1, COUPE_AVANT - 1, 0.8), Z_FOND, Z_VITRE + 0.01, BIAIS - 1.5)
    return v - proue(DESSUS + 0.3) - Pos(0, 2.2, 0) * talon()   # parois de 1,5 mm sous le biseau


def rainure():
    """Ombre de 0,8 × 0,6 mm au plan de joint, tout autour."""
    tranche = lambda w, y0, y1, c_ar, c_av: extrude(Plane.XY.offset(PLAN_JOINT - 0.4) * plan(w, y0, y1, c_ar, c_av), 0.8)
    return tranche(W + 2, Y_EXT[0] - 1, Y_EXT[1] + 1, COUPE_ARRIERE, COUPE_AVANT) - \
        tranche(W - 1.2, Y_EXT[0] + 0.6, Y_EXT[1] - 0.6, COUPE_ARRIERE - 0.25, COUPE_AVANT - 0.25)


def obliques():
    """L'oblique du logo, gravée deux fois sur le nez (0,4 mm)."""
    y = (PROUE_Y + Y_EXT[1]) / 2 + 2
    traits = [Pos(dx, y, 0) * Rot(Z=-OBLIQUE) * Box(1.4, 11, 100) for dx in (-2.2, 2.2)]
    return (traits[0] + traits[1]) & proue(0.4)


def colonnes(r, z0, z1):
    return Compound([Pos(x, y, (z0 + z1) / 2) * Cylinder(r, z1 - z0) for x, y in VIS_CAPOT])


def capuchon(x, y):
    """Capuchon imprimé (TPU) : dépasse de 0,8 mm sous le nez, collerette à l'intérieur."""
    tige = Pos(x, y, Z_NEZ - 0.8 + (FOND + 0.8) / 2) * Cylinder(3.9, FOND + 0.8)
    tige = chamfer(tige.edges().group_by(Axis.Z)[0], 0.5)
    return tige + Pos(x, y, Z_NEZ + FOND + 0.4) * Cylinder(5.5, 0.8)


def levre(jeu=0.0):
    """Lèvre du boîtier, dans la moitié intérieure de la paroi ; avec jeu, sa rainure dans le capot.
    Elle s'efface sous le talon, là où le capot est trop mince pour la recevoir."""
    dedans = plan(W_INT, *Y_INT, COUPE_ARRIERE - 1, COUPE_AVANT - 1, 0.8)
    anneau = offset(dedans, LEVRE[0] + jeu) - dedans
    l = extrude(Plane.XY.offset(PLAN_JOINT - 0.01) * anneau, LEVRE[1] + jeu + 0.01)
    return l - Pos(0, 1.6 - jeu, 0) * talon()


def trous_du_dessous():
    """Ce qui traverse le dessous : percé après l'ajout du bras, qui le reboucherait."""
    t = []
    for x, y in VIS_CAPOT:
        t += [Pos(x, y, (Z_BAS + PLAN_JOINT) / 2) * Cylinder(1.4, PLAN_JOINT - Z_BAS + 1),    # passage M2,5
              Pos(x, y, Z_BAS + 1.3) * Cylinder(2.6, 2.7)]                                     # tête noyée
    for x, y, z in C.pi_trous(EMPILEMENT):
        t += [Pos(x, y, (Z_BAS + z) / 2) * Cylinder(1.4, z - Z_BAS + 1),                      # vis traversante
              Pos(x, y, Z_BAS + 0.55) * Cone(2.7, 1.4, 1.3)]                                   # tête fraisée
    # saignée sous la barrette du Pi : ses picots soudés dépassent d'environ 1,5 mm
    t.append(Pos(C.BARRETTE_X, C.BARRETTE_Y, Z_FOND - 0.5) * Box(6, 51.6, 1.02))
    return t


def coque():
    """Boîtier (sans le bras) et capot, dans le repère coque."""
    ext = volume_exterieur()
    boite = ext - volume_interieur()
    # colonnes des vis du capot, du fond au plan de joint (percées dans trous_du_dessous)
    for x, y in VIS_CAPOT:
        boite += ext & Pos(x, y, (Z_BAS + PLAN_JOINT) / 2) * Cylinder(3.2, PLAN_JOINT - Z_BAS)
    # entretoises du Pi (percées dans trous_du_dessous)
    for x, y, z in C.pi_trous(EMPILEMENT):
        boite += Pos(x, y, (Z_FOND + z) / 2) * Cylinder(2.8, z - Z_FOND + 0.01)
    # colonnes du GPS sous ses 4 coins, inserts par-dessus
    for x, y in C.gps_trous(Y_GPS):
        boite += ext & Pos(x, y, (Z_BAS + Z_GPS_CARTE) / 2) * Cylinder(3.2, Z_GPS_CARTE - Z_BAS)
        boite -= Pos(x, y, Z_GPS_CARTE - INSERT[1] / 2) * Cylinder(INSERT[0] / 2, INSERT[1] + 0.01)
    # cadre du Pololu : le cale sur son adhésif
    px, py = POLOLU_XY
    lx, ly = C.POLOLU[0] + 0.6, C.POLOLU[1] + 0.6
    cadre = Box(lx + 1.6, ly + 1.6, 1.2) - Box(lx, ly, 1.2)
    boite += ext & Pos(px + C.POLOLU[0] / 2, py + C.POLOLU[1] / 2, Z_FOND + 0.6) * cadre
    # appuis de l'écran côté gauche (le Pi occupe le côté droit)
    for y in (4, C.ECRAN[1] - 4):
        x = -W_INT / 2 + 3
        boite += Pos(x, y, (Z_FOND + -C.ECRAN_BLOC) / 2) * Box(5, 5, -C.ECRAN_BLOC - Z_FOND)
    # boutons : trou du capuchon dans le fond du nez
    for x, y in BOUTONS:
        boite -= Pos(x, y, Z_NEZ + FOND / 2) * Cylinder(4.2, FOND + 1)

    capot = ext & (Pos(0, 0, (PLAN_JOINT + 10) / 2 + 0.0) * Box(300, 300, 10 - PLAN_JOINT))
    capot -= volume_interieur() & Pos(0, 0, PLAN_JOINT - 50) * Box(300, 300, 100)
    # logement de la vitre
    capot -= Pos(0, JEU + C.ECRAN[1] / 2, (PLAN_JOINT + Z_VITRE) / 2) * Box(C.ECRAN[0] + 2 * JEU, C.ECRAN[1] + 2 * JEU,
                                                                         Z_VITRE - PLAN_JOINT)
    # fenêtre : zone affichée, bords en biais
    x0, x1, y0, y1 = C.ECRAN_ACTIF
    fen = Pos((x0 + x1) / 2, (y0 + y1) / 2, Z_VITRE) * Box(x1 - x0 + 0.6, y1 - y0 + 0.6, 2 * DESSUS + 0.2)
    fen = chamfer(fen.edges().group_by(Axis.Z)[-1], DESSUS * 0.9)
    capot -= fen
    # bossages des inserts M2,5 (laiton, à chaud) sous le capot
    for x, y in VIS_CAPOT:
        z_haut = z_proue(y) - DESSUS
        capot += ext & Pos(x, y, (PLAN_JOINT + z_haut) / 2) * Cylinder(3.2, z_haut - PLAN_JOINT)
        profondeur = min(INSERT[1], z_haut - PLAN_JOINT - 0.6)
        capot -= Pos(x, y, PLAN_JOINT + profondeur / 2) * Cylinder(INSERT[0] / 2, profondeur + 0.01)
    boite -= Pos(0, 0, PLAN_JOINT + 50) * Box(300, 300, 100)
    boite += levre()
    capot -= levre(JEU_LEVRE)
    boite -= rainure()
    capot -= rainure()
    capot -= obliques()
    return boite, capot
