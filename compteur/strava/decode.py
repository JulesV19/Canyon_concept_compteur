"""Réponses de Strava et entrées du cache : temps, records, tracés, fantômes."""

import math

from ..ride import Sample
from ..route import Point, Route
from ..segments import record_splits
from .client import SyncError
from .files import as_dict


def parse_time(text: object) -> float | None:
    """Un temps tel que Strava l'affiche (« 58s », « 4:37 », « 1:02:03 »), en secondes ; None s'il est illisible."""
    if not isinstance(text, str):
        return None
    text = text.strip().lower()
    try:
        if text.endswith("s"):
            seconds = float(text[:-1])
        else:
            parts = text.split(":")
            if len(parts) > 3:
                return None
            seconds = 0.0
            for part in parts:
                seconds = seconds * 60 + float(part)
    except ValueError:
        return None
    return seconds if math.isfinite(seconds) and seconds > 0 else None


def personal_record(segment: dict) -> dict | None:
    """Record perso, s'il est dans la réponse (Strava le réserve peut-être aux abonnés)."""
    effort = as_dict(segment.get("athlete_pr_effort"))
    stats = as_dict(segment.get("athlete_segment_stats"))
    elapsed = effort.get("elapsed_time") or stats.get("pr_elapsed_time")
    if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed <= 0:
        return None
    date = effort.get("start_date_local") or stats.get("pr_date")
    return {"elapsed_s": float(elapsed), "date": date[:10] if isinstance(date, str) and date else None,
            "activity_id": effort.get("activity_id") or stats.get("pr_activity_id"), "effort_id": effort.get("id")}


def by_type(streams: object) -> dict:
    """Flux Strava rangés par type (ils arrivent en liste sans key_by_type)."""
    if isinstance(streams, list):
        return {stream.get("type"): stream for stream in streams if isinstance(stream, dict)}
    return as_dict(streams)


def segment_points(streams: object) -> list[list]:
    """Tracé d'un segment, [lat, lon, altitude] point par point, depuis ses flux Strava."""
    streams = by_type(streams)
    try:
        points = [[round(float(lat), 6), round(float(lon), 6), None] for lat, lon in streams["latlng"]["data"]]
        altitude = as_dict(streams.get("altitude")).get("data") or []
        if len(altitude) == len(points):
            for point, ele in zip(points, altitude):
                point[2] = round(float(ele), 1)
    except (TypeError, KeyError, ValueError, AttributeError) as error:
        raise SyncError("réponse de Strava illisible") from error
    return points


def ride_samples(streams: object) -> list[Sample]:
    """Une sortie, mesure par mesure (heure et position), depuis ses flux Strava ; vide sans positions."""
    streams = by_type(streams)
    try:
        return [Sample(t=float(t), lat=float(lat), lon=float(lon))
                for t, (lat, lon) in zip(streams["time"]["data"], streams["latlng"]["data"])]
    except (TypeError, KeyError, ValueError, AttributeError):
        return []


def segment_route(entry: dict) -> Route:
    """Tracé d'un segment du cache ; TypeError, KeyError ou ValueError s'il est incomplet."""
    name = str(entry["name"])
    return Route(name, [Point(float(lat), float(lon), None if ele is None else float(ele))
                        for lat, lon, ele in entry["points"]])


def rounded_splits(splits) -> list[list[float]]:
    return [[round(d, 1), round(t, 1)] for d, t in splits]


def read_splits(value: object) -> tuple[tuple[float, float], ...]:
    try:
        return tuple((float(d), float(t)) for d, t in value)
    except (TypeError, ValueError):
        return ()


def ghost_splits(entry: dict, streams: object) -> list[list[float]]:
    """Fantôme du record : ses temps de passage, retrouvés dans la sortie du record (voir segments.record_splits)."""
    try:
        route, elapsed = segment_route(entry), float(entry["pr"]["elapsed_s"])
    except (TypeError, KeyError, ValueError):
        return []
    return rounded_splits(record_splits(route, ride_samples(streams), elapsed))


def athlete_fields(data: dict) -> dict:
    return {key: data.get(key) for key in ("id", "firstname", "sex")}
