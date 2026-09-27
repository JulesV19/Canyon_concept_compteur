"""GPS Adafruit Mini GPS PA1010D (puce MediaTek), sur le bus I2C : position, vitesse, cap, altitude, heure UTC, et
l'état de la réception (satellites dans le ciel et leur signal, précision).

Le GPS prépare chaque seconde des lignes de texte NMEA ; le compteur les lit sur le bus, par morceaux, dans un fil à
part. Quand il n'a rien à envoyer, le GPS répond par des sauts de ligne (0x0A). Un seul lecteur à la fois : deux
programmes qui lisent le GPS se partageraient ses lignes.

- `nmea.py` : le format des lignes et des commandes ;
- `fix.py` : ce que le GPS sait (satellites, position, heure) ;
- `reader.py` : des octets lus aux lignes, puis au Fix ;
- `receiver.py` : la lecture en continu, dans un fil à part ;
- `status.py`, `clock.py` : l'état pour l'écran, l'heure pour l'horloge du système ;
- `rider.py` : les mesures de la sortie.
"""

from .clock import CLOCK_TOLERANCE_S, ClockCheck  # noqa: F401
from .fix import Fix, Satellite  # noqa: F401
from .nmea import KNOT_MPS, OUTPUT, QUERY_FIRMWARE, checksum, command, coordinate, parse  # noqa: F401
from .reader import NmeaReader  # noqa: F401
from .receiver import ADDRESS, STALE_S, Receiver  # noqa: F401
from .rider import GpsRider  # noqa: F401
from .status import ACCURACY_M_PER_HDOP, Status, bars  # noqa: F401
