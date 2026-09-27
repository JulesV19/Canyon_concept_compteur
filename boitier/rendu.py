"""Rendus ombrés des pièces (pyvista, hors écran)."""

import tempfile
from pathlib import Path

import pyvista as pv
from build123d import export_stl

RENDUS = Path(__file__).parent / "rendus"
CAPTURE = Path(__file__).parent.parent / "docs" / "principale.png"
# Noir mat du cockpit Canyon CP0018, relevé sur photo (faces éclairées #37363b, ombre #1e1c1d)
NOIR_COCKPIT = "#26252a"
MATS = ("corps", "capot", "capuchons")
COULEURS = {
    "corps": NOIR_COCKPIT, "capot": NOIR_COCKPIT, "ecran": "#07080a", "pi": "#2f7a44",
    "barrettes": "#141414", "gps": "#2b4f9a", "pololu": "#5a3a8a", "boutons": "#c9ced4",
    "capuchons": NOIR_COCKPIT,
}


def maillage(shape, tol=0.05):
    with tempfile.NamedTemporaryFile(suffix=".stl") as f:
        export_stl(shape, f.name, tolerance=tol, angular_tolerance=0.2)
        return pv.read(f.name)


def scene(maillages, fichier, camera, coupe=None, ecarte=0.0, cockpit=None, taille=(1600, 1100), image=None, zoom=1.4):
    p = pv.Plotter(off_screen=True, window_size=taille)
    p.set_background("#eef0f2", top="#ffffff")
    for nom, m in maillages.items():
        if ecarte and nom == "capot":
            m = m.translate((0, 0, ecarte))
        if coupe is not None:
            m = m.clip(normal="x", origin=(coupe, 0, 0), invert=True)
        mat = nom in MATS
        p.add_mesh(m, color=COULEURS.get(nom, "#999"), smooth_shading=True, split_sharp_edges=True,
                   specular=0.12 if mat else 0.5, specular_power=8 if mat else 30,
                   ambient=0.22 if mat else 0.15, diffuse=0.85 if mat else 0.8)
    if image is not None and coupe is None:
        # capture de l'appli sur la zone affichée, 0,05 mm au-dessus de la vitre
        (ax, ay, az), (bx, by, _), (cx, cy, _) = image
        dalle = pv.Plane(center=((ax + bx) / 2, (ay + cy) / 2, az + 0.05), direction=(0, 0, 1),
                         i_size=bx - ax, j_size=cy - ay)
        dalle.texture_map_to_plane(inplace=True)
        p.add_mesh(dalle, texture=pv.read_texture(str(CAPTURE)), ambient=0.6, diffuse=0.4, specular=0.3)
    if cockpit:
        # cockpit, forme indicative : cintre aéro (aile de 34 mm) et potence de 110 mm
        avant, haut, arriere = cockpit
        aile = pv.Box((-200, 200, avant - 34, avant, 0, haut * 0.6))
        potence = pv.Box((-18, 18, -110, avant - 30, 0, haut))
        for m in (aile, potence):
            p.add_mesh(m, color="#c5ccd4", opacity=0.14)
    p.enable_anti_aliasing("ssaa")
    # cadrage : direction de la caméra seulement, puis la pièce entière (bras compris) dans l'image
    (px, py, pz), (fx, fy, fz), haut = camera
    p.view_vector((px - fx, py - fy, pz - fz), viewup=haut)
    tout = pv.merge([m.translate((0, 0, ecarte)) if (ecarte and n == "capot") else m for n, m in maillages.items()])
    if coupe is not None:
        tout = tout.clip(normal="x", origin=(coupe, 0, 0), invert=True)
    p.reset_camera(bounds=tout.bounds)
    p.camera.zoom(zoom)
    p.screenshot(RENDUS / fichier)
    p.close()


def rendre(corps, capot, pieces, image=None, cockpit=None):
    RENDUS.mkdir(exist_ok=True)
    for f in RENDUS.glob("*.png"):
        f.unlink()
    m = {"corps": maillage(corps), "capot": maillage(capot)}
    m.update({k: maillage(v, 0.1) for k, v in pieces.items()})
    cible = (0, 75, 10)
    scene(m, "1_trois_quarts.png", [(-170, -90, 140), cible, (0, 0, 1)], image=image, cockpit=cockpit)
    scene(m, "2_avant.png", [(140, 260, 100), cible, (0, 0, 1)], image=image, cockpit=cockpit)
    scene(m, "6_cycliste.png", [(0, -170, 180), (0, 80, 15), (0, 0, 1)], image=image, cockpit=cockpit, zoom=1.1)
    scene(m, "7_profil.png", [(260, 40, 20), (0, 40, 10), (0, 0, 1)], image=image, cockpit=cockpit)
    scene(m, "3_dessous.png", [(-130, 10, -140), cible, (0, 0, 1)])
    scene(m, "4_coupe.png", [(190, 40, 40), cible, (0, 0, 1)], coupe=10)
    scene(m, "5_eclate.png", [(-150, -60, 150), cible, (0, 0, 1)], ecarte=35)
    print("rendus :", ", ".join(sorted(f.name for f in RENDUS.glob("*.png"))))
