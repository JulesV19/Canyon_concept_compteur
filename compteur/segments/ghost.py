"""Le fantôme d'un record : ses temps de passage, retrouvés dans sa sortie."""

from collections.abc import Iterable

from ..ride import Sample
from ..route import Route
from .efforts import StarredSegment
from .tracker import SegmentTracker

GHOST_TOLERANCE = 0.1         # passage du record retrouvé dans sa sortie : à 10 % de son temps près...
GHOST_TOLERANCE_S = 5.0       # ... et au moins 5 s (le compteur et Strava ne coupent pas la ligne pile au même endroit)


def record_splits(route: Route, samples: Iterable[Sample], elapsed_s: float) -> tuple[tuple[float, float], ...]:
    """Temps de passage d'un record, retrouvés en rejouant sa sortie avec le même moteur qu'en direct. Une sortie peut
    passer plusieurs fois sur le segment (des tours de Longchamp) : c'est le passage au temps le plus proche de celui
    du record. Vide si aucun ne colle."""
    tracker = SegmentTracker([StarredSegment(0, route.name, route)])
    for sample in samples:
        tracker.update(sample)
    tolerance = max(GHOST_TOLERANCE_S, GHOST_TOLERANCE * elapsed_s)
    passes = [result for result in tracker.results if abs(result.elapsed_s - elapsed_s) <= tolerance]
    return min(passes, key=lambda result: abs(result.elapsed_s - elapsed_s)).splits if passes else ()
