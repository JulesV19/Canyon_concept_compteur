"""Cotes du boîtier avant : réglages sur le vélo, coque, bras, et hauteurs dans la coque (voir avant.py)."""

import composants as C


# --- À régler sur le vélo (provisoire) ---
# CP0018 (étiquette) : potence 110 mm ; l'insert avant est à la jonction potence-cintre.
CINTRE_AVANT = 40   # bord avant du cintre, devant l'insert avant (estimé d'après photo)
CINTRE_H = 30       # dessus du cintre, au-dessus du dessous du cockpit (estimé)
MARGE = 40          # entre le bord avant du cintre et le dos du boîtier
RECUL = CINTRE_AVANT + MARGE   # de l'insert avant au dos du boîtier
HAUTEUR = 6         # du dessous du cockpit au dessous du boîtier

# --- Empilement : vitre → dos du Pi = 16 mm, mesuré écran et Pi enfichés ---
EMPILEMENT = 16.0 - 7.6 - 1.6   # du dos de la carte de l'écran au dessus de la carte du Pi

# --- Coque ---
PAROI = 2.2
FOND = 1.8
DESSUS = 1.2        # capot au-dessus de la vitre
JEU = 0.3
ARRIERE = 9.0       # place derrière la vitre : colonnes des vis arrière, arrivée du câble ;
                    # assez pour que le talon à 45° couvre l'insert d'au moins 1,5 mm
ECART_GPS = 2.0
COUPE_ARRIERE = 0   # l'arrière se fond dans le bras : pas de coins coupés
COUPE_AVANT = 11
PLAN_JOINT = -7.0   # entre capot et boîtier (repère coque), juste au-dessus du dos de l'écran
BIAIS = 3.5         # tour du dessous rabattu à 45°
PROUE = 5.0         # le nez plonge de 5 mm vers la pointe, comme la proue du cintre
OBLIQUE = 20        # angle de l'oblique du logo, en degrés
LEVRE = (0.8, 1.5)  # lèvre du boîtier au joint (épaisseur, hauteur), dans la paroi
JEU_LEVRE = 0.15
INSERT = (3.6, 4.6) # trou d'un insert M2,5 à chaud (diamètre, profondeur)

# --- Bras ---
ENTRAXE = 44
BRAS = (26, 10)     # section (largeur, hauteur)
SEMELLE_ARRIERE = -ENTRAXE - 12
Y_DROIT = CINTRE_AVANT + 2          # le bras reste plaqué sous le cockpit jusqu'au-delà du cintre
CABLE_D = 5.5       # câble M8 surmoulé : environ 5 mm
CABLE_X = 8.5       # à côté des vis
VIS_D, TETE_D, TETE_H = 4.5, 7.8, 4.2

# --- Hauteurs dans la coque ---
Z_VITRE = 0.0
Z_PI_DESSOUS = -C.ECRAN_BLOC - EMPILEMENT - C.PI[2]
Z_FOND = Z_PI_DESSOUS - 1.5                     # dessus du fond, sous les entretoises du Pi
Z_BAS = Z_FOND - FOND
Z_HAUT = Z_VITRE + DESSUS
Z_NEZ = Z_BAS                                   # dessous plat : les boutons y logent sous le nez
Y_GPS = C.ECRAN[1] + JEU + ECART_GPS
POLOLU_XY = (-(C.ECRAN[0] + 2 * JEU) / 2 + 1, 10)   # coin arrière gauche du Pololu

W_INT = C.ECRAN[0] + 2 * JEU
Y_INT = (-ARRIERE, Y_GPS + C.GPS[1] + JEU)
W = W_INT + 2 * PAROI
PROUE_Y = C.ECRAN[1] + 2 * JEU + 1.5            # le nez commence à plonger juste après la vitre
Y_EXT = (Y_INT[0] - PAROI, Y_INT[1] + PAROI)


def z_proue(y):
    """Dessus du capot à l'ordonnée y : plonge vers le nez, et à 45° vers le bras à l'arrière."""
    avant = Z_HAUT - PROUE * max(0.0, y - PROUE_Y) / (Y_EXT[1] - PROUE_Y)
    return min(avant, PLAN_JOINT + (y - Y_EXT[0]))


Z_GPS_ANTENNE = z_proue(Y_GPS + 18) - DESSUS - 0.6       # l'antenne sous le dessus plongeant
Z_GPS_CARTE = Z_GPS_ANTENNE - C.GPS_HAUT                  # dessous de la carte du GPS


VIS_CAPOT = [(-W_INT / 2 + 4, -3.3), (W_INT / 2 - 4, -3.3),     # derrière : colonnes à 0,1 mm de la vitre
             (-W_INT / 2 + 3.5, PROUE_Y + 3), (W_INT / 2 - 3.5, PROUE_Y + 3)]  # devant : là où le capot est épais
BOUTONS = [(-16.5, Y_GPS + 11), (16.5, Y_GPS + 11)]  # allumage à gauche, Start/Pause à droite ;
                                                     # plaquettes à côté de la carte du GPS, pas dessous
