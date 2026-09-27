"""Valeurs de la sortie et du parcours, dans les unités de l'écran."""

from ..ride import HR_ZONE_BOUNDS, Ride, Segment
from ..route import OFF_ROUTE_M, Position, Route
from .units import kmh


def lap_summary(lap: Segment) -> dict:
    return {
        "number": lap.number,
        "timerS": lap.timer_s,
        "distanceKm": lap.distance_m / 1000,
        "avgSpeedKmh": kmh(lap.avg_speed_mps),
        "avgHeartRate": lap.heart_rate.mean,
        "ascentM": lap.ascent_m,
    }


def snapshot(ride: Ride) -> dict:
    """Toutes les valeurs affichables, dans les unités de l'écran."""
    now = ride.current
    total = ride.total
    heart_rate = now.heart_rate if now else None
    return {
        "state": ride.state.value,
        "autoPaused": ride.auto_paused,
        # Instantané
        "speedKmh": kmh(now.speed_mps) if now else None,
        "heartRate": heart_rate,
        "hrZone": ride.hr_zone(heart_rate),
        "altitudeM": now.altitude_m if now else None,
        "gradePct": ride.grade_pct,
        # Sortie complète
        "timerS": total.timer_s,
        "elapsedS": ride.elapsed_s,
        "distanceKm": total.distance_m / 1000,
        "avgSpeedKmh": kmh(total.avg_speed_mps),
        "maxSpeedKmh": kmh(total.max_speed_mps),
        "avgHeartRate": total.heart_rate.mean,
        "maxHeartRate": total.heart_rate.max,
        "ascentM": total.ascent_m,
        "descentM": total.descent_m,
        "hrZonesS": list(ride.hr_zone_s),  # temps passé dans chaque zone cardio
        # Début des zones 2 à 5, en bpm, non arrondi : l'écran classe chaque mesure comme le moteur
        "hrZoneBounds": [bound * ride.max_hr for bound in HR_ZONE_BOUNDS],
        # Tour en cours
        "lap": lap_summary(ride.current_lap),
    }


def route_progress(route: Route | None, position: Position | None) -> dict:
    """Avancement sur le parcours suivi (rien sans parcours)."""
    if route is None:
        return {}
    done = position.along_m if position else 0.0
    return {
        "routeName": route.name,
        "routeKm": route.length_m / 1000,
        "routeAscentM": route.ascent_m,
        "routeDoneKm": done / 1000,
        "routeRemainingKm": (route.length_m - done) / 1000,
        "routeAscentLeftM": route.ascent_after(done),
        "routeProgress": done / route.length_m,
        "offRoute": position is not None and position.offset_m > OFF_ROUTE_M,
    }
