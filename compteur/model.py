"""Pont entre le backend Python et l'interface QML."""

import bisect
import math

from PySide6.QtCore import Property, QObject, QPointF, Signal, Slot

from .ride import HR_ZONE_BOUNDS, PROFILE_STEP_M, Ride, Sample, Segment
from .route import OFF_ROUTE_M, Position, Route
from .tiles import world

# La trace part vers la carte par tronçons de 50 points (500 m) : un tronçon fini n'est plus jamais redessiné, et seuls
# ceux qui touchent l'écran sont tracés, en entier, à chaque image. Un tronçon fini perd aussi les points dont l'écart ne
# se voit pas (moins d'un pixel au zoom le plus fort) : environ 4 points sur 5 sur les routes de la région. C'est ce qui
# garde la carte légère quand une longue sortie libre repasse plusieurs fois au même endroit.
TRACK_CHUNK = 50
TRACK_TOLERANCE = 1.0  # en coordonnées carte, soit en pixels au zoom 16
# Sortie reprise : la position sur le parcours est retrouvée en suivant la trace, une mesure sur 30 (assez pour ne pas
# confondre les deux passages d'un aller-retour, et rapide même pour une longue sortie)
RESUME_LOCATE_EVERY = 30
# Courbe cardio : une moyenne par tranche de 5 s, soit 120 points sur 10 min pour ~370 px de large
HR_CURVE_STEP = 5


def _kmh(mps: float | None) -> float | None:
    return None if mps is None else mps * 3.6


def simplified(points: list[QPointF], tolerance: float) -> list[QPointF]:
    """Le tracé sans les points qui s'écartent de moins de `tolerance` du segment entre leurs voisins gardés
    (Douglas-Peucker). Le premier et le dernier restent, pour que les tronçons se raccordent ; un demi-tour aussi, même
    au bout d'une ligne droite."""
    if tolerance <= 0 or len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    spans = [(0, len(points) - 1)]
    while spans:
        first, last = spans.pop()
        ax, ay, bx, by = points[first].x(), points[first].y(), points[last].x(), points[last].y()
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        worst, index = tolerance, None
        for i in range(first + 1, last):
            px, py = points[i].x(), points[i].y()
            t = min(1.0, max(0.0, ((px - ax) * dx + (py - ay) * dy) / length2)) if length2 else 0.0
            distance = math.hypot(px - ax - t * dx, py - ay - t * dy)
            if distance > worst:
                worst, index = distance, i
        if index is not None:
            keep[index] = True
            spans += [(first, index), (index, last)]
    return [point for point, kept in zip(points, keep) if kept]


def lap_summary(lap: Segment) -> dict:
    return {
        "number": lap.number,
        "timerS": lap.timer_s,
        "distanceKm": lap.distance_m / 1000,
        "avgSpeedKmh": _kmh(lap.avg_speed_mps),
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
        "speedKmh": _kmh(now.speed_mps) if now else None,
        "heartRate": heart_rate,
        "hrZone": ride.hr_zone(heart_rate),
        "altitudeM": now.altitude_m if now else None,
        "gradePct": ride.grade_pct,
        # Sortie complète
        "timerS": total.timer_s,
        "elapsedS": ride.elapsed_s,
        "distanceKm": total.distance_m / 1000,
        "avgSpeedKmh": _kmh(total.avg_speed_mps),
        "maxSpeedKmh": _kmh(total.max_speed_mps),
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


class RideModel(QObject):
    """Expose la sortie à QML : `ride.values.speedKmh`, `ride.routePath`, `ride.startPause()`..."""

    changed = Signal()
    routeChanged = Signal()
    trackChanged = Signal()        # nouveau point de trace : `trackRecent` a changé
    trackChunksChanged = Signal()  # un tronçon de trace de plus est fini
    profileChanged = Signal()      # nouveau point du profil roulé
    lapsChanged = Signal()         # un tour de plus est fini
    lapCompleted = Signal("QVariantMap")

    def __init__(self, ride: Ride, route: Route | None = None,
                 origin: tuple[float, float] = (0.0, 0.0), parent: QObject | None = None):
        super().__init__(parent)
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

    def update(self, sample: Sample) -> None:
        """Nouvelle mesure : calculs de la sortie et position sur le parcours."""
        self.ride.update(sample)
        if self.route is not None and sample.lat is not None and sample.lon is not None:
            self._position = self.route.locate(sample.lat, sample.lon)

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
        self._values = (snapshot(self.ride) | route_progress(self.route, self._position)
                        | on_map | self._device | {"tick": self._tick})
        self.changed.emit()
        self._extend_track()
        self._extend_profile()
        if len(self.ride.laps) - 1 != len(self._laps):
            self._laps = [lap_summary(lap) for lap in reversed(self.ride.laps[:-1])]
            self.lapsChanged.emit()

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
