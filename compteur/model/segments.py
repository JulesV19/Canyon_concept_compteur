"""Segments Strava pour l'écran : fiche, passage en cours, résultat, profil."""

from PySide6.QtCore import QPointF

from ..segments import Result, SegmentTracker, StarredSegment
from .units import kmh

SEGMENT_PROFILE_STEP_M = 50.0  # profil d'un segment : un point tous les 50 m


def segment_card(segment: StarredSegment, kom_label: str) -> dict:
    """Ce qui ne change pas d'un passage à l'autre : nom, longueur, pente moyenne, record, KOM ou QOM."""
    first, last = segment.route.points[0].ele, segment.route.points[-1].ele
    return {
        "id": segment.id,
        "name": segment.name,
        "lengthKm": segment.length_m / 1000,
        "gradePct": None if first is None or last is None else (last - first) / segment.length_m * 100,
        "prS": segment.pr.elapsed_s if segment.pr else None,
        "komLabel": kom_label,
        "komS": segment.kom.elapsed_s if segment.kom else None,
    }


def segment_progress(tracker: SegmentTracker, kom_label: str) -> dict:
    """Segment annoncé (distance à son départ) et passage en cours (celui qui finit le premier)."""
    values = {}
    if tracker.approach is not None:
        values["segmentApproach"] = segment_card(tracker.approach.segment, kom_label) | {
            "distanceM": tracker.approach.distance_m}
    active = tracker.active
    if active:
        effort = active[0]
        values["segment"] = segment_card(effort.segment, kom_label) | {
            "prS": effort.pr.elapsed_s if effort.pr else None,  # record au départ du passage
            "elapsedS": effort.elapsed_s,
            "gapS": effort.pr_gap_s,
            "komGapS": effort.kom_gap_s,
            "doneKm": effort.along_m / 1000,
            "remainingKm": effort.remaining_m / 1000,
            "progress": effort.along_m / effort.segment.length_m,
            "avgSpeedKmh": kmh(effort.avg_speed_mps),
        }
    return values


def segment_result(result: Result, kom_label: str) -> dict:
    """Un segment fini, pour l'écran d'arrivée."""
    before = result.pr
    return segment_card(result.segment, kom_label) | {
        "elapsedS": result.elapsed_s,
        "gapS": result.pr_gap_s,
        "newRecord": result.new_record,
        "prS": before.elapsed_s if before else None,  # record d'avant
        "prDate": before.date if before else None,
        "komGapS": result.kom_gap_s,
        "avgSpeedKmh": kmh(result.avg_speed_mps),
        "avgHeartRate": result.avg_heart_rate,
        "maxHeartRate": result.max_heart_rate,
    }


def segment_profile(segment: StarredSegment) -> list[QPointF]:
    """Profil du segment (km, m), un point tous les 50 m (au moins 10) ; vide sans altitudes."""
    steps = max(10, round(segment.length_m / SEGMENT_PROFILE_STEP_M)) + 1
    return [QPointF(d / 1000, ele) for d, ele in segment.route.profile(steps)]
