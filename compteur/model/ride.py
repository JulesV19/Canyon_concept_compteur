"""RideModel : la sortie en cours, exposée à QML."""

import bisect
import math
from collections.abc import Callable

from PySide6.QtCore import Property, QObject, QPointF, Signal, Slot

from ..ride import PROFILE_STEP_M, Ride, Sample, State
from ..route import Position, Route
from ..segments import Abandon, Approach, Finish, Result, SegmentTracker, Start, StarredSegment
from ..tiles import world
from .segments import segment_card, segment_profile, segment_progress, segment_result
from .track import TRACK_CHUNK, TRACK_TOLERANCE, simplified
from .values import lap_summary, route_progress, snapshot

# Sortie reprise : la position sur le parcours est retrouvée en suivant la trace, une mesure sur 30 (assez pour ne pas
# confondre les deux passages d'un aller-retour, et rapide même pour une longue sortie)
RESUME_LOCATE_EVERY = 30
# Courbe cardio : une moyenne par tranche de 5 s, soit 120 points sur 10 min pour ~370 px de large
HR_CURVE_STEP = 5


class RideModel(QObject):
    """Expose la sortie à QML : `ride.values.speedKmh`, `ride.routePath`, `ride.startPause()`..."""

    changed = Signal()
    routeChanged = Signal()
    trackChanged = Signal()        # nouveau point de trace : `trackRecent` a changé
    trackChunksChanged = Signal()  # un tronçon de trace de plus est fini
    profileChanged = Signal()      # nouveau point du profil roulé
    lapsChanged = Signal()         # un tour de plus est fini
    lapCompleted = Signal("QVariantMap")
    segmentProfileChanged = Signal()           # autre segment à l'écran
    segmentApproached = Signal("QVariantMap")  # segment en favori à 300 m
    segmentStarted = Signal("QVariantMap")
    segmentFinished = Signal("QVariantMap")    # son résultat
    segmentAbandoned = Signal("QVariantMap")

    def __init__(self, ride: Ride, route: Route | None = None,
                 origin: tuple[float, float] = (0.0, 0.0), parent: QObject | None = None,
                 segments: list[StarredSegment] | None = None):
        super().__init__(parent)
        # Segments en favori, suivis à chaque nouvelle sortie ; KOM ou QOM, selon le profil Strava
        self.segments: list[StarredSegment] = segments or []
        self.kom_label = "KOM"
        self.record_beaten: Callable[[Result], None] | None = None  # record battu sur un segment : à garder
        # Coordonnées carte comptées depuis une origine proche : des nombres assez petits
        # pour rester précis dans le moteur graphique
        self._origin = origin
        self._device: dict = {}
        self._values: dict = {}
        self._tick = 0  # numéro de la mise à jour
        self._start(ride, route)
        self.refresh()

    def _start(self, ride: Ride, route: Route | None) -> None:
        self.ride = ride
        self.route = route
        if route is not None:
            route.rewind()
        self._route_path = [self._map_point(p.lat, p.lon) for p in route.points] if route else []
        # Longueur du tracé dessiné (coordonnées carte) jusqu'à chaque point
        self._route_lengths = [0.0]
        for a, b in zip(self._route_path, self._route_path[1:]):
            self._route_lengths.append(self._route_lengths[-1] + math.hypot(b.x() - a.x(), b.y() - a.y()))
        # Profil du parcours tous les 50 m (vide si le GPX n'a pas d'altitudes)
        steps = max(2, round(route.length_m / PROFILE_STEP_M) + 1) if route else 0
        self._route_profile = [QPointF(d / 1000, ele) for d, ele in route.profile(steps)] if route else []
        self._track_path: list[QPointF] = []          # toute la trace, en coordonnées carte
        self._track_chunks: list[list[QPointF]] = []  # ses tronçons finis
        self._ride_profile: list[QPointF] = []        # profil roulé : (km, m) tous les 50 m
        self._laps: list[dict] = []                   # tours finis, du plus récent au plus ancien
        self._position: Position | None = None
        self.tracker = SegmentTracker(list(self.segments))
        self._segment_events: list = []               # annonces, départs, arrivées : montrés au prochain refresh
        self._finished_segment: StarredSegment | None = None  # dernier segment fini : son profil reste à l'écran
        self._profile_segment: StarredSegment | None = None
        self._segment_profile: list[QPointF] = []

    def reset(self, ride: Ride, route: Route | None) -> None:
        """Nouvelle sortie, au repos : sur ce parcours, ou sans parcours."""
        self._start(ride, route)
        self._changed()

    def resume(self, ride: Ride, route: Route | None) -> None:
        """Sortie reprise après une coupure (voir journal.py) : la même, avec sa position sur le parcours."""
        self._start(ride, route)
        if route is not None:
            samples = [record.sample for record in ride.records[::RESUME_LOCATE_EVERY]] + [ride.current]
            for sample in samples:
                if sample is not None and sample.lat is not None and sample.lon is not None:
                    self._position = route.locate(sample.lat, sample.lon)
        self._changed()

    @property
    def position(self) -> Position | None:
        """Position sur le parcours suivi (None sans parcours, ou pas encore trouvée)."""
        return self._position

    def _changed(self) -> None:
        self.routeChanged.emit()
        self.trackChunksChanged.emit()
        self.trackChanged.emit()
        self.profileChanged.emit()
        self.lapsChanged.emit()
        self.segmentProfileChanged.emit()
        self.refresh()

    def _map_point(self, lat: float, lon: float) -> QPointF:
        x, y = world(lat, lon)
        return QPointF(x - self._origin[0], y - self._origin[1])

    def _drawn_length(self, along_m: float) -> float:
        """Longueur faite le long du tracé dessiné (coordonnées carte) pour `along_m` mètres faits :
        c'est là que la carte creuse le parcours, pile sous la position."""
        cumulative = self.route.cumulative
        i = min(max(bisect.bisect_right(cumulative, along_m) - 1, 0), len(cumulative) - 2)
        span = cumulative[i + 1] - cumulative[i]
        t = min(max((along_m - cumulative[i]) / span, 0.0), 1.0) if span else 0.0
        return self._route_lengths[i] + t * (self._route_lengths[i + 1] - self._route_lengths[i])

    def _get_values(self) -> dict:
        return self._values

    def _get_origin(self) -> QPointF:
        return QPointF(*self._origin)

    def _get_route_path(self) -> list:
        return self._route_path

    def _get_route_profile(self) -> list:
        return self._route_profile

    def _get_track_chunk_count(self) -> int:
        return len(self._track_chunks)

    @Slot(int, result="QVariantList")
    def trackChunk(self, index: int) -> list:
        """Un tronçon fini de la trace. La carte le demande une fois, quand il arrive : les autres ne bougent pas."""
        return self._track_chunks[index] if 0 <= index < len(self._track_chunks) else []

    def _get_track_recent(self) -> list:
        return self._track_path[len(self._track_chunks) * TRACK_CHUNK:]

    def _get_ride_profile(self) -> list:
        return self._ride_profile

    def _get_heart_rate_curve(self) -> list:
        """Courbe cardio des 10 dernières minutes, en points (âge en s, bpm), du plus ancien au plus récent : une
        moyenne par tranche de 5 s, calée sur le numéro des mesures (la courbe glisse sans changer de forme), puis la
        dernière mesure, pour finir pile sur la valeur du moment. La tranche en cours et celle que l'historique
        a entamée sont laissées de côté."""
        history = list(self.ride.hr_history)
        count = self.ride.hr_count
        first = count - len(history)  # numéro de la plus ancienne mesure gardée
        points = []
        for start in range(first + (-first) % HR_CURVE_STEP, count - HR_CURVE_STEP + 1, HR_CURVE_STEP):
            chunk = history[start - first:start - first + HR_CURVE_STEP]
            points.append(QPointF(count - 1 - (start + (HR_CURVE_STEP - 1) / 2), sum(chunk) / len(chunk)))
        if history:
            points.append(QPointF(0, history[-1]))
        return points

    def _get_laps(self) -> list:
        return self._laps

    def _get_segment_profile(self) -> list:
        return self._segment_profile

    values = Property("QVariantMap", _get_values, notify=changed)
    mapOrigin = Property(QPointF, _get_origin, constant=True)
    routePath = Property("QVariantList", _get_route_path, notify=routeChanged)
    routeProfile = Property("QVariantList", _get_route_profile, notify=routeChanged)
    # La trace en tronçons finis (chacun commence au dernier point du précédent, voir trackChunk), puis le tronçon en cours
    trackChunkCount = Property(int, _get_track_chunk_count, notify=trackChunksChanged)
    trackRecent = Property("QVariantList", _get_track_recent, notify=trackChanged)
    rideProfile = Property("QVariantList", _get_ride_profile, notify=profileChanged)
    heartRateCurve = Property("QVariantList", _get_heart_rate_curve, notify=changed)  # 10 dernières minutes
    laps = Property("QVariantList", _get_laps, notify=lapsChanged)
    segmentProfile = Property("QVariantList", _get_segment_profile, notify=segmentProfileChanged)  # (km, m)

    def update(self, sample: Sample) -> None:
        """Nouvelle mesure : calculs de la sortie, position sur le parcours et sur les segments en favori."""
        self.ride.update(sample)
        if self.route is not None and sample.lat is not None and sample.lon is not None:
            self._position = self.route.locate(sample.lat, sample.lon)
        if self.ride.state is not State.IDLE:
            events = self.tracker.update(self.ride.current)
            self._segment_events += events
            for event in events:
                if isinstance(event, Finish) and event.result.new_record and self.record_beaten is not None:
                    self.record_beaten(event.result)

    def refresh(self, device: dict | None = None) -> None:
        """Recalcule les valeurs affichées. `device` : état du boîtier (GPS, batterie)."""
        if device is not None:
            self._device = device
        now = self.ride.current
        on_map = {}  # position et avancement, en coordonnées carte
        if now is not None and now.lat is not None and now.lon is not None:
            point = self._map_point(now.lat, now.lon)
            on_map = {"x": point.x(), "y": point.y(), "heading": now.heading_deg}
        if self.route is not None:
            on_map["routeDoneLength"] = self._drawn_length(self._position.along_m if self._position else 0.0)
        # Numéro de la mise à jour : ce qui clignote suit la seconde, sans aucune image de plus à dessiner
        self._tick += 1
        events, self._segment_events = self._segment_events, []
        for event in events:
            if isinstance(event, Finish):
                self._finished_segment = event.result.segment
        self._values = (snapshot(self.ride) | route_progress(self.route, self._position)
                        | segment_progress(self.tracker, self.kom_label)
                        | on_map | self._device | {"tick": self._tick})
        self._update_segment_profile()
        self.changed.emit()
        self._extend_track()
        self._extend_profile()
        if len(self.ride.laps) - 1 != len(self._laps):
            self._laps = [lap_summary(lap) for lap in reversed(self.ride.laps[:-1])]
            self.lapsChanged.emit()
        self._emit_segment_events(events)

    def _update_segment_profile(self) -> None:
        """Profil du segment à l'écran : celui du passage en cours, sinon celui qu'on annonce, sinon le dernier fini."""
        tracker = self.tracker
        active = tracker.active
        segment = (active[0].segment if active else tracker.approach.segment if tracker.approach is not None
                   else self._finished_segment)
        if segment is not self._profile_segment:
            self._profile_segment = segment
            self._segment_profile = segment_profile(segment) if segment is not None else []
            self.segmentProfileChanged.emit()

    def _emit_segment_events(self, events: list) -> None:
        """Annonces, départs, arrivées et abandons, une fois les valeurs de l'écran à jour."""
        label = self.kom_label
        for event in events:
            if isinstance(event, Approach):
                self.segmentApproached.emit(segment_card(event.segment, label) | {"distanceM": event.distance_m})
            elif isinstance(event, Start):
                self.segmentStarted.emit(segment_card(event.effort.segment, label))
            elif isinstance(event, Finish):
                self.segmentFinished.emit(segment_result(event.result, label))
            elif isinstance(event, Abandon):
                self.segmentAbandoned.emit(segment_card(event.effort.segment, label))

    def _extend_track(self) -> None:
        """Nouveaux points de trace. Un tronçon est fini dès qu'un point le suit : le dernier point reçu reste
        dans le tronçon en cours, que la carte prolonge en douceur jusqu'à la position."""
        track = self.ride.track
        if len(track) <= len(self._track_path):
            return
        self._track_path.extend(self._map_point(lat, lon) for lat, lon in track[len(self._track_path):])
        finished = max(0, (len(self._track_path) - 2) // TRACK_CHUNK)
        if finished > len(self._track_chunks):
            self._track_chunks.extend(simplified(self._track_path[i * TRACK_CHUNK:(i + 1) * TRACK_CHUNK + 1],
                                                 TRACK_TOLERANCE)
                                      for i in range(len(self._track_chunks), finished))
            self.trackChunksChanged.emit()
        self.trackChanged.emit()

    def _extend_profile(self) -> None:
        profile = self.ride.profile
        if len(profile) > len(self._ride_profile):
            self._ride_profile.extend(QPointF(d / 1000, ele) for d, ele in profile[len(self._ride_profile):])
            self.profileChanged.emit()

    @Slot()
    def startPause(self) -> None:
        self.ride.start_pause()
        self.refresh()

    @Slot()
    def lap(self) -> None:
        done = self.ride.lap()
        if done is not None:
            self.lapCompleted.emit(lap_summary(done))
            self.refresh()
