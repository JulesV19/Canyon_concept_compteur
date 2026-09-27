"""Liaison Bluetooth avec l'iPhone, sans puce MFi : notifications (appels, SMS, WhatsApp) et musique.

L'iPhone ouvre deux services Bluetooth basse consommation à tout appareil appairé :
- ANCS (Apple Notification Center Service) : chaque notification (appli, titre, texte), avec ses actions
  « oui / non » : décrocher ou refuser un appel ;
- AMS (Apple Media Service) : le morceau en cours (titre, artiste, album, durée, position) et les commandes
  (lecture, pause, suivant, précédent, volume). Pas de pochette.

Le compteur se présente en « périphérique » qui demande ANCS : l'iPhone le montre alors dans Réglages > Bluetooth.
On l'appaire une fois ; ensuite l'iPhone se reconnecte seul dès que le compteur est en marche.

- `ancs.py`, `ams.py` : décodage des deux services, sans dépendance ;
- `state.py` : ce que l'iPhone a envoyé, partagé entre le fil Bluetooth et l'interface ;
- `views.py` : les listes que montre l'écran ;
- `link.py` : la liaison, par BlueZ sur D-Bus (dbus-fast, Linux seul), dans un fil à part ;
- `__main__.py` : essai en ligne de commande, `python -m compteur.iphone` sur le Pi.
"""

from .ams import *  # noqa: F401,F403
from .ancs import *  # noqa: F401,F403
from .link import Link  # noqa: F401
from .state import PhoneState, State  # noqa: F401
from .views import *  # noqa: F401,F403
