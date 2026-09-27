"""Pont entre le backend Python et l'interface QML.

- `ride.py` : la sortie en cours (valeurs, trace, profils, tours, segments) ;
- `values.py`, `segments.py`, `track.py`, `units.py` : ce que `ride.py` calcule pour l'écran ;
- `battery.py`, `gps.py`, `phone.py` : la batterie, le GPS et l'iPhone.
"""

from .battery import BatteryModel  # noqa: F401
from .gps import GpsModel  # noqa: F401
from .phone import PhoneModel  # noqa: F401
from .ride import RideModel  # noqa: F401
from .segments import segment_card  # noqa: F401
from .track import simplified  # noqa: F401
from .values import route_progress, snapshot  # noqa: F401
