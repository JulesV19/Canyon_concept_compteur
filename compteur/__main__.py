"""Point d'entrée : python -m compteur"""

import argparse
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path


def main() -> None:
    started = time.perf_counter()  # pour --mesure : délai jusqu'à la première image
    parser = argparse.ArgumentParser(prog="compteur", description="Compteur vélo autonome")
    parser.add_argument("--accel", type=float, default=1.0,
                        help="accélère la simulation (ex. 10 = 10 s simulées par seconde)")
    parser.add_argument("--sans-intro", action="store_true",
                        help="démarre directement sur l'accueil")
    parser.add_argument("--screenshot", metavar="FICHIER.png",
                        help="capture de l'écran (sans fenêtre), puis quitte")
    parser.add_argument("--page", choices=["accueil", "libre", "menu", "sorties", "reglages", "principale", "carte",
                                           "altitude", "cardio", "tours", "resume"],
                        default="principale",
                        help="écran à capturer : accueil (libre : sur la carte Sortie libre), menu, Mes sorties, "
                             "réglages, page de sortie après une sortie simulée (principale, carte, altitude, "
                             "cardio, tours), ou son résumé (resume)")
    parser.add_argument("--minutes", type=float, default=51,
                        help="durée de la sortie simulée avant la capture ou la mesure")
    parser.add_argument("--intro-gif", metavar="FICHIER.gif",
                        help="enregistre l'intro en GIF (sans fenêtre, avec ffmpeg), puis quitte")
    parser.add_argument("--images", metavar="DOSSIER",
                        help="avec --intro-gif : garde les images de l'intro dans ce dossier ; avec --mesure : "
                             "une capture à la fin de chaque phase")
    parser.add_argument("--mesure", nargs="?", const="", metavar="FICHIER.json",
                        help="mesure la fluidité et la charge page par page (environ 3 min), puis quitte ; "
                             "avec FICHIER, garde aussi le bilan en JSON")
    parser.add_argument("--miroir", nargs="?", const=8080, type=int, metavar="PORT",
                        help="montre aussi l'écran dans un navigateur (http://<machine>.local:PORT, 8080 par défaut), "
                             "où la souris fait le doigt")
    args = parser.parse_args()

    offscreen = bool(args.screenshot or args.intro_gif)
    if offscreen:
        # Rendu hors écran, à 2x pour une capture nette
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        os.environ["QT_SCALE_FACTOR"] = "2"

    from .app import Compteur
    from .history import RIDES_DIR

    # Seule l'appli protège la sortie en cours (fichier de reprise, reprise au démarrage) : ni les captures ni la mesure,
    # qui ne doivent jamais toucher aux sorties. La mesure fait une sortie et la supprime : dans un dossier à part.
    rides_dir = Path(tempfile.mkdtemp(prefix="compteur-mesure-")) if args.mesure is not None else RIDES_DIR
    compteur = Compteur(sys.argv[:1], software_rendering=offscreen, accel=args.accel,
                        intro=not (args.sans_intro or args.screenshot), autoplay=not args.intro_gif,
                        rides_dir=rides_dir, recovery=not (offscreen or args.mesure is not None))
    if args.intro_gif:
        compteur.record_intro(args.intro_gif, args.images)
        print(f"Intro enregistrée : {args.intro_gif}")
    elif args.screenshot:
        compteur.screenshot(args.screenshot, args.page, args.minutes)
        print(f"Capture enregistrée : {args.screenshot}")
    elif args.mesure is not None:
        from .benchmark import Benchmark

        Benchmark(compteur, args.mesure or None, args.minutes, started, images_dir=args.images).run()
    else:
        if args.miroir is not None:
            from .mirror import Mirror

            mirror = Mirror(compteur.window, args.miroir)  # gardé jusqu'à la fermeture
            print(f"Miroir : {mirror.url}", flush=True)
        sys.exit(compteur.run())
    compteur.close()
    if rides_dir != RIDES_DIR:
        shutil.rmtree(rides_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
