"""Segments Strava en direct : annonce à l'approche, départ, suivi de l'effort, arrivée ou abandon.

Indépendant de Qt et du matériel, comme ride.py : on lui passe les mesures (Sample), il suit chaque segment en favori.
La géométrie d'un segment est un parcours (route.py) : position le long du tracé, écart au tracé. Le chrono d'un
segment est le temps écoulé, pauses comprises, comme sur Strava.

- `geo.py` : distances et caps ;
- `efforts.py` : segment, temps de référence, passage, résultat, et ce que renvoie le suivi ;
- `tracker.py` : le suivi, mesure après mesure ;
- `ghost.py` : les temps de passage d'un record.
"""

from .efforts import (START_RADIUS_M, Abandon, Approach, Best, Effort, Finish, Result, StarredSegment,  # noqa: F401
                      Start)
from .ghost import record_splits  # noqa: F401
from .tracker import APPROACH_M, SegmentTracker  # noqa: F401
