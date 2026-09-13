# Matériel

## Composants

| Élément | Choix | Remarques |
|---|---|---|
| Carte | Raspberry Pi Zero 2 W | 4 cœurs + GPU : nécessaire pour une interface fluide (le Zero W d'origine est trop faible) |
| Écran | Écran 2,8" DPI 480×640, IPS, tactile capacitif, vitre trempée (ex. Waveshare 2,8" DPI LCD) | Branché en DPI sur les GPIO : l'image sort directement du GPU |
| GPS | Module u-blox M10 (ou M8) avec sortie USB | En USB car l'écran occupe le port série (voir plus bas) |
| Capteurs | Ceinture cardio, capteur vitesse/cadence, capteur de puissance en Bluetooth (BLE) | Bluetooth intégré au Pi, pas besoin d'ANT+ |
| Baromètre (option) | BMP390 ou BMP280 (I2C) | Altitude, pente et dénivelé bien plus précis qu'avec le GPS |
| Boutons | 3 boutons étanches : Start/Pause, Lap, Page | En secours du tactile (pluie, gants) |
| Batterie | LiPo 3000 à 4000 mAh + carte de charge USB-C avec sortie 5 V | Ajouter une jauge (MAX17048, I2C) pour afficher le pourcentage |
| Horloge (option) | Module RTC (DS3231) | Heure juste dès l'allumage, avant que le GPS capte |
| Boîtier | Impression 3D, fixation Garmin quart de tour | Se monte sur le support du cockpit Canyon |

## Points d'attention

- **Lisibilité au soleil** : un écran IPS classique fait 300 à 500 nits, c'est moins lisible en plein soleil qu'un Garmin. D'où le thème sombre à fort contraste et les gros chiffres. Un film anti-reflet aide aussi. Vérifier la luminosité avant d'acheter (viser 500 nits ou plus).
- **Broches GPIO** : l'écran DPI utilise les GPIO 0 à 21, donc aussi le port série (GPIO 14/15) et le bus I2C principal (GPIO 2/3). D'où le GPS en USB. Boutons, baromètre et jauge iront sur les broches restantes : à confirmer avec le brochage de l'écran choisi avant de câbler.
- **Autonomie** : le Pi et l'écran rétroéclairé consomment environ 2 W, soit 4 à 6 h avec 3000 à 4000 mAh (à mesurer). Leviers : luminosité du rétroéclairage, Wi-Fi coupé pendant la sortie, interface qui ne se redessine que quand une valeur change (fait : voir le README, et `python -m compteur --mesure` pour le vérifier sur le Pi).
- **Mémoire du GPU** : le Zero 2 W n'a que 512 Mo, partagés avec le GPU. Il faut réserver 128 Mo au GPU (`dtoverlay=vc4-kms-v3d,cma-128`) : avec les 256 Mo par défaut, le Pi se fige au changement de page.
- **Tactile sous la pluie** : les gouttes provoquent de faux appuis. Il faudra un verrouillage du tactile, les boutons physiques restant toujours actifs.
- **Étanchéité** : joint autour de la vitre, boutons IP67, prise USB-C avec cache.
