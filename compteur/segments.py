"""Segments Strava en direct : annonce à l'approche, départ, suivi de l'effort, arrivée ou abandon.

Indépendant de Qt et du matériel, comme ride.py : on lui passe les mesures (Sample), il suit chaque segment en favori.
La géométrie d'un segment est un parcours (route.py) : position le long du tracé, écart au tracé. Le chrono d'un
segment est le temps écoulé, pauses comprises, comme sur Strava.
"""

import bisect
import math
from collections.abc import Iterable
from dataclasses import dataclass, field

from .ride import MAX_GAP_S, Average, Sample
from .route import EARTH_RADIUS_M, OFF_ROUTE_M, Route

APPROACH_M = 300.0            # annonce à 300 m du départ, à vol d'oiseau
APPROACH_END_M = 30.0         # l'annonce s'efface quand on s'éloigne de 30 m du départ
NEAR_START_M = 60.0           # près du départ, on guette le passage de la ligne
START_RADIUS_M = 25.0         # la ligne de départ se franchit à moins de 25 m du début du segment
CONFIRM_M = 20.0              # un effort n'est annoncé qu'après 20 m sur le segment (pas pour un simple croisement)
FINISH_FROM = 0.9             # l'arrivée ne compte que venue d'au moins 90 % du segment...
FINISH_FROM_M = 50.0          # ... ou des 50 derniers mètres (segment court, grande vitesse)
ABANDON_S = 10.0              # abandon : plus de 40 m d'écart au tracé pendant 10 s...
U_TURN_M = 50.0               # ... ou 50 m de recul sur le segment (demi-tour)
HEADING_TOLERANCE_DEG = 90.0  # l'annonce ne vaut que dans le sens du segment
GHOST_TOLERANCE = 0.1         # passage du record retrouvé dans sa sortie : à 10 % de son temps près...
GHOST_TOLERANCE_S = 5.0       # ... et au moins 5 s (le compteur et Strava ne coupent pas la ligne pile au même endroit)


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


class SegmentTracker:
    """Suit tous les segments en favori pendant une sortie. `update` renvoie ce qui vient de se passer ; `approach` et
    `active` disent où on en est."""

    def __init__(self, segments: list[StarredSegment]):
        self.segments = segments
        self.efforts: list[Effort] = []        # passages en cours, annoncés ou pas encore
        self.approach: Approach | None = None  # segment annoncé, et distance à son départ
        self._approach_min = math.inf          # plus courte distance au départ depuis l'annonce
        self._distance: dict[int, float] = {}  # distance au départ de chaque segment, à la mesure d'avant
        self._near: dict[int, float] = {}      # près du départ : position le long du segment, à la mesure d'avant
        self._last: Sample | None = None       # dernière mesure avec une position
        self.results: list[Result] = []        # segments finis pendant la sortie

    @property
    def active(self) -> list[Effort]:
        """Passages annoncés, celui qui finit le premier d'abord."""
        return sorted((effort for effort in self.efforts if effort.confirmed), key=lambda effort: effort.remaining_m)

    def update(self, sample: Sample) -> list:
        """À chaque mesure. Renvoie les Approach, Start, Finish et Abandon qu'elle déclenche."""
        if sample.lat is None or sample.lon is None:
            for effort in self.efforts:  # sans position, le chrono tourne quand même
                effort.now_t = sample.t
            return []
        events = []
        for effort in list(self.efforts):
            events += self._follow(effort, sample)
        heading = self._heading(sample)
        running = {effort.segment.id for effort in self.efforts}
        for segment in self.segments:
            if segment.id not in running:
                events += self._watch(segment, sample, heading)
        self._last = sample
        return events

    def _heading(self, sample: Sample) -> float | None:
        """Cap du cycliste : celui du GPS, sinon celui de son dernier déplacement."""
        if sample.heading_deg is not None:
            return sample.heading_deg
        last = self._last
        if last is None or distance_m(last.lat, last.lon, sample.lat, sample.lon) < 2:
            return None
        return bearing_deg(last.lat, last.lon, sample.lat, sample.lon)

    def _speed(self, sample: Sample) -> float | None:
        if sample.speed_mps is not None and sample.speed_mps > 0.5:
            return sample.speed_mps
        last = self._last
        if last is None or sample.t <= last.t:
            return None
        return distance_m(last.lat, last.lon, sample.lat, sample.lon) / (sample.t - last.t) or None

    def _watch(self, segment: StarredSegment, sample: Sample, heading: float | None) -> list:
        """Segment pas encore commencé : annonce à l'approche, puis passage de la ligne de départ."""
        start = segment.route.points[0]
        d = distance_m(sample.lat, sample.lon, start.lat, start.lon)
        before = self._distance.get(segment.id)
        self._distance[segment.id] = d
        events = []
        if self.approach is not None and self.approach.segment is segment:
            self._approach_min = min(self._approach_min, d)
            away = d > APPROACH_M + APPROACH_END_M or d > self._approach_min + APPROACH_END_M
            self.approach = None if away else Approach(segment, d)
        elif (self.approach is None and before is not None and before > APPROACH_M >= d
              and (heading is None
                   or angle_between(heading, segment.route.heading_at(0)) <= HEADING_TOLERANCE_DEG)):
            self.approach = Approach(segment, d)
            self._approach_min = d
            events.append(self.approach)

        # Ligne de départ franchie : la position le long du segment quitte son début (ou, sur une boucle, passe de la
        # fin du tour à son début). Dans l'autre sens (segment descendu à rebours), elle y arrive au lieu d'en partir :
        # pas de départ.
        if d > NEAR_START_M:
            self._near.pop(segment.id, None)
            return events
        route = segment.route
        route.rewind()
        position = route.locate(sample.lat, sample.lon)
        before_along = self._near.get(segment.id)
        self._near[segment.id] = position.along_m
        if before_along is None or position.offset_m > START_RADIUS_M or not (
                before_along <= 0.5 < position.along_m
                or (segment.loop and before_along >= route.length_m - NEAR_START_M
                    and 0.5 < position.along_m < NEAR_START_M)):
            return events
        # Heure du passage de la ligne, à la vitesse du moment
        speed = self._speed(sample)
        start_t = sample.t - position.along_m / speed if speed else sample.t
        if self._last is not None:
            start_t = max(start_t, self._last.t)
        effort = Effort(segment, start_t=start_t, now_t=sample.t, pr=segment.pr,
                        along_m=position.along_m, max_along_m=position.along_m)
        effort.splits += [(0.0, 0.0), (position.along_m, sample.t - start_t)]
        self.efforts.append(effort)
        del self._near[segment.id]
        return events + self._confirm(effort)

    def _confirm(self, effort: Effort) -> list:
        """Assez de chemin fait sur le segment : l'effort est annoncé, et l'annonce d'approche s'efface."""
        if effort.confirmed or effort.along_m < min(CONFIRM_M, effort.segment.length_m / 2):
            return []
        effort.confirmed = True
        if self.approach is not None and self.approach.segment is effort.segment:
            self.approach = None
        return [Start(effort)]

    def _follow(self, effort: Effort, sample: Sample) -> list:
        """Segment en cours : avancée, arrivée, abandon."""
        route = effort.segment.route
        previous_t, before = effort.now_t, effort.along_m
        effort.heart_rate.add(sample.heart_rate, min(max(sample.t - previous_t, 0.0), MAX_GAP_S))
        effort.now_t = sample.t
        position = route.locate(sample.lat, sample.lon)
        if position.offset_m > OFF_ROUTE_M:
            if effort.off_since is None:
                effort.off_since = sample.t
            return self._abandon(effort) if sample.t - effort.off_since >= ABANDON_S else []
        effort.off_since = None
        along, length = position.along_m, route.length_m
        if effort.max_along_m - along > U_TURN_M:
            return self._abandon(effort)

        # Arrivée : la position le long du segment atteint son bout (elle y reste au-delà). Venue de trop loin, une
        # partie du segment a été coupée : il ne compte pas.
        if along >= length - 0.5:
            if before < length - max((1 - FINISH_FROM) * length, FINISH_FROM_M):
                return self._abandon(effort)
            speed = self._speed(sample)
            end_t = previous_t + (length - before) / speed if speed else sample.t
            effort.now_t = min(max(end_t, previous_t), sample.t)
            effort.along_m = effort.max_along_m = length
            effort.splits.append((length, effort.elapsed_s))
            return self._confirm(effort) + [self._finish(effort)]

        effort.along_m = along
        if along > effort.max_along_m:
            effort.max_along_m = along
            effort.splits.append((along, effort.elapsed_s))
        return self._confirm(effort)

    def _finish(self, effort: Effort) -> Finish:
        """Segment fini : son résultat. Un record battu (ou un premier temps) devient la référence, fantôme compris."""
        self.efforts.remove(effort)
        segment = effort.segment
        new_record = effort.pr is None or effort.elapsed_s < effort.pr.elapsed_s
        result = Result(segment, effort.elapsed_s, effort.pr_gap_s, effort.kom_gap_s, new_record,
                        segment.length_m / effort.elapsed_s if effort.elapsed_s > 0 else 0.0,
                        effort.heart_rate.mean, effort.heart_rate.max, effort.pr, tuple(effort.splits))
        self.results.append(result)
        if new_record:
            segment.pr = Best(effort.elapsed_s, result.splits)
        if segment.loop:  # le tour suivant part de la fin de celui-ci
            self._near[segment.id] = segment.length_m
        return Finish(result)

    def _abandon(self, effort: Effort) -> list:
        self.efforts.remove(effort)
        return [Abandon(effort)] if effort.confirmed else []


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
