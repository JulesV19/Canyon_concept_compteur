"""Résumé d'une sortie terminée : ce que montre l'écran de fin, et ce que garde l'historique.

Pas de Qt ici : le résumé est un dictionnaire de valeurs simples, prêt à être écrit en JSON.
"""

from datetime import datetime

from .ride import Ride, Segment
from .route import Point, Route

OUTLINE_POINTS = 160  # points du tracé miniature
PROFILE_POINTS = 120  # points du profil d'altitude

DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre")


def _kmh(mps: float | None) -> float | None:
    return None if mps is None else mps * 3.6


def date_text(when: datetime) -> str:
    """Date et heure lisibles : « Vendredi 11 septembre · 15:12 »."""
    return f"{DAYS[when.weekday()].capitalize()} {when.day} {MONTHS[when.month - 1]} · {when:%H:%M}"


def track_outline(track: list[tuple[float, float]], points: int = OUTLINE_POINTS) -> list[tuple[float, float]]:
    """La trace ramenée entre 0 et 1, nord en haut, comme les tracés des parcours de l'accueil. Vide si elle ne se
    dessine pas : moins de deux points, ou tous au même endroit (GPS figé)."""
    try:
        return Route("trace", [Point(lat, lon) for lat, lon in track]).outline(points)
    except ValueError:
        return []


def thinned(values: list, count: int) -> list:
    """Au plus `count` valeurs, prises à intervalles réguliers (la première et la dernière comprises)."""
    if len(values) <= count:
        return list(values)
    return [values[round(i * (len(values) - 1) / (count - 1))] for i in range(count)]


def _lap(lap: Segment) -> dict:
    return {
        "number": lap.number,
        "timerS": lap.timer_s,
        "distanceKm": lap.distance_m / 1000,
        "avgSpeedKmh": _kmh(lap.avg_speed_mps),
        "avgHeartRate": lap.heart_rate.mean,
    }


def ride_summary(ride: Ride, name: str, started_at: datetime) -> dict:
    """Résumé de la sortie : nom (parcours ou « Sortie libre »), date, chiffres clés et maximums,
    temps par zone cardio, tracé ramené entre 0 et 1, profil (km, m) et tours."""
    total = ride.total
    return {
        "name": name,
        "startedAt": started_at.isoformat(timespec="seconds"),
        "dateText": date_text(started_at),
        "distanceKm": total.distance_m / 1000,
        "timerS": total.timer_s,
        "elapsedS": ride.elapsed_s,
        "avgSpeedKmh": _kmh(total.avg_speed_mps),
        "maxSpeedKmh": _kmh(total.max_speed_mps) if total.timer_s else None,
        "ascentM": total.ascent_m,
        "descentM": total.descent_m,
        "avgHeartRate": total.heart_rate.mean,
        "maxHeartRate": total.heart_rate.max,
        "hrZonesS": list(ride.hr_zone_s),
        "outline": track_outline(ride.track),
        "profile": [(d / 1000, ele) for d, ele in thinned(ride.profile, PROFILE_POINTS)],
        # Sans le tour vide d'une sortie terminée juste après Lap
        "laps": [_lap(lap) for lap in ride.laps if lap.timer_s > 0],
    }
