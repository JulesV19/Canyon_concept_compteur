"""Distances et caps sur la Terre, à courte distance."""

import math

from ..route import EARTH_RADIUS_M


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance entre deux points proches, en projection plane locale."""
    kx = math.radians(1) * EARTH_RADIUS_M * math.cos(math.radians((lat1 + lat2) / 2))
    ky = math.radians(1) * EARTH_RADIUS_M
    return math.hypot((lon2 - lon1) * kx, (lat2 - lat1) * ky)


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Cap pour aller du premier point au second, en degrés (0 = nord)."""
    kx = math.cos(math.radians((lat1 + lat2) / 2))
    return math.degrees(math.atan2((lon2 - lon1) * kx, lat2 - lat1)) % 360


def angle_between(a: float, b: float) -> float:
    """Écart entre deux caps, de 0 à 180°."""
    return abs((a - b + 180) % 360 - 180)
