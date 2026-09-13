# Fiabilité : revue et corrections du 13 septembre 2026

La revue a vérifié l'appli de quatre façons, sur le Raspberry Pi Zero 2 W avec le dessin par le processeur : relecture indépendante de tout le code avec reproduction des défauts, essai d'endurance de 10 h simulées, comparaisons avec et sans l'image de la carte, mesure fine de ce qui grossit avec la durée d'une sortie.

**Tout est corrigé ou traité, sauf P5**, et vérifié sur le Mac comme sur le Pi. Pour chaque point : le problème en deux lignes, la correction, et comment elle est vérifiée.

## Bilan

| Point | Correction | Vérifié par |
|---|---|---|
| 1. Sortie seulement en mémoire | fichier de reprise, reprise en pause au démarrage | coupure brutale (SIGKILL) puis relance ; 12 essais du fichier |
| 2. Enregistrement raté : écran bloqué, sortie perdue | écriture à part, raison affichée, on réessaie | dossier non inscriptible, puis de nouveau inscriptible |
| 3. FIT sans contrôle de plage | valeur hors plage écrite « absente » | les 5 valeurs de la revue, relues par `garmin_fit_sdk` |
| 4. Éteindre n'éteint pas | règle polkit, arrêt demandé avant de fermer | arrêt réel du Pi par l'interface, le 13/09 à 22:31 |
| 5. Pas de fsync | fichier forcé, renommé, dossier forcé | ordre des opérations ; échec sans fichier temporaire |
| 6. Échap et Q ferment tout | seulement depuis l'accueil | touches en sortie, sur le résumé, à l'accueil |
| 7. Fichier invalide : pas de démarrage | GPX, carte et réglages abîmés ignorés | appli lancée avec 3 GPX et une carte abîmés |
| 8. Parcours de longueur nulle | refusé au chargement | GPX « sur place » ; résumé d'un GPS figé |
| 9. Pas d'horloge sans réseau | à faire avec le GPS | — |
| P1. Carte coûteuse hors écran | invisible hors écran, rien n'y est dessiné | image à jour dans 7 scénarios, tuiles prêtes au retour ; mesures sur le Pi |
| P2. Longue sortie libre | trace en tronçons de 500 m, allégés | mesures sur le Pi |
| P3. Carte sur parcours à 5 h | expliqué : ce sont les virages, pas la durée | même endroit mesuré à 89 min et à 5 h |
| P4. Enregistrer fige l'écran | écriture sur un fil à part | essai d'endurance : écran libre pendant les 4 s d'écriture |
| P5. Miroir plus lent | non traité (priorité basse, cause inconnue) | — |

- **Tests** : 139, qui passent en 33 s sur le Mac et en 1 min 45 sur le Pi (Python 3.13), sur les mêmes fichiers. Ils couvrent aussi l'appli entière, lancée hors écran dans un processus à part ([tests/pilote.py](../tests/pilote.py)) : coupures, enregistrement refusé, fichiers abîmés, touches, Éteindre, image et tuiles de la carte.
- **Sur le Pi** : noyau stable 6.18.39 remis, arrêt réel par l'appli, campagne de mesures, et nouvel essai d'endurance de 10 h simulées sur le code final : aucun plantage, aucune erreur du noyau (voir plus bas).

## 1. La sortie en cours n'existait qu'en mémoire

- **Problème** : jusqu'à « Enregistrer », la sortie n'existait que dans `Ride.records`. Batterie vide, courant coupé ou plantage : tout était perdu, y compris pendant l'attente sur le résumé.
- **Correction** : un fichier de reprise, `sorties/reprise.jsonl` ([journal.py](../compteur/journal.py)).
  - Le moteur de calcul donne toujours le même résultat à partir des mêmes entrées. Le fichier garde donc ces entrées, dans l'ordre : chaque mesure, chaque Start/Pause et chaque Lap ([Ride.on_input](../compteur/ride.py#L163)), une ligne JSON par entrée après un en-tête (départ, parcours, réglages).
  - Les mesures partent par paquets de 30, soit toutes les 30 s ; Start/Pause, Lap et la fin de la sortie partent tout de suite. Chaque paquet est forcé sur la carte par le fil d'écriture, sans faire attendre l'écran. Au plus 30 s perdues.
  - **Au démarrage** ([app.py:251](../compteur/app.py#L251)), une sortie en cours reprend en pause, là où elle en était, avec un bandeau « Sortie reprise · coupée à 22:07 » et ses chiffres ; Start la continue. Une sortie terminée rouvre son résumé.
  - L'horloge des mesures repart d'où elle était, plus le temps passé depuis la dernière écriture : la coupure compte comme une pause (12 h au plus, voir le point 9). La position sur le parcours est retrouvée en suivant la trace, une mesure sur 30, sans confondre les deux passages d'un aller-retour. Le cycliste simulé repart de là.
  - Une ligne coupée par une coupure est ignorée, comme tout ce qui suivrait une ligne illisible : la sortie reprend dans l'état cohérent de sa dernière ligne complète. Le fichier y est ramené avant de continuer.
  - Si la carte refuse d'écrire, la sortie continue ; ce qui n'a pas pu s'écrire repart à l'écriture suivante, dans l'ordre et sans doublon.
  - Le fichier s'efface une fois la sortie supprimée, ou enregistrée et ses fichiers forcés sur la carte. Une sortie déjà enregistrée n'est pas reprise. Un en-tête illisible est mis de côté (`reprise-illisible-….jsonl`), jamais effacé.
  - Seule l'appli s'en sert : ni les captures, ni `--mesure`, ni les scripts d'essai (option `recovery` de `Compteur`).
- **Vérifié** :
  - [test_journal.py](../tests/test_journal.py) : sortie rejouée identique champ par champ (chrono, tours, trace, mesures, zones, pauses) ; paquets de 30 ; ligne coupée à la fin ; ligne illisible au milieu ; fin de sortie ; reprise dans le même fichier, qui redonne la même sortie que sans coupure ; carte qui refuse puis accepte ; vrai fil d'écriture.
  - [test_app.py](../tests/test_app.py) : **coupure brutale** (SIGKILL) après 10 min de sortie, puis relance. Distance, chrono, tours, trace et mesures sont identiques à la dernière écriture ; la sortie est en pause ; l'horloge ne recule pas ; après Start, le cycliste simulé repart à moins de 150 m de là.
  - Coupure sur le résumé : le résumé revient, et Enregistrer donne un FIT valide pour `garmin_fit_sdk` ; le fichier de reprise est effacé.
  - Sur le Pi, pendant l'essai d'endurance : le fichier d'une sortie de 5 h pèse 1,9 Mo et se rejoue en 3,1 s, à l'identique (0,000 m d'écart). Redémarrer après une coupure en fin de longue sortie prend donc 3 s de plus.

## 2. Un enregistrement qui échoue bloquait l'écran et perdait la sortie

- **Problème** : l'exception remontait jusqu'à `closeSummary` dans Main.qml ; l'écran restait sur « Enregistrée », ni Enregistrer ni Supprimer ne répondaient, et un `.fit.tmp` pouvait rester.
- **Correction** :
  - l'enregistrement se fait sur le fil d'écriture ([app.py:205](../compteur/app.py#L205)) ; `SessionModel` expose `saving`, `saveError` et le signal `saved` ;
  - sur le résumé : « Enregistrement… » avec un anneau (seulement si l'écriture dure plus de 250 ms), puis « ✓ Enregistrée », puis l'accueil ;
  - refusé : « Pas enregistrée : carte SD pleine » (ou « en lecture seule », « écriture refusée », « erreur d'écriture ») à la place des tirets. La sortie reste : Enregistrer réessaie, Supprimer reste possible ;
  - aucun fichier temporaire laissé derrière ; Supprimer après un échec efface aussi un `.fit` resté seul ; rien ne se supprime pendant l'écriture (Retour arrière compris).
- **Vérifié** : [test_app.py](../tests/test_app.py) reproduit le cas de la revue, dossier des sorties non inscriptible : message « écriture refusée », le résumé reste, seul le fichier de reprise est dans le dossier. Dossier de nouveau inscriptible : Entrée enregistre et l'accueil revient. Aussi `test_session` (réessai) et `test_summary` (carte pleine au deuxième fichier).

## 3. Le fichier FIT écrivait les valeurs sans vérifier leur plage

- **Problème** : `struct.pack` sur la valeur brute ; une seule valeur aberrante faisait échouer tout l'enregistrement.
- **Correction** : chaque type FIT connaît sa plage ([fit.py:42](../compteur/fit.py#L42)). Une valeur hors plage, ou qui n'est pas un nombre fini, est écrite « absente ». En amont, le moteur compte comme absente une valeur non finie d'un capteur ([ride.py:41](../compteur/ride.py#L41)).
- **Vérifié** : [test_fit.py](../tests/test_fit.py), avec les valeurs de la revue : 70 m/s, −600 m, FC 300, NaN, et aussi longitude 180° et infini. Le fichier se relit sans erreur avec `garmin_fit_sdk`, la valeur est absente et ses voisines présentes ; dans les tours et la séance, les maximums aberrants sont absents et les moyennes écrites.
- **Reste** : une valeur fausse mais dans la plage (pic GPS à 25 m/s) compte encore dans les maximums. Le tri se fera avec les vrais capteurs.

## 4. « Éteindre » n'éteignait pas le Pi

- **Problème** : polkit exigeait un mot de passe (`CanPowerOff` : `"challenge"`), et l'échec de `systemctl` passait inaperçu.
- **Correction** :
  - [installer.sh](../tools/pi/installer.sh#L23) pose `/etc/polkit-1/rules.d/50-compteur.rules`, qui autorise `power-off` et `power-off-multiple-sessions` pour l'utilisateur de l'appli ;
  - l'appli demande l'arrêt (`systemctl --no-ask-password poweroff`) avant de se fermer ([app.py:305](../compteur/app.py#L305)) ; s'il est refusé, le menu affiche « Impossible d'éteindre : le système refuse l'arrêt » et le compteur reste allumé ;
  - un SIGTERM (arrêt du système, `systemctl stop`) ferme l'appli proprement : ce qui attend est écrit dans le fichier de reprise.
- **Vérifié sur le Pi** : `CanPowerOff` répond `"yes"`, `pkcheck` rend 0. **Arrêt réel par l'interface**, le 13/09 à 22:31 : menu, puis appui maintenu sur « Maintenir pour éteindre » par le miroir. Le journal montre « The system will power off now! » à l'instant où le bouton se remplit, puis un arrêt complet (démontage, synchronisation, mise hors tension). Au redémarrage, le système de fichiers est propre. Le refus est testé dans [test_app.py](../tests/test_app.py).

## 5. Les fichiers n'étaient pas forcés sur la carte SD

- **Correction** : [storage.write_atomic](../compteur/storage.py#L31) écrit un fichier temporaire, le force sur la carte, le renomme, puis force le dossier. Il sert au FIT, au résumé et aux réglages. Le fichier de reprise est forcé à chaque paquet, et son dossier à la création comme à l'effacement.
- **Vérifié** : [test_storage.py](../tests/test_storage.py) contrôle l'ordre (données forcées, renommage, dossier forcé), et qu'un échec laisse l'ancien fichier intact, sans fichier temporaire.
- **Coût sur le Pi** : 50 ms pour un FIT de 600 Ko ; 7 ms pour un paquet du fichier de reprise (10 ms au plus), sur le fil d'écriture.

## 6. Échap ou Q fermaient l'appli en pleine sortie

- **Correction** : Échap revient en arrière dans le menu et ne quitte que depuis l'accueil ; Q ne marche qu'à l'accueil ([Main.qml:228](../compteur/ui/Main.qml#L228)). Le miroir peut continuer à transmettre Échap.
- **Vérifié** : [test_app.py](../tests/test_app.py) : Échap et Q pendant une sortie et sur le résumé, l'appli reste ; Q à l'accueil, elle se ferme.

## 7. Un fichier invalide empêchait l'appli de démarrer

- **GPX** : un fichier illisible ou inutilisable est ignoré et signalé dans la console ([app.py:62](../compteur/app.py#L62)) ; `Route.load` lève `ValueError` pour un GPX mal formé, un point sans coordonnées, moins de deux points ou une longueur nulle. Une altitude non finie compte comme absente.
- **Carte** : un `.mbtiles` corrompu, vide ou sans tuiles est ignoré, avec un message ; une tuile illisible découverte en roulant manque simplement ([tiles.py:46](../compteur/tiles.py#L46)).
- **Réglages** : `Infinity` redonne les réglages par défaut ; une valeur illisible venue de l'interface est ignorée ; une carte qui refuse d'enregistrer garde le réglage jusqu'à l'arrêt, sans erreur dans l'interface.
- **Vérifié** : [test_app.py](../tests/test_app.py) lance l'appli avec un GPX tronqué, un GPX d'un seul point, un GPX « sur place » et une carte faite de zéros. Elle démarre avec le seul bon parcours et signale les quatre fichiers. Aussi `test_route`, `test_tiles` et `test_settings`.

## 8. Un parcours de longueur nulle divisait par zéro

- **Correction** : `Route` refuse une longueur nulle et un point hors de la carte ([route.py:60](../compteur/route.py#L60)).
- **Piège évité** : le tracé du résumé est lui aussi un `Route`, fait de la trace. Un GPS figé donne des points identiques ; le résumé s'affiche alors sans tracé au lieu d'échouer ([summary.py](../compteur/summary.py)).
- **Vérifié** : `test_route` et `test_summary` (GPS figé pendant une minute).

## 9. Le Pi n'a pas d'horloge sans réseau

- **Inchangé** : le Pi n'a ni pile d'horloge ni `fake-hwclock`. À régler avec le GPS : mettre l'heure du système à celle du GPS, ou dater la sortie avec.
- **Lien avec la reprise** : la durée de la coupure vient de l'horloge du système. Si elle recule (sans réseau), la coupure compte pour zéro ; si elle saute en avant, pour 12 h au plus.
- **Lien avec l'enregistrement** : deux sorties parties à la même seconde (horloge qui a reculé) ne s'écrasent plus : la seconde s'appelle `…-2` (voir plus bas).

## Relecture indépendante des corrections

Une fois tout corrigé, une relecture indépendante de l'ensemble des changements a trouvé un défaut, reproduit, et quelques faiblesses. Tous sont corrigés, chacun avec un essai écrit d'abord, vu en échec, puis réussi.

| Trouvé | Correction | Essai |
|---|---|---|
| Après une coupure sur le résumé, le bandeau « Sortie reprise » s'affichait sur la sortie **suivante**, toute neuve | l'heure de la coupure n'est donnée que pour une sortie reprise en cours ; une nouvelle sortie l'efface aussi | `test_bandeau_de_reprise_jamais_sur_une_nouvelle_sortie` |
| Hors de l'écran, la carte ne chargeait plus ses tuiles : en revenant après 400 m ou plus, elles arrivaient une à une | hors de l'écran, seules les tuiles suivent la position, sans rien dessiner ([MapView.qml](../compteur/ui/MapView.qml)) | « tuiles pas prêtes au retour » : 0, contre 6 sans la correction |
| Après une reprise, le « Temps total » de l'écran ne comptait pas la coupure, le FIT si | le temps total compte toute l'heure qui passe ; seuls le chrono et la distance plafonnent un trou de mesures à 5 s | `test_temps_total_identique_a_l_ecran_et_dans_le_fichier` |
| Une sortie passait pour déjà enregistrée sur la seule seconde du départ ; et une sortie partie à la même seconde en **écrasait** une autre | reconnue à son contenu (départ, temps, distance) ; une sortie enregistrée n'est jamais remplacée | `test_jamais_une_sortie_ecrasee`, `test_sortie_deja_enregistree_reconnue` |
| `--mesure` pouvait effacer un fichier dans `sorties/` | la mesure travaille dans un dossier temporaire | `--mesure` complet : `sorties/` inchangé |
| Écran bloqué sur « Enregistrement » si Mes sorties ne se relisait pas ; résumé modifié à la main qui empêchait de démarrer ; `.tmp` laissés par une coupure ; SIGTERM perdu pendant le démarrage | écran toujours libéré ; résumé mal formé ignoré ; `.tmp` effacés au démarrage ; arrêt passé par la boucle de l'appli | `test_resume_mal_forme_ignore`, `test_fichiers_temporaires_…`, `test_arret_du_systeme_pendant_le_demarrage` |

Rien de sérieux n'a été trouvé ailleurs, en particulier :
- entre le fil de l'interface et le fil d'écriture ;
- dans la durabilité du fichier de reprise ;
- dans la logique de reprise.

## Performance

Mesures du 13/09 au soir sur le Pi, noyau 6.18.39, au rythme réel, sur une sortie simulée identique d'une version à l'autre.

### P1. La carte coûtait même hors de l'écran

- **Correction** : la carte est invisible dès que sa page n'est plus à l'écran ([MapPage.qml:19](../compteur/ui/MapPage.qml#L19)). Rien n'y est alors calculé ni dessiné : ni l'image, ni la trace, ni le glissement ([MapView.qml:143](../compteur/ui/MapView.qml#L143)). La trace n'est même plus lue hors de l'écran.
- Les deux pièges de la revue :
  - « à l'écran » se calcule d'après la position de la page dans le balayage, pas d'après la page courante : la carte réapparaît dès le premier pixel du geste ;
  - en réapparaissant, elle se place et refait son image dans tous les cas ([MapView.qml:95](../compteur/ui/MapView.qml#L95)). Qt la refait déjà de lui-même quand elle redevient visible : c'est une précaution.
- Hors de l'écran, seules les tuiles suivent la position : elles se chargent sur d'autres fils, et la carte réapparaît complète (voir la relecture indépendante).
- **Vérifié** : [test_carte.py](../tests/test_carte.py) compare l'écran à une image de la carte refaite pour l'occasion, dans 7 scénarios : à l'écran, retour après 3 min ailleurs, en plein balayage, zoom, nord en haut, tuiles arrivées hors de l'écran, sortie libre puis parcours. 0 pixel de différence. Il vérifie aussi qu'au retour après 2 km, aucune tuile ne reste à charger. Le test sait échouer : une carte cachée pendant le balayage, une image jamais refaite (jusqu'à 160 000 pixels faux), ou des tuiles pas préchargées (6 en attente) le font échouer.
- **Mesuré sur le Pi**, au rythme réel, même sortie simulée avant et après (noyau 6.18.39) :

  | | Avant | Après |
  |---|---|---|
  | Page principale, parcours, 51 min | 7,7 à 8,6 % | **4,1 %** |
  | Page principale, sortie libre, 5 h | 13,5 % | **3,8 %** |
  | Carte, parcours, 51 min | 19,5 img/s, 30 % | 22 img/s, 32 % |

  Sur la carte elle-même, le coût d'une image ne change pas ; elle en dessine un peu plus, donc plus fluide.

### P2. Longue sortie libre qui repasse sur ses traces

- **Correction** ([model.py:16](../compteur/model.py#L16)) :
  - la trace part par tronçons de 50 points (500 m) au lieu de 200 : seuls ceux qui touchent l'écran sont tracés ;
  - un tronçon fini perd les points dont l'écart ne se voit pas (moins d'un pixel au zoom 16, Douglas-Peucker, distance au segment pour garder les demi-tours) : 24 % des points restent sur une sortie de 5 h ;
  - chaque tronçon est lu une seule fois par la carte ([RideModel.trackChunk](../compteur/model.py#L215)) : un tronçon qui arrive ne fait plus relire ni retracer les autres ;
  - sur parcours, plus aucune trace de sortie libre n'est créée, même cachée.
- **Mesuré sur le Pi**, carte en sortie libre, au rythme réel. Le cycliste simulé tourne en boucle : à 5 h, il est passé plus de trois fois au même endroit.

  | | 51 min | 5 h |
  |---|---|---|
  | Avant | 20,7 img/s, 34 % | 12,2 img/s, 72 % |
  | Carte hors écran corrigée, tronçons de 200 points | 19,3 img/s, 32 % | 12,7 img/s, 74 % |
  | Tronçons de 50 points | 22,5 img/s, 39 % | 12,9 img/s, 75 % |
  | **Tronçons de 50 points allégés (retenu)** | **22,5 img/s, 29 %** | **21,7 img/s, 63 %** |

  - Raccourcir les tronçons ne change presque rien : ce qui coûte, c'est le nombre de points tracés à chaque image, pas la longueur des tronçons.
  - Avec la trace allégée, la carte d'une sortie de 5 h est aussi fluide qu'à 51 min, 22 images par seconde au lieu de 12. Chaque image coûte deux fois moins : 2,9 % d'un cœur au lieu de 5,9.
- **Reste** : 63 % à 5 h, contre 29 % à 51 min. Prochaine piste : mettre les tronçons finis dans l'image de la carte. La revue l'avait trouvée plus chère à 51 min (40 % contre 31 %), à remesurer avec la trace.

### P3. Carte sur parcours à 5 h

- **La piste de la trace cachée était fausse** : supprimer la trace de sortie libre sur parcours (P2) ne change rien à 5 h. Même plan de mesure, avant et après : 24,2 img/s et 58,5 %, contre 24,3 img/s et 58,8 %.
- **La cause est l'endroit du parcours, pas la durée.** À 5 h, le cycliste simulé est au kilomètre 37,6, dans une portion sinueuse : la carte y tourne de 88° en une minute, contre 26° au point mesuré à 51 min. Or chaque pas de rotation visible refait l'image de la carte.
- **La bonne mesure est le coût d'une image.** D'une série à l'autre, au même instant de la même sortie simulée, le processeur varie de 43 à 59 % à 5 h, parce que le nombre d'images dessinées varie (19 à 24 par seconde). Le coût d'une image, lui, est stable, et ne grossit pas avec la durée :

  | Carte sur parcours | Séries | Images/s | Processeur | Par image |
  |---|---|---|---|---|
  | 51 min, portion droite | 2 | 21,9 à 22,5 | 33 à 35 % | 1,5 % |
  | 89 min, km 37,6 (premier tour) | 2 | 17,4 à 18,3 | 44 à 46 % | 2,5 % |
  | 5 h, km 37,6 (quatrième tour) | 4 | 19,4 à 24,3 | 43 à 59 % | 2,2 à 2,4 % |

  « Par image » : part d'un cœur pour une image, soit le processeur divisé par les images par seconde. Le code d'avant les corrections donne les mêmes chiffres à 5 h (24,2 img/s, 58,5 %).
- **Leçon pour les mesures** : comparer le coût par image, ou deux mesures d'une même série. Un chiffre isolé de processeur peut varier de 15 points.
- **Piste, si les virages coûtent trop avec le vrai écran** : refaire l'image de la carte moins souvent en virage, par exemple par pas de rotation plus grands. Cela se voit un peu plus.

### P4. Enregistrer une sortie de 5 h figeait l'écran 3,2 s

- **Correction** : l'encodage du FIT, l'écriture et la relecture de Mes sorties se font sur le fil d'écriture (point 2).
- **Mesuré sur le Pi**, sortie de 5 h (essai d'endurance) : l'écriture prend 4,0 s, à part, et l'écran dessine 196 images pendant ce temps. Le plus long écart entre deux images (264 ms) est l'attente voulue avant d'afficher l'anneau « Enregistrement… » (250 ms), pendant laquelle rien ne change à l'écran. Avant : 3,2 s d'écran figé.

### P5. Miroir plus lent avec l'image de la carte

- **Non traité** : cause non trouvée, et le miroir ne sert qu'en attendant le vrai écran.

## Le Pi

- **Noyau** : retour au noyau stable des paquets le 13/09 (6.18.39+rpt-rpi-v8), en réinstallant le paquet du noyau lui-même, `linux-image-6.18.39+rpt-rpi-v8`, et `raspi-firmware`. Le méta-paquet `linux-image-rpi-v8` ne réinstalle pas le noyau.
  - `kernel8.img`, `initramfs8`, l'arbre du Zero 2 W et l'overlay vc4 sont identiques à ceux du paquet ; la marque de rpi-update est effacée ; `config.txt` est inchangé (`cma-128`).
  - Restes de rpi-update, sans effet : `/lib/modules/6.18.50-v8*` et `/boot/firmware.bak`.
- **Réglages d'essai encore posés** :
  - HDMI forcé en 480×640 dans `cmdline.txt` (`video=HDMI-A-1:480x640M@60D`, sauvegarde `cmdline.txt.avant-compteur`) : à revoir en branchant le vrai écran ;
  - sauvegarde `config.txt.avant-compteur` ;
  - journal permanent (`/etc/systemd/journald.conf.d/90-compteur-tests.conf`).
- **Lancement** : l'appli ne démarre pas encore toute seule au démarrage du Pi. C'est l'étape d'installation ; elle devra passer `recovery` (appli normale) et laisser SIGTERM fermer l'appli.
- **Outils de test** : `pytest` et `garmin-fit-sdk` sont installés dans `~/compteur/.venv`, pour lancer les tests sur le Pi.
- **Essai d'endurance sur le code final** (13/09, 23:21 à 23:38, noyau 6.18.39) : deux sorties de 5 h en accéléré, sur parcours puis en sortie libre, chacune suivie de mesures au rythme réel.
  - Code de sortie 0, aucune erreur du noyau (seulement les avis habituels du démarrage), 52 °C au plus.
  - La sortie sur parcours, enregistrée, donne un FIT valide pour `garmin_fit_sdk` : intégrité (CRC) correcte, aucune erreur, 17 502 points. Distance (128,25 km), temps total (18 131 s) et temps en mouvement (17 502 s) sont identiques dans le FIT et dans le résumé. Pour le fichier de reprise, voir le point 1.

  | À 5 h de sortie | Essai d'avant (noyau 6.18.50) | Code final (noyau 6.18.39) |
  |---|---|---|
  | Carte, parcours | 20,5 img/s, 47 % | 21,9 img/s, 50 % |
  | Page principale, parcours | 2,3 img/s, 10 % | 2,5 img/s, 4 % |
  | Carte, sortie libre | 11,8 img/s, 69 % | **23,5 img/s**, 71 % |
  | Page principale, sortie libre | 2,4 img/s, 14 % | 2,4 img/s, **4 %** |
  | Pic de mémoire | 144 Mo | 149 Mo |
  | Enregistrer la sortie | 3,2 s d'écran figé | 4,0 s à part, écran libre |

## Ordre suivi

- [x] 1. Ne plus jamais perdre une sortie : points 1, 2, 3 et 5.
- [x] 2. « Éteindre » : point 4.
- [x] 3. Carte hors écran : P1.
- [x] 4. Échap et Q (point 6), fichiers invalides (points 7 et 8).
- [x] 5. Longue sortie libre (P2), carte sur parcours à 5 h (P3), enregistrement en arrière-plan (P4).
- [x] 6. Retour au noyau stable, puis nouvel essai d'endurance.

## Outils pour remesurer

- **Tests** : `.venv/bin/python -m pytest -q`, sur le Mac comme sur le Pi (dans `~/compteur`).
- **Piloter l'appli hors écran** : partir de [tests/pilote.py](../tests/pilote.py). Ne jamais attendre avec `QTest.qWait` : il garde Python pour lui pendant l'attente, et le fil qui charge les tuiles, qui passe par Python, bloque tout. Il faut une boucle `QEventLoop`, comme `wait()`.
- **Mesure habituelle** : `.venv/bin/python -m compteur --mesure`, environ 3 minutes, sur le Pi.
- **Scripts dans `~/essais` sur le Pi**, à lancer depuis la copie à mesurer :
  - `campagne.sh` : enchaîne tout ce qui suit, sans rester connecté (`nohup setsid ~/essais/campagne.sh > ~/essais/campagne.log 2>&1 < /dev/null &`) ; journaux dans `~/essais/campagne`. `fin.sh` fait de même pour P3 au même endroit du parcours, puis l'essai d'endurance ;
  - `ab_principale.py` : page principale, carte, puis page principale, à 51 min de parcours (`DUREE` : durée de chaque mesure) ;
  - `mesure_carte.py` : carte et page principale selon la durée de la sortie. `PLAN="libre:51:carte,principale;libre:300:carte"` : une même sortie continue tant que le mode (`libre` ou `parcours`) ne change pas ;
  - `endurance.py` : deux sorties de 5 h en accéléré, sur parcours puis en sortie libre, chacune suivie de mesures au rythme réel. Il garde la sortie dans un vrai fichier de reprise, mesure le temps de le rejouer, et la durée de l'enregistrement avec la plus longue image pendant l'écriture. Les sorties vont dans `~/essais/sorties`. `HEURES` règle la durée ;
  - `profil_longueur.py` : calcul de chaque seconde, découpage de chaque image et ramasse-miettes, à 51 min puis à 5 h. On dépouille avec `python3 ~/essais/depouiller.py ~/essais/profil.log` ;
  - copies : `~/essais/avant` (le code d'avant les corrections), `~/essais/v0` et `v1` (variantes de la trace).
- **Pièges** :
  - toujours `ssh -4` ; si `compteur.local` ne se résout plus (mDNS), passer par l'adresse IP (192.168.1.58) avec `-o HostKeyAlias=compteur.local` : le `known_hosts` du Mac a une autre clé pour cette adresse, laissée par un ancien appareil ;
  - `pgrep -f "[e]ssais/endurance.py"`, avec les crochets, pour ne pas trouver la commande ssh elle-même ;
  - une seule appli à la fois peut tenir l'écran.
- **Vérifier un FIT** : `garmin_fit_sdk` ; `Decoder(...).check_integrity()`, puis `read()` doit renvoyer une liste d'erreurs vide.
