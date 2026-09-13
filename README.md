# Canyon compteur

Compteur vélo autonome façon Garmin, avec une interface soignée et tactile : Raspberry Pi Zero 2 W + écran couleur 2,8" 480×640 en portrait.

L'interface a une identité « Graphite », accordée au Canyon Ultimate CF SL 7 Ash Grey :
- le gris est la marque, et la couleur ne sert qu'à informer ;
- l'oblique du logo Canyon revient partout : chiffres penchés, coins coupés, glissements en diagonale ;
- tout se dessine au trait : le vélo dans l'intro, les parcours sur l'accueil.

<img src="docs/intro.gif" alt="Intro" width="240"> <img src="docs/accueil.png" alt="Accueil" width="240"> <img src="docs/capture.png" alt="Page principale" width="240"> <img src="docs/carte.png" alt="Page carte" width="240"> <img src="docs/altitude.png" alt="Page altitude" width="240"> <img src="docs/cardio.png" alt="Page cardio" width="240"> <img src="docs/tours.png" alt="Page tours" width="240"> <img src="docs/resume.png" alt="Résumé de sortie" width="240"> <img src="docs/sorties.png" alt="Mes sorties" width="240">

Matériel et points d'attention : [docs/materiel.md](docs/materiel.md)

## Lancer le simulateur (Mac/PC)

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m compteur                              # fenêtre 480×640, avec l'intro
.venv/bin/python -m compteur --sans-intro --accel 10      # directement sur l'accueil, simulation 10x plus rapide
.venv/bin/python -m compteur --screenshot capture.png     # capture sans fenêtre (--page accueil, libre, menu, sorties, reglages,
                                                          #   principale, carte, altitude, cardio, tours ou resume)
.venv/bin/python -m compteur --intro-gif docs/intro.gif   # enregistre l'intro en GIF (avec ffmpeg)
.venv/bin/python -m compteur --mesure                     # fluidité et charge page par page (3 min), pour le Pi
.venv/bin/python -m compteur --miroir                     # l'écran aussi dans un navigateur, où la souris fait le doigt
.venv/bin/python -m pytest                                # tests
```

La carte n'est pas fournie (trop lourde) : voir [Carte hors ligne](#carte-hors-ligne). Sans elle, la page carte affiche le parcours sur un fond uni.

**Au démarrage**, le vélo se dessine au trait, son cadre se replie en « Ʌ » et devient le logo Canyon, qui se pose sur l'accueil. Un toucher, Espace ou Entrée passe l'intro.

**Sur l'accueil**, on balaie les parcours du dossier `parcours/` (tracé, profil d'altitude, distance, dénivelé), puis la carte « Sortie libre ». Pour ajouter les tiens (Komoot, Strava), dépose leurs GPX dans `parcours/` et reconstruis la carte (voir plus bas). Un GPX illisible ou inutilisable (tronqué, un seul point, tous ses points au même endroit) est ignoré et signalé dans la console ; une carte abîmée aussi : l'appli démarre sans elle.

**Démarrer** attend le signal GPS : la sortie part toute seule au premier signal, ou tout de suite si l'on appuie une deuxième fois.

**Pendant la sortie**, cinq pages se balaient :
- **Page principale** : la vitesse en grand, l'avancement en segments penchés, puis six mesures sur un panneau carbone.
- **Page carte** : le parcours en laque, qui se creuse derrière toi, et ta position sous la forme du « Ʌ » du logo. En sortie libre, ta trace se dessine derrière toi. Le creux comme la trace suivent la flèche sans à-coups, entre deux mesures.
- **Page altitude** : l'altitude et la pente ; les 5 prochains km en gros plan, colorés selon la pente (ambre, orange puis rouge en montée, bleu en descente), avec leur dénivelé ; tout le parcours en bande fine, avec ta position, le D+ fait et ce qui reste à grimper. En sortie libre : les 5 derniers km et toute la sortie.
- **Page cardio** : la FC et sa zone (Récupération, Endurance, Tempo, Seuil, Maximum), la courbe des 10 dernières minutes aux couleurs des zones, puis le temps passé dans chaque zone, avec la moyenne et le max.
- **Page tours** : le tour en cours en grand (chrono, distance, moyenne, cardio), les tours finis du plus récent au plus ancien, et un bouton « Nouveau tour » : un simple toucher, comme le bouton Lap.
- **Couleur** : elle n'apparaît que pour informer. Pente : ambre, orange puis rouge en montée, bleu en descente. Zone cardio, hors parcours (ambre), point rouge pendant l'enregistrement.
- **Fin de tour** : un bandeau glisse sur le haut de la page avec le temps, la distance, la moyenne et le cardio du tour. Sur la page tours, pas de bandeau : le tour fini arrive en haut de la liste.

**En pause**, un bouton « Maintenir pour terminer » ouvre le résumé de la sortie. Il faut le tenir une seconde, pour éviter les fausses manœuvres.

**Le résumé** se balaie sur trois pages : le tracé et les chiffres clés (avec vitesse et FC max), l'altitude et le temps passé dans chaque zone cardio, puis les tours. En bas :
- **Enregistrer** écrit la sortie dans `sorties/` : un fichier `.fit` à déposer sur Strava ou Garmin Connect (trace, altitude, vitesse, cardio, pauses, tours), et son résumé en `.json` pour Mes sorties. L'écriture se fait à part, sans figer l'écran, et chaque fichier est forcé sur la carte SD avant d'être annoncé « Enregistrée ». Si la carte refuse (pleine, en lecture seule), le résumé reste, avec la raison : on peut réessayer, ou supprimer. Une valeur aberrante d'un capteur (pic GPS, défaut de la ceinture) est écrite « absente » dans le fichier FIT, sans empêcher l'enregistrement.
- **Supprimer** se maintient une seconde, comme Terminer.

**Après une coupure** (batterie vide, courant coupé, plantage), rien n'est perdu : la sortie en cours s'écrit au fil de l'eau dans `sorties/reprise.jsonl`, toutes les 30 s et à chaque Start/Pause, Lap et fin de sortie. Au démarrage suivant, elle reprend en pause, là où elle en était, avec un bandeau « Sortie reprise » ; Start la continue. Coupée sur le résumé, c'est le résumé qui revient. Au plus 30 s de mesures perdues. Le fichier s'efface une fois la sortie enregistrée ou supprimée.

**Le menu** (bouton ≡ à gauche de Démarrer) :
- **Mes sorties** : les sorties enregistrées, de la plus récente à la plus ancienne, avec leur tracé, leur date, leur distance et leur temps. Un toucher rouvre leur résumé ; en bas, Retour, ou Supprimer (à maintenir), qui efface ses deux fichiers.
- **Réglages** : FC max, qui donne les zones cardio affichées en dessous ; auto-pause ; luminosité de l'écran. Ils sont enregistrés dès qu'on les change, dans `~/.config/canyon-compteur/reglages.json`. La FC max et l'auto-pause s'appliquent au prochain départ. La luminosité règle le rétroéclairage du Pi tout de suite ; sur le Mac, elle est sans effet.
- **Éteindre** (à maintenir) : sur le Pi, le compteur s'arrête proprement, sans risque pour la carte SD (le droit d'arrêter le système est donné par `tools/pi/installer.sh`) ; si le système refuse, un message le dit et le compteur reste allumé. Sur le Mac, l'appli se ferme.

**Le cycliste simulé** roule sur le parcours choisi (le premier en sortie libre) : plus lent en montée, plus rapide en descente, avec un arrêt de 15 s toutes les 5 minutes (pour voir l'auto-pause). Son GPS met 4 s à capter au lancement.

| Touche | Bouton du compteur |
|---|---|
| Espace | Start / Pause pendant la sortie ; ailleurs, comme Entrée |
| Entrée | Démarrer sur l'accueil, Enregistrer sur le résumé, ouvrir l'entrée choisie dans le menu, Retour sur une sortie rouverte |
| ← → (ou P) | Parcours précédent / suivant sur l'accueil, page précédente / suivante pendant la sortie et sur les résumés, valeur dans les réglages ; dans le menu et Mes sorties : retour / ouvrir |
| ↑ ↓ | Entrée du menu, sortie ou réglage précédent / suivant |
| M | Menu (depuis l'accueil) |
| R | Réglages (depuis l'accueil) |
| L | Lap (nouveau tour) |
| E | Terminer la sortie (en pause) : ouvre le résumé |
| Retour arrière | Supprimer la sortie (sur le résumé, ou une sortie rouverte depuis Mes sorties) |
| Échap | Écran précédent dans le menu ; quitter depuis l'accueil (jamais pendant une sortie ni sur son résumé) |
| Q | Quitter, depuis l'accueil seulement |

Sur la carte : + et − pour zoomer (ou pincer), la boussole bascule entre « cap en haut » et « nord en haut ».

## Carte hors ligne

Le compteur n'a pas internet et le Pi Zero est trop faible pour dessiner une carte vectorielle. La carte est donc dessinée une fois pour toutes sur le Mac, à partir des données OpenStreetMap (fond [Protomaps](https://protomaps.com)), avec un style graphite accordé à l'interface. Le compteur n'affiche ensuite que des images : le fichier `cartes/ile-de-france.mbtiles`.

```bash
brew install pmtiles
# 1. Données OSM de l'Île-de-France (≈ 300 Mo). Date d'un build récent : https://maps.protomaps.com/builds/
pmtiles extract https://build.protomaps.com/20260911.pmtiles cartes/osm-ile-de-france.pmtiles \
  --bbox=1.4462,48.1201,3.5591,49.2415 --maxzoom=15
# 2. Outils de rendu (MapLibre n'existe que jusqu'à Node 24, d'où npx -p node@24)
cd tools/carte && npx -y -p node@24 -c "npm install"
# 3. Dessin des tuiles : toute la région jusqu'au zoom 12, zooms 13 à 16 autour des parcours
#    (≈ 70 s et 95 Mo pour les trois parcours fournis)
npm run construire
```

Pour rouler n'importe où sans parcours, passer `REGION_ZOOMS` à `[8, 16]` dans `tools/carte/rendu.mjs` (≈ 150 000 tuiles, une quinzaine de minutes, ≈ 2 Go).

Les tuiles sont dessinées en x2 (512 px) pour être nettes sur l'écran du compteur, qui affiche un pixel de tuile par pixel d'écran. Sur un écran Retina de Mac, la carte paraît donc un peu floue : c'est normal.

## Sur le Raspberry Pi

Testé sur un Raspberry Pi Zero 2 W avec Raspberry Pi OS Lite 64 bits (Debian 13), préparé avec Raspberry Pi Imager (nom `compteur`, Wi-Fi, SSH par clé). Depuis le Mac, le Pi étant sur le même Wi-Fi :

```bash
tools/pi/envoyer.sh                                             # copie le projet dans ~/compteur (sans les sorties du Mac)
ssh julesvide@compteur.local compteur/tools/pi/installer.sh     # bibliothèques, Python et PySide6, réglage du GPU, droit d'éteindre
ssh julesvide@compteur.local 'cd compteur && .venv/bin/python -m compteur --miroir'
```

- **Affichage** : plein écran sans bureau (`linuxfb`, par DRM), dessiné par le processeur, sans le GPU (voir plus bas) ; réglé dans `compteur/app.py`. Le GPU reste possible pour des essais : `tools/pi/qt_gbm.py` ajoute la pièce de Qt qui manque aux paquets PySide6 (`libQt6EglFsKmsGbmSupport`, prise dans la distribution officielle de Qt, même compilation, vérifiée), puis `QT_QPA_PLATFORM=eglfs QT_QPA_EGLFS_INTEGRATION=eglfs_kms QT_QUICK_BACKEND= .venv/bin/python -m compteur`.
- **Mémoire du GPU à 128 Mo** (`dtoverlay=vc4-kms-v3d,cma-128`, posé par l'installation) : avec les 256 Mo par défaut, le Pi se figeait au changement de page quand le GPU dessinait.
- **GPU : écarté.** Sur le Zero 2 W, le pilote du GPU (vc4) laisse le GPU écrire hors de sa mémoire : mémoire des applis et du noyau corrompue, plantages, Pi figé. Observé ici avec les noyaux 6.18.34, 6.18.39 et 6.18.50 (septembre 2026), ce dernier ayant pourtant les correctifs du 4 août (« drm/vc4: Supply the overflow slot size in BPOS »), et avec une alimentation 5 V 2,5 A comme avec le port USB d'un ordinateur. Dessinée par le processeur, la même appli tourne sans aucune corruption.
- **Miroir** (`--miroir`) : l'écran du Pi dans un navigateur, sur http://compteur.local:8080, où la souris fait le doigt et le clavier les boutons. Jusqu'à 25 images par seconde, moins quand le processeur dessine : l'écran DRM ne se capture pas, chaque image du miroir coûte donc un dessin complet, et le miroir ralentit plutôt que l'appli. Sans mot de passe : réseau de la maison seulement.
- **Mesure** (`--mesure`) : une sortie simulée passe par chaque page ; images par seconde, processeur, mémoire et température. Sans écran branché, `video=HDMI-A-1:480x640M@60D` dans `/boot/firmware/cmdline.txt` simule un écran de la bonne taille.

Mesuré sur le Pi Zero 2 W (images dessinées par seconde, processeur en % d'un cœur sur 4) : au GPU, avant et après l'allègement de l'interface, puis dessiné par le processeur, le réglage actuel. Sur la carte, l'image ne change qu'au pixel près : une vingtaine de fois par seconde à 30 km/h, virages et halo compris.

| Page | GPU, avant | GPU, après | Processeur |
|---|---|---|---|
| Accueil | 60 images/s, 36 % | 0 image/s, 1 % | 0 image/s, 1 % |
| Principale | 60 images/s, 81 % | 1 image/s, 4 % | 2 images/s, 4 % |
| Carte | 57 images/s, 96 % | 26 images/s, 42 % | 22 images/s, 32 % |
| Carte, sortie libre | 57 images/s, 94 % | 25 images/s, 41 % | 22 images/s, 29 % |
| Altitude | 5 images/s, 25 % | 1,7 image/s, 7 % | 2 images/s, 11 % |
| Cardio | 47 images/s, 80 % | 2 images/s, 10 % | 2 images/s, 9 % |
| Tours | 49 images/s, 66 % | 1 image/s, 5 % | 2 images/s, 5 % |
| Pause | 60 images/s, 53 % | 1 image/s, 4 % | 1,3 image/s, 4 % |
| Résumé | 60 images/s, 34 % | 0,7 image/s, 3 % | 0,9 image/s, 4 % |

La mise à jour de chaque seconde (calcul et affichage) passe de 200 ms environ à 30-60 ms sur les pages cardio, tours et altitude.

Principale, carte et carte en sortie libre ont été remesurées le 13/09/2026, après les corrections de fiabilité, à 51 min de sortie, avec le noyau 6.18.39 : la carte hors de l'écran ne coûte plus rien, et une longue sortie libre reste fluide (22 images/s à 5 h au lieu de 12). Le détail est dans [docs/fiabilite.md](docs/fiabilite.md).

## Architecture

- **Backend en Python** : capteurs, calculs, enregistrement. Le moteur de calcul (`ride.py`) ne dépend ni de Qt ni du matériel, il est testé seul.
- **Interface en Qt Quick (QML)** via PySide6 : rendue par le GPU, animations fluides, gestes tactiles. Elle lit les valeurs via `RideModel`, `SessionModel`, `HistoryModel` et `SettingsModel`.
- **Même code partout** : sur le Mac l'interface s'ouvre dans une fenêtre, sur le Pi elle tourne en plein écran sans bureau (`linuxfb`), dessinée par le processeur, et Qt gère directement le tactile.
- **Rien ne se redessine pour rien**, pour la batterie et le Pi Zero :
  - l'écran ne change qu'à la mise à jour de chaque seconde : ce qui clignote (enregistrement, chrono en pause, capteur qui cherche) suit cette seconde au lieu d'être animé ;
  - la carte ne glisse que lorsqu'elle est à l'écran, et ne se redessine que lorsqu'elle a bougé ou tourné d'au moins un pixel. Hors de l'écran, elle ne dessine rien, ni son image ni sa trace ; seules ses tuiles suivent la position, pour qu'elle réapparaisse complète. Elle se replace dès qu'elle réapparaît, même en partie pendant un balayage. Son halo ne respire qu'en roulant, par pas d'un pixel. Parcours et trace y sont découpés en tronçons : seuls ceux à l'écran sont dessinés, et seul le bout qui avance sous la flèche est redessiné. La trace va par tronçons de 500 m, allégés des points dont l'écart ne se voit pas ;
  - une page de sortie ne recalcule ses courbes que si on la regarde ; une page voisine est dessinée une fois, pour arriver prête sous le doigt. Le gros plan altitude n'est recalculé que tous les 20 m, la courbe cardio compte 120 points, et leurs tracés sont calculés hors du fil de l'interface.

```
compteur/
  __main__.py      point d'entrée (python -m compteur)
  app.py           démarre Qt, cadence les mesures (1/s), relie backend et interface, éteint le Pi
  ride.py          moteur de calcul : chrono, distance, moyennes, altitude, cardio, auto-pause, tours
  route.py         parcours GPX : position sur le tracé, distance et dénivelé restants, tracé miniature
  sim.py           cycliste simulé et son GPS (en attendant les vrais capteurs)
  model.py         RideModel : la sortie en cours, exposée à l'interface (trace par tronçons, profils,
                   courbe cardio, tours)
  session.py       SessionModel : parcours de l'accueil, départ, fin et résumé de sortie ;
                   HistoryModel : Mes sorties
  settings.py      réglages enregistrés (FC max, auto-pause, luminosité) et rétroéclairage
  summary.py       résumé d'une sortie terminée
  fit.py           fichier FIT (Strava, Garmin Connect), écrit sans dépendance
  history.py       sorties enregistrées dans sorties/ : écriture (FIT et résumé), liste, suppression
  journal.py       fichier de reprise : la sortie en cours, pour la retrouver après une coupure
  storage.py       écritures sur la carte SD : forcées sur la carte, par un fil à part qui ne fige pas l'écran
  tiles.py         carte hors ligne : sert les tuiles du fichier MBTiles à l'interface
  benchmark.py     mode mesure : fluidité, processeur et mémoire, page par page (pour le Pi)
  mirror.py        miroir : l'écran dans un navigateur, clics et touches rejoués comme sur l'écran tactile
  mirror.html      page du miroir
  ui/
    Main.qml       fenêtre, raccourcis clavier, enchaînement intro → accueil → sortie, écrans du menu
    Intro.qml      intro : le vélo se dessine au trait et devient le logo
    Logo.qml       logo Canyon, une forme par lettre
    BikeLine.qml   Canyon Ultimate de profil, au trait
    HomePage.qml   accueil : parcours à balayer, état des capteurs, menu, départ
    RouteCard.qml  carte d'un parcours : tracé, profil d'altitude, distance, dénivelé
    FreeRideCard.qml  carte « Sortie libre »
    MenuPage.qml   menu : Mes sorties, Réglages, Éteindre
    RidesPage.qml  Mes sorties : les sorties enregistrées
    SettingsPage.qml  réglages
    SummaryPage.qml   résumé d'une sortie : Enregistrer ou Supprimer, ou Retour depuis Mes sorties
    RidePage.qml   page principale : vitesse, avancement, six mesures
    MapPage.qml    page carte
    MapView.qml    carte : tuiles, parcours, trace, position
    AltitudePage.qml  page altitude : gros plan sur 5 km, profil du parcours, dénivelé restant
    CardioPage.qml    page cardio : courbe des 10 dernières minutes, temps par zone
    LapsPage.qml      page tours : tour en cours, tours finis, Nouveau tour
    StatusBar.qml  heure, état de la sortie, GPS, batterie
    LapBanner.qml  bandeau de fin de tour
    PageHeader.qml en-tête des écrans du menu (retour)
    Panel.qml      panneau à coins coupés, en carbone tissé
    HeroFigure.qml grande mesure en tête de page
    GradeWedge.qml pente dessinée, à sa couleur
    ZoneGauge.qml  jauge des cinq zones cardio
    ZoneRow.qml    temps passé dans une zone cardio
    Outline.qml    tracé en miniature
    Dashes.qml     indicateur de page, en traits penchés
    HoldButton.qml bouton à maintenir (terminer, supprimer, éteindre)
    Theme.qml      couleurs (dont celle de la pente), polices, pente du logo
    Format.js      formatage des nombres et des durées
    fonts/         Barlow (licence OFL)
    textures/      trame carbone des panneaux
parcours/          parcours GPX (Komoot, Strava...) : vallée de Chevreuse, forêt de Rambouillet, Vexin
cartes/            carte hors ligne (générée, non versionnée)
sorties/           sorties enregistrées : .fit et .json (non versionnées)
tools/carte/       fabrication de la carte (Node + MapLibre)
tools/texture_carbone.py   fabrication de la trame carbone
tests/             tests du moteur de calcul, des modèles, des réglages, de l'historique, du fichier FIT et du
                   fichier de reprise ; l'appli entière hors écran (coupures, enregistrement refusé, fichiers
                   abîmés, touches, Éteindre, image de la carte), pilotée par tests/pilote.py
```

## Règles de calcul

- **Temps** : temps en mouvement, hors pauses manuelles et auto-pause. Le temps total écoulé est aussi calculé.
- **Auto-pause** (désactivable dans les réglages) : sous 3 km/h pendant 2 s. Reprise dès qu'on repart. Si la vitesse est inconnue (GPS perdu), rien ne change.
- **Moyennes** : pondérées par le temps.
- **Dénivelé** : une variation d'altitude n'est comptée qu'au-delà de 2 m, pour ignorer le bruit de l'altimètre. Le dénivelé restant d'un parcours est compté de la même façon.
- **Pente** : mesurée sur les 40 derniers mètres. Sur le gros plan de la page altitude, lissée sur environ 150 m.
- **Zones cardio** : en % de la FC max (190 par défaut, réglable de 120 à 220) : moins de 60, 60-70, 70-80, 80-90, plus de 90 %.
- **Parcours** : position recherchée le long du tracé, sans confondre les deux passages d'un aller-retour. Hors parcours au-delà de 40 m.

## Feuille de route

1. ✅ Squelette + simulateur
2. ✅ Moteur de calcul : chrono, distance, moyennes, auto-pause, tours
3. Pages et navigation :
   - fait : intro et accueil (identité Graphite), choix du parcours, attente du GPS, pages principale, carte OSM hors ligne, altitude, cardio et tours, fin de sortie et résumé, menu (Mes sorties, réglages, extinction) ;
   - à faire : retour guidé vers le parcours quand on s'en écarte.
4. Vrais capteurs : GPS, ceinture cardio Bluetooth, baromètre
5. Enregistrement .FIT : fait (fichier à déposer à la main sur Strava ou Garmin Connect) ; à faire : envoi automatique en Wi-Fi
6. Installation sur le Pi :
   - fait : installation logicielle (`tools/pi`), affichage par le processeur, mesure, miroir, interface allégée pour la batterie, droit d'éteindre le système, sortie protégée des coupures ;
   - à faire : écran DPI et tactile, GPS (et l'heure du GPS : le Pi n'a pas d'horloge sans réseau), BLE, boutons, démarrage auto, Wi-Fi coupé pendant la sortie.
7. Montage et tests sur le vélo

## Crédits

- **Logo Canyon** : redessiné d'après [CanyonBicycles.svg](https://commons.wikimedia.org/wiki/File:CanyonBicycles.svg) (Wikimedia Commons). C'est une marque de Canyon Bicycles GmbH, utilisée ici pour un usage personnel.
- **Police** : [Barlow](https://github.com/jpt/barlow), sous licence SIL Open Font License.
- **Parcours de démo** : calculés avec [BRouter](https://brouter.de).
- **Données cartographiques** : © les contributeurs d'OpenStreetMap.
