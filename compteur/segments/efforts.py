"""Les données d'un segment : temps de référence, segment en favori, passage, résultat, événements."""

import bisect
from dataclasses import dataclass, field

from ..ride import Average
from ..route import Route
from .geo import distance_m

START_RADIUS_M = 25.0         # la ligne de départ se franchit à moins de 25 m du début du segment


@dataclass(frozen=True)
class Best:
    """Temps de référence sur un segment : record perso, ou KOM/QOM. `splits` : temps de passage (distance depuis le
    départ, temps depuis le départ), croissants ; sans eux, on suppose une allure régulière."""

    elapsed_s: float
    splits: tuple[tuple[float, float], ...] = ()
    date: str | None = None  # AAAA-MM-JJ

    def time_at(self, along_m: float, length_m: float) -> float:
        """Temps mis pour arriver à `along_m` du départ. Les temps de passage sont ramenés à la longueur du segment et
        au temps total : le fantôme arrive pile avec le record."""
        fraction = min(max(along_m / length_m, 0.0), 1.0) if length_m > 0 else 1.0
        splits = self.splits
        if len(splits) < 2 or splits[-1][0] <= 0 or splits[-1][1] <= 0:
            return self.elapsed_s * fraction
        target = fraction * splits[-1][0]
        i = min(max(bisect.bisect_left(splits, target, key=lambda split: split[0]), 1), len(splits) - 1)
        (d0, t0), (d1, t1) = splits[i - 1], splits[i]
        t = t0 if d1 <= d0 else t0 + (t1 - t0) * (target - d0) / (d1 - d0)
        return max(t, 0.0) * self.elapsed_s / splits[-1][1]


@dataclass
class StarredSegment:
    """Un segment en favori : sa géométrie, et les temps auxquels se comparer."""

    id: int
    name: str
    route: Route
    pr: Best | None = None   # record perso
    kom: Best | None = None  # KOM ou QOM, selon le profil Strava

    @property
    def length_m(self) -> float:
        return self.route.length_m

    @property
    def loop(self) -> bool:
        """Boucle qui finit sur sa ligne de départ, comme Longchamp : les tours s'enchaînent."""
        start, end = self.route.points[0], self.route.points[-1]
        return distance_m(start.lat, start.lon, end.lat, end.lon) <= START_RADIUS_M


@dataclass
class Effort:
    """Un passage sur un segment, de la ligne de départ à l'arrivée (ou à l'abandon)."""

    segment: StarredSegment
    start_t: float                 # franchissement de la ligne (horloge des mesures)
    now_t: float                   # dernière mesure
    pr: Best | None                # record au départ : la comparaison ne change pas en route
    along_m: float = 0.0           # distance faite le long du segment
    max_along_m: float = 0.0
    confirmed: bool = False        # assez de chemin fait pour l'annoncer
    off_since: float | None = None  # hors du segment depuis
    heart_rate: Average = field(default_factory=Average)
    splits: list[tuple[float, float]] = field(default_factory=list)  # temps de passage, pour le prochain fantôme

    @property
    def elapsed_s(self) -> float:
        return self.now_t - self.start_t

    @property
    def remaining_m(self) -> float:
        return max(self.segment.length_m - self.along_m, 0.0)

    def gap_s(self, best: Best | None) -> float | None:
        """Écart à ce temps de référence au même point du segment : négatif en avance, positif en retard."""
        return None if best is None else self.elapsed_s - best.time_at(self.along_m, self.segment.length_m)

    @property
    def pr_gap_s(self) -> float | None:
        return self.gap_s(self.pr)

    @property
    def kom_gap_s(self) -> float | None:
        return self.gap_s(self.segment.kom)

    @property
    def avg_speed_mps(self) -> float | None:
        return self.along_m / self.elapsed_s if self.elapsed_s > 0 else None


@dataclass(frozen=True)
class Result:
    """Un segment fini."""

    segment: StarredSegment
    elapsed_s: float
    pr_gap_s: float | None   # écart au record d'avant (négatif : battu) ; None au premier passage
    kom_gap_s: float | None
    new_record: bool         # record battu, ou premier temps
    avg_speed_mps: float
    avg_heart_rate: float | None
    max_heart_rate: float | None
    pr: Best | None = None   # record d'avant
    splits: tuple[tuple[float, float], ...] = ()  # temps de passage de ce passage-ci


# Ce que renvoie SegmentTracker.update
@dataclass(frozen=True)
class Approach:
    segment: StarredSegment
    distance_m: float  # distance au départ, à vol d'oiseau


@dataclass(frozen=True)
class Start:
    effort: Effort


@dataclass(frozen=True)
class Finish:
    result: Result


@dataclass(frozen=True)
class Abandon:
    effort: Effort
