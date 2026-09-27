"""Segments du cache prêts à suivre, avec le record auquel se comparer."""

from datetime import datetime, timedelta

from ..segments import Best, StarredSegment
from ..summary import MONTHS
from .decode import read_splits, segment_route
from .files import as_dict


def reference(entry: dict, records: dict) -> Best | None:
    """Record auquel se comparer : celui de Strava, avec son fantôme, sauf si le compteur a fait mieux depuis. Le record
    du compteur tient tant que Strava donne encore celui qu'il a battu ; dès que Strava en donne un autre (la sortie
    envoyée, en principe), c'est son temps qui fait foi."""
    pr = as_dict(entry.get("pr"))
    strava_s = pr.get("elapsed_s")
    local = as_dict(records.get(str(entry.get("id"))))
    if local and local.get("strava_pr_s") == strava_s:
        try:
            if strava_s is None or float(local["elapsed_s"]) < float(strava_s):
                return Best(float(local["elapsed_s"]), read_splits(local.get("splits")), local.get("date"))
        except (TypeError, KeyError, ValueError):
            pass  # record du compteur illisible : celui de Strava
    if not isinstance(strava_s, (int, float)) or strava_s <= 0:
        return None
    ghost = as_dict(entry.get("ghost"))
    splits = read_splits(ghost.get("splits")) if ghost.get("activity_id") == pr.get("activity_id") else ()
    return Best(float(strava_s), splits, pr.get("date"))


def starred_segments(cache: dict, records: dict | None = None) -> list[StarredSegment]:
    """Les segments du cache, prêts à suivre, avec leur record (`records` : ceux battus avec le compteur). Neufs à
    chaque appel : une sortie change leur record. Un segment sans tracé (pas encore arrivé) est laissé de côté."""
    entries = cache.get("segments")
    if not isinstance(entries, list):
        return []
    female = as_dict(cache.get("athlete")).get("sex") == "F"
    segments = []
    for entry in entries:
        try:
            kom_s = entry.get("qom_s" if female else "kom_s")
            segments.append(StarredSegment(int(entry["id"]), str(entry["name"]), segment_route(entry),
                                           pr=reference(entry, records or {}),
                                           kom=Best(float(kom_s)) if kom_s else None))
        except (TypeError, KeyError, ValueError, AttributeError):
            continue
    return segments


def kom_label(cache: dict) -> str:
    """KOM ou QOM, selon le profil Strava."""
    return "QOM" if as_dict(cache.get("athlete")).get("sex") == "F" else "KOM"


def synced_text(timestamp: object, now: datetime | None = None) -> str:
    """Moment de la dernière synchro : « aujourd'hui à 09:41 », « hier à 18:02 », « le 3 juin »."""
    if not isinstance(timestamp, (int, float)) or timestamp <= 0:
        return ""
    when = datetime.fromtimestamp(timestamp)
    today = (now or datetime.now()).date()
    if when.date() == today:
        return f"aujourd'hui à {when:%H:%M}"
    if when.date() == today - timedelta(days=1):
        return f"hier à {when:%H:%M}"
    return f"le {when.day} {MONTHS[when.month - 1]}"
