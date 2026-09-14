# Canyon compteur

Compteur vélo autonome pour un Canyon Ultimate : Raspberry Pi Zero 2 W, écran tactile 2,8" 480×640 en portrait, interface Qt Quick (PySide6). Projet personnel en cours ; les capteurs sont encore simulés.

<img src="docs/intro.gif" alt="Intro" width="160"> <img src="docs/accueil.png" alt="Accueil" width="160"> <img src="docs/principale.png" alt="Page principale" width="160"> <img src="docs/carte.png" alt="Carte" width="160"> <img src="docs/altitude.png" alt="Altitude" width="160"> <img src="docs/cardio.png" alt="Cardio" width="160"> <img src="docs/tours.png" alt="Tours" width="160"> <img src="docs/resume.png" alt="Résumé" width="160"> <img src="docs/sorties.png" alt="Mes sorties" width="160">

## Fonctions

- Parcours GPX (dossier `parcours/`) ou sortie libre ; départ au premier signal GPS.
- Cinq pages pendant la sortie : principale, carte OSM hors ligne, altitude, cardio, tours.
- Auto-pause, tours, résumé de fin de sortie.
- Enregistrement en `.fit` (Strava, Garmin Connect) et historique, dans `sorties/`.
- Reprise après coupure : la sortie en cours est écrite dans `sorties/reprise.jsonl` toutes les 30 s.
- Réglages : FC max, auto-pause, luminosité (`~/.config/canyon-compteur/reglages.json`).

## Lancer sur le Mac

```bash
uv venv .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m compteur                                  # fenêtre 480×640
.venv/bin/python -m compteur --sans-intro --accel 10          # sans l'intro, simulation 10× plus rapide
.venv/bin/python -m compteur --screenshot f.png --page carte  # capture sans fenêtre (autres options : --help)
.venv/bin/python -m compteur --mesure                         # fluidité et charge page par page (≈ 3 min)
.venv/bin/python -m compteur --miroir                         # l'écran aussi dans un navigateur (port 8080)
.venv/bin/python -m pytest
```

Clavier : Espace Start/Pause · Entrée valider · ← → pages et parcours · ↑ ↓ listes · L tour · E terminer (en pause) · M menu · R réglages · Retour arrière supprimer · Échap retour · Q quitter (depuis l'accueil).

## Carte hors ligne

Tuiles images dessinées une fois sur le Mac depuis OpenStreetMap (fond Protomaps), puis lues par le compteur dans `cartes/ile-de-france.mbtiles` (non versionné). Sans ce fichier, la page carte montre le parcours sur fond uni.

```bash
brew install pmtiles
pmtiles extract https://build.protomaps.com/20260911.pmtiles cartes/osm-ile-de-france.pmtiles \
  --bbox=1.4462,48.1201,3.5591,49.2415 --maxzoom=15     # ≈ 300 Mo ; builds : https://maps.protomaps.com/builds/
cd tools/carte && npx -y -p node@24 -c "npm install" && npm run construire
```

Zooms 8 à 12 sur toute la région, 13 à 16 autour des parcours (≈ 70 s, ≈ 95 Mo) : à relancer après l'ajout d'un GPX.

## Raspberry Pi

Raspberry Pi OS Lite 64 bits, PySide6 ≥ 6.10 installé par pip.

```bash
tools/pi/envoyer.sh                                               # copie le projet dans ~/compteur
ssh -4 julesvide@compteur.local compteur/tools/pi/installer.sh    # paquets, venv, réserve CMA, droit d'éteindre
ssh -4 julesvide@compteur.local 'cd compteur && .venv/bin/python -m compteur --miroir'
```

- Plein écran sans bureau (`linuxfb` par DRM), **dessiné par le processeur** (`PI_QT_ENV` dans `compteur/app.py`). Le GPU est écarté : sur le Zero 2 W, son pilote (vc4) corrompt la mémoire, jusqu'à figer le Pi (noyaux 6.18.34 à 6.18.50).
- Charge mesurée : carte ≈ 22 images/s pour ≈ 30 % d'un cœur ; autres pages ≤ 11 %.

Matériel prévu : [docs/materiel.md](docs/materiel.md).

## Organisation

| Dossier | Contenu |
|---|---|
| `compteur/` | backend Python : moteur de calcul sans Qt (`ride.py`), parcours, modèles pour l'interface, FIT, historique, reprise, simulateur |
| `compteur/ui/` | interface QML (`Main.qml` : navigation et raccourcis), polices Barlow, trame carbone |
| `tests/` | pytest, dont l'appli entière hors écran (`tests/pilote.py`) |
| `tools/` | fabrication de la carte (Node + MapLibre), envoi et installation sur le Pi, trame carbone |
| `parcours/` | parcours GPX de démo |
| `cartes/`, `sorties/` | carte générée et sorties enregistrées (non versionnées) |

## Règles de calcul

- Temps en mouvement, hors pauses. Auto-pause sous 3 km/h pendant 2 s.
- Moyennes pondérées par le temps.
- Dénivelé : variations de plus de 2 m seulement. Pente sur les 40 derniers mètres.
- Zones cardio en % de la FC max (190 par défaut, de 120 à 220) : < 60, 60-70, 70-80, 80-90, > 90 %.
- Hors parcours au-delà de 40 m.

## Reste à faire

- Vrais capteurs : GPS (et son heure : le Pi n'a pas d'horloge sans réseau), ceinture cardio BLE, baromètre.
- Écran DPI tactile, boutons, démarrage automatique, Wi-Fi coupé pendant la sortie.
- Retour guidé vers le parcours ; envoi automatique des sorties.
- Boîtier, montage et essais sur le vélo.

## Crédits

- Logo Canyon redessiné d'après [CanyonBicycles.svg](https://commons.wikimedia.org/wiki/File:CanyonBicycles.svg) (Wikimedia Commons) ; marque de Canyon Bicycles GmbH, usage personnel.
- Police [Barlow](https://github.com/jpt/barlow), licence SIL Open Font License.
- Parcours de démo calculés avec [BRouter](https://brouter.de).
- Données cartographiques © les contributeurs d'OpenStreetMap.
