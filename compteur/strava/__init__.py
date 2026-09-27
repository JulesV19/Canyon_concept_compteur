"""Strava : les segments en favori, gardés sur la carte SD pour rouler sans réseau, et leur synchro.

tools/strava/connecter.py relie une fois pour toutes l'appareil au compte : ses jetons sont dans
~/.config/canyon-compteur/strava.json, les segments dans segments.json, à côté, et les records battus avec le compteur
dans records.json. La synchro ne relit que ce qui manque ou a vieilli, car Strava limite les lectures (100 par quart
d'heure). Elle passe par son propre fil : l'écran n'attend jamais le réseau, et une synchro lente ne retarde pas
l'écriture des sorties.

- `files.py` : les fichiers sur la carte SD ;
- `client.py` : l'API de Strava ;
- `decode.py` : ses réponses et les entrées du cache ;
- `sync.py` : la synchro ;
- `segments.py` : les segments prêts à suivre, avec leur record ;
- `model.py` : `StravaModel`, pour l'interface.
"""

from .client import API_URL, TOKEN_URL, Client, SyncError  # noqa: F401
from .decode import parse_time  # noqa: F401
from .files import CACHE_FILE, RECORDS_FILE, STRAVA_DIR, TOKENS_FILE, load_cache, save_tokens  # noqa: F401
from .model import ROW_PROFILE_POINTS, StravaModel  # noqa: F401
from .segments import kom_label, starred_segments, synced_text  # noqa: F401
from .sync import sync  # noqa: F401
