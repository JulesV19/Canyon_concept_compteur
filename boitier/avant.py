"""Boîtier avant du compteur, d'une pièce avec son bras, et son capot.

Le bras se visse sous le cockpit Canyon CP0018 (2 inserts M4, 44 mm d'entraxe avant-arrière)
et porte le boîtier devant le cintre. Le câble qui vient de la batterie passe dans le bras.
Dedans : écran, Pi, GPS (sous le nez, antenne vers le ciel), Pololu, 2 boutons dessous.
Le capot tient la vitre par son bord ; 4 vis M2,5 par-dessous le serrent sur le boîtier,
une lèvre au joint le guide et arrête la pluie.

Visserie, toute en M2,5 :
- capot : 4 vis CHC M2,5 × 14 par-dessous, dans des inserts à chaud (Ø 3,6 × 4) du capot ;
- Pi : 4 vis fraisées M2,5 × 8 par-dessous, écrou sur le Pi (à poser avant d'enficher l'écran) ;
- GPS : 4 vis M2,5 × 6 par-dessus, dans des inserts à chaud des colonnes ;
- Pololu : adhésif double face mousse, calé dans son cadre.

Deux repères :
- vélo : X à droite, Y vers l'avant, Z vers le haut ; origine sur l'insert M4 avant,
  à la face d'appui (le dessous du cockpit) ;
- coque : même axes ; origine au milieu du bord arrière de la vitre, sur la vitre (voir composants.py).

Modules : cotes.py (dimensions), formes.py, coque.py, bras.py ; composants.py (pièces du
commerce), rendu.py (images).

Lancer : .venv/bin/python avant.py  → sortie/*.step, *.stl et rendus/*.png
"""

from build123d import Pos, export_step, export_stl, Compound
import composants as C
from cotes import (BOUTONS, CINTRE_AVANT, CINTRE_H, EMPILEMENT, FOND, POLOLU_XY, SEMELLE_ARRIERE, W, Y_EXT, Y_GPS,
                   Z_BAS, Z_FOND, Z_GPS_ANTENNE, Z_HAUT, Z_NEZ, Z_VITRE)
from coque import capuchon, coque, trous_du_dessous, volume_interieur
from bras import bras, canal, vers_velo


def construire():
    boite, capot = coque()
    corps = vers_velo(boite) + (bras() - vers_velo(volume_interieur()))
    for morceau in canal() + [vers_velo(t) for t in trous_du_dessous()]:
        corps -= morceau
    capot = vers_velo(capot)
    pieces = {
        "ecran": C.ecran(),
        "pi": C.pi(EMPILEMENT),
        "barrettes": C.barrettes(EMPILEMENT),
        "gps": C.gps(Y_GPS, Z_GPS_ANTENNE),
        "pololu": C.pololu(*POLOLU_XY, Z_FOND),
        "boutons": Compound([C.bouton(x, y, Z_NEZ + FOND + 0.8) for x, y in BOUTONS]),
        "capuchons": Compound([capuchon(x, y) for x, y in BOUTONS]),
    }
    pieces = {k: vers_velo(v) for k, v in pieces.items()}
    return corps, capot, pieces


if __name__ == "__main__":
    import time
    t = time.time()
    corps, capot, pieces = construire()
    print(f"construit en {time.time() - t:.1f} s")
    print(f"boîtier : {W:.1f} × {Y_EXT[1] - Y_EXT[0]:.1f} × {Z_HAUT - Z_BAS:.1f} mm (nez : {Z_HAUT - Z_NEZ:.1f} mm)")
    from pathlib import Path
    sortie = Path(__file__).parent / "sortie"
    sortie.mkdir(exist_ok=True)
    for nom, p in (("avant_corps", corps), ("avant_capot", capot)):
        export_step(p, sortie / f"{nom}.step")
        export_stl(p, sortie / f"{nom}.stl", tolerance=0.02, angular_tolerance=0.1)
        print(nom, f"{p.volume / 1000:.1f} cm³", "valide" if p.is_valid else "INVALIDE")
    import rendu
    x0, x1, y0, y1 = C.ECRAN_ACTIF
    image = [tuple(vers_velo(Pos(x, y, Z_VITRE)).position) for x, y in ((x0, y0), (x1, y0), (x0, y1))]
    rendu.rendre(corps, capot, pieces, image, (CINTRE_AVANT, CINTRE_H, SEMELLE_ARRIERE))
