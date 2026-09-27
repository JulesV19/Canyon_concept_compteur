# Canyon compteur : notes de travail

Vue d'ensemble et commandes : README.md.

## Conventions

- Tout en français : interface, commentaires, docs. Identifiants du code en anglais.
- Python du projet : `.venv/bin/python`. Tests : `.venv/bin/python -m pytest -q` (≈ 35 s sur le Mac).
- `compteur/ride.py` ne dépend ni de Qt ni du matériel : le garder ainsi.
- Petits fichiers clairs : un fichier, un sujet, qu'on lit d'une traite. Viser moins de 300 lignes ; au-delà, découper
  en modules (un paquet Python avec un `__init__.py` qui réexporte, ou des composants QML) avant d'ajouter du code.
  Chaque découpage se fait seul, sans changer le comportement, et la suite de tests passe avant et après ; pour le
  QML, captures d'avant et d'après comparées au pixel. Exemples : `compteur/iphone/`, `compteur/strava/`,
  `GpsPage.qml` (un fichier par encadré : `GpsHero`, `GpsSky`…), `tests/test_app_*.py`.
- QML :
  - un nouveau type va dans `compteur/ui/qmldir` ;
  - réutiliser les petits composants partagés avant d'en écrire un : `Hairline` (filet), `SlantRule` (filet penché),
    `FigureLine` (valeur et unité), `LabeledFigure`, `RowLabel`, `RowHint`, `StepButton`, `SlantToggle`, `SlantSlider` ;
  - un encadré sorti d'une page reçoit la page par `required property var view` (écrire `page: page` ferait
    pointer la propriété sur elle-même) ; sa position qui dépend d'un voisin (`y: hero.y + …`) reste dans la page ;
  - jamais `id: layer` : dans un élément enfant, `layer` désigne sa propriété `Item.layer`.

## Produit

- Pas de capteur de puissance : aucune donnée de puissance à l'écran.
- Accueil : le carrousel ne montre que les parcours puis « Sortie libre ». Tout nouvel écran (capteurs, Strava…) devient une entrée du menu ≡ (`MenuPage.qml`), seulement quand il marche, jamais en entrée « Bientôt ». Exception voulue : Batterie s'ouvre depuis les Réglages.
- Identité « Graphite », accordée au Canyon Ultimate CF SL 7 Ash Grey :
  - le gris est la marque, la couleur ne sert qu'à informer (pente, zones, alertes) ; seule exception, l'orange Strava (`Theme.strava`), réservé au logo Strava et à ses animations, jamais à un chiffre ;
  - l'oblique du logo est le motif (chiffres penchés, coins coupés) ;
  - police Barlow ; une seule grande animation, l'intro ; les segments Strava ont en plus des instants courts (moins d'une seconde) : annonce, départ, record battu.
- Sobriété pour le Pi : l'écran ne change qu'au tic de chaque seconde (ce qui clignote suit ce tic), et une page hors de l'écran ne dessine rien.

## Données de l'utilisateur

`sorties/` contient ses vraies sorties. Aucun script de test ou de capture n'y écrit : `compteur.history.folder = <dossier temporaire>` puis `compteur.history.reload()` avant toute action, `tmp_path` dans pytest. Le fichier de reprise ne s'active qu'avec `Compteur(recovery=True)` (l'appli seule).

Strava : jetons, segments et records battus avec le compteur dans `~/.config/canyon-compteur/` (`strava.json`, `segments.json`, `records.json`). Seule l'appli synchronise et garde les records (`strava_sync=True`) ; essais et captures passent `strava_dir=<dossier temporaire>` (ou rien), jamais le vrai compte.

## Piloter l'appli hors écran

- Partir de `tests/pilote.py` (`wait`, `wait_for`, `activate`, `barrier`, `launch`).
- Jamais `QTest.qWait` ni `QTest.qWaitForWindowActive` : ils gardent le GIL, et le fil qui charge les tuiles (en Python) bloque l'appli. Attendre avec `QEventLoop` et `QTimer.singleShot`.
- Fenêtre active obligatoire, sinon les raccourcis sont ignorés. `compteur.timer.stop()`, puis `step()` et `tick()`, pour avancer le temps à la main.
- macOS n'a pas la commande `timeout`.
- Montrer chaque écran modifié par une capture (`--screenshot … --page …`), l'intro en GIF (`--intro-gif`).
- Après un gros changement, faire relire les corrections par un agent indépendant : la dernière fois, il a trouvé un vrai bogue.

## Raspberry Pi

- Accès : `ssh -4 julesvide@compteur.local` (l'IPv6 du Pi décroche), par clé, sudo sans mot de passe. Envoi : `tools/pi/envoyer.sh`.
- Rendu par le processeur, boucle simple sur un fil (`PI_QT_ENV` dans `compteur/pi.py`). Écartés :
  - le GPU : le pilote vc4 corrompt la mémoire (segfaults, Oops du noyau, Pi figé) avec les noyaux 6.18.34, 6.18.39 et 6.18.50, ce dernier ayant les correctifs vc4 d'août 2026 ; la RAM et l'alimentation sont hors de cause ;
  - `QSG_RENDER_LOOP=threaded` : deux fois moins d'images pour le même processeur.
- Noyau : 6.18.39+rpt-rpi-v8 des paquets. Pour le réinstaller : `linux-image-6.18.39+rpt-rpi-v8` et `raspi-firmware` (le méta-paquet ne recopie rien).
- Capture en linuxfb DRM : seul `QQuickWindow.grabWindow()` marche, et il redessine toute la fenêtre ; d'où le miroir qui espace ses captures.
- Heure : ni RTC ni réseau à vélo ; l'appli met l'horloge du système à l'heure du GPS dès sa première position (`Compteur.sync_clock`, droit `CAP_SYS_TIME` du service).
- Mesurer : `--mesure`. D'une série à l'autre, le processeur varie de 15 points parce que le nombre d'images varie : comparer le coût par image (% d'un cœur ÷ images/s).
- Retirés, dans le commit 94ee672 : `tools/pi/qt_gbm.py` (ajoute `libQt6EglFsKmsGbmSupport`, absente des roues PySide6, pour un essai au GPU) et `docs/fiabilite.md` (revue de fiabilité du 13/09/2026, avec toutes ses mesures).

## Points ouverts

- Carte plus chère en virage : chaque pas de rotation refait son image.
- Miroir plus lent depuis l'image en cache de la carte (cause inconnue, priorité basse).
