"""Les fichiers de Strava sur la carte SD : jetons, segments en favori, records battus avec le compteur."""

import json
from pathlib import Path

from ..storage import write_atomic

STRAVA_DIR = Path.home() / ".config" / "canyon-compteur"
TOKENS_FILE = "strava.json"   # jetons d'accès, posés par tools/strava/connecter.py
CACHE_FILE = "segments.json"  # segments en favori, tels qu'à la dernière synchro
RECORDS_FILE = "records.json"  # records battus avec le compteur, en attendant que Strava les donne


def as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def save_tokens(path: Path, tokens: dict) -> None:
    """Écrit les jetons, lisibles par leur seul propriétaire."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(path, json.dumps(tokens, indent=2).encode("utf-8"), mode=0o600)


def load_cache(path: Path) -> dict:
    """Le cache des segments (ou les records du compteur) ; vide s'il manque ou est illisible."""
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return as_dict(cache)
