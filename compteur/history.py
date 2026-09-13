"""Historique des sorties : chaque sortie enregistrée donne un fichier FIT (à déposer sur Strava
ou Garmin Connect) et son résumé en JSON (pour l'écran du compteur), dans le dossier sorties/."""

import json
from datetime import datetime
from pathlib import Path

from .fit import encode_activity
from .ride import Ride
from .storage import write_atomic

RIDES_DIR = Path(__file__).resolve().parent.parent / "sorties"


def ride_id(started_at: datetime) -> str:
    """Identifiant d'une sortie, qui nomme ses fichiers : la date et l'heure du départ, `AAAA-MM-JJ_HH-MM-SS`."""
    return started_at.strftime("%Y-%m-%d_%H-%M-%S")


def save(ride: Ride, summary: dict, started_at: datetime, folder: Path = RIDES_DIR) -> Path:
    """Enregistre la sortie : son fichier FIT et son résumé `.json`, chacun écrit d'un coup et forcé sur la carte.
    Renvoie le fichier FIT. En cas d'échec, l'erreur remonte, sans fichier temporaire laissé derrière. Une sortie
    enregistrée n'est jamais remplacée : partie à la même seconde (horloge qui a reculé), la nouvelle s'appelle `…-2`."""
    folder.mkdir(parents=True, exist_ok=True)
    base = stem = ride_id(started_at)
    number = 1
    while (folder / f"{stem}.json").exists():
        number += 1
        stem = f"{base}-{number}"
    fit_path = folder / f"{stem}.fit"
    write_atomic(fit_path, encode_activity(ride, started_at))
    # Le résumé en dernier : sa présence dit que la sortie est complète
    summary = summary | {"file": fit_path.name}
    write_atomic(folder / f"{stem}.json", json.dumps(summary, ensure_ascii=False).encode("utf-8"))
    return fit_path


def find_saved(summary: dict, folder: Path = RIDES_DIR) -> str | None:
    """Identifiant de la sortie enregistrée qui a ce résumé (même départ, même temps, même distance), ou None."""
    base = ride_id(datetime.fromisoformat(summary["startedAt"]))
    for path in sorted(folder.glob(f"{base}*.json")):
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(saved, dict) and all(saved.get(key) == summary.get(key)
                                           for key in ("startedAt", "timerS", "distanceKm")):
            return path.stem
    return None


def remove_orphans(started_at: datetime, folder: Path = RIDES_DIR) -> None:
    """Efface les fichiers FIT de cette seconde de départ restés sans résumé : un enregistrement raté."""
    for path in folder.glob(f"{ride_id(started_at)}*.fit"):
        if not path.with_suffix(".json").exists():
            path.unlink(missing_ok=True)


def clean(folder: Path = RIDES_DIR) -> None:
    """Efface les fichiers temporaires qu'une coupure en plein enregistrement a pu laisser."""
    for path in folder.glob("*.tmp"):
        try:
            path.unlink()
        except OSError:
            pass


def load(folder: Path = RIDES_DIR) -> list[dict]:
    """Résumés des sorties enregistrées, de la plus récente à la plus ancienne, chacun avec son identifiant
    `id` (le nom de ses fichiers). Un résumé illisible est ignoré."""
    rides = []
    for path in sorted(folder.glob("*.json"), reverse=True):
        try:
            summary = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(summary, dict):
            rides.append(summary | {"id": path.stem})
    return rides


def remove(ride_id: str, folder: Path = RIDES_DIR) -> None:
    """Supprime une sortie : son résumé d'abord (elle disparaît de l'historique), puis son fichier FIT."""
    for suffix in (".json", ".fit"):
        (folder / f"{ride_id}{suffix}").unlink(missing_ok=True)
