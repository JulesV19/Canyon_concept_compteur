"""Moteur de calcul d'une sortie : chrono, distance, moyennes, altitude, cardio, auto-pause, tours.

Indépendant de Qt et du matériel : on lui passe des mesures horodatées
(Sample), il tient les compteurs à jour. Unités SI : m, m/s, s.
"""

import math
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from enum import StrEnum

AUTO_PAUSE_SPEED_MPS = 3 / 3.6  # sous 3 km/h, on est à l'arrêt
AUTO_PAUSE_DELAY_S = 2.0        # le chrono se met en pause après 2 s à l'arrêt
MAX_GAP_S = 5.0                 # écart maximal compté entre deux mesures, pour le chrono et la distance
CLIMB_THRESHOLD_M = 2.0         # variation d'altitude minimale comptée (filtre le bruit de l'altimètre)
GRADE_DISTANCE_M = 40.0         # pente mesurée sur les 40 derniers mètres
TRACK_STEP_M = 10.0             # un point de trace tous les 10 m
PROFILE_STEP_M = 50.0           # un point du profil d'altitude tous les 50 m
HR_HISTORY_S = 600              # courbe cardio des 10 dernières minutes (1 mesure/s)
DEFAULT_MAX_HR = 190
HR_ZONE_BOUNDS = (0.6, 0.7, 0.8, 0.9)  # début des zones 2 à 5, en fraction de la FC max


@dataclass
class Sample:
    """Mesures instantanées à l'instant t (secondes, horloge monotone)."""

    t: float
    speed_mps: float | None = None
    heart_rate: float | None = None
    lat: float | None = None
    lon: float | None = None
    altitude_m: float | None = None
    heading_deg: float | None = None  # cap, 0 = nord, 90 = est


SENSOR_FIELDS = ("speed_mps", "heart_rate", "lat", "lon", "altitude_m", "heading_deg")


def finite(sample: Sample) -> Sample:
    """La mesure, où une valeur qui n'est pas un nombre fini (capteur en défaut) devient absente."""
    bad = {name: None for name in SENSOR_FIELDS
           if (value := getattr(sample, name)) is not None and not math.isfinite(value)}
    return replace(sample, **bad) if bad else sample


@dataclass(frozen=True)
class Record:
    """Mesure comptée, avec la distance parcourue depuis le départ : une ligne de l'enregistrement."""

    sample: Sample
    distance_m: float


@dataclass
class Average:
    """Moyenne pondérée par le temps, et maximum."""

    total: float = 0.0
    duration: float = 0.0
    max: float | None = None

    def add(self, value: float | None, dt: float) -> None:
        if value is None:
            return
        self.max = value if self.max is None else max(self.max, value)
        self.total += value * dt
        self.duration += dt

    @property
    def mean(self) -> float | None:
        return self.total / self.duration if self.duration else None


@dataclass
class Climb:
    """Dénivelé : une variation n'est comptée qu'une fois le seuil franchi, pour ignorer le bruit.
    Le sommet (ou le creux) atteint entre-temps est rattrapé au changement de sens."""

    threshold_m: float = CLIMB_THRESHOLD_M
    reference: float | None = None  # dernière altitude comptée
    high: float = 0.0               # plus haut et plus bas depuis
    low: float = 0.0

    def add(self, altitude: float) -> tuple[float, float]:
        """Renvoie (montée, descente) comptées avec cette mesure."""
        if self.reference is None:
            self.reference = self.high = self.low = altitude
            return 0.0, 0.0
        self.high = max(self.high, altitude)
        self.low = min(self.low, altitude)
        if altitude - self.reference >= self.threshold_m:
            up, down = altitude - self.low, self.reference - self.low
        elif self.reference - altitude >= self.threshold_m:
            up, down = self.high - self.reference, self.high - altitude
        else:
            return 0.0, 0.0
        self.reference = self.high = self.low = altitude
        return up, down


@dataclass
class Segment:
    """Compteurs d'une portion de sortie : la sortie entière ou un tour."""

    number: int = 1
    start_t: float | None = None  # début (horloge des mesures)
    timer_s: float = 0.0  # temps en mouvement, hors pauses
    distance_m: float = 0.0
    max_speed_mps: float = 0.0
    ascent_m: float = 0.0
    descent_m: float = 0.0
    heart_rate: Average = field(default_factory=Average)

    def add(self, sample: Sample, dt: float, climb: tuple[float, float]) -> None:
        self.timer_s += dt
        if sample.speed_mps is not None:
            self.distance_m += sample.speed_mps * dt
            self.max_speed_mps = max(self.max_speed_mps, sample.speed_mps)
        self.ascent_m += climb[0]
        self.descent_m += climb[1]
        self.heart_rate.add(sample.heart_rate, dt)

    @property
    def avg_speed_mps(self) -> float | None:
        return self.distance_m / self.timer_s if self.timer_s else None


class State(StrEnum):
    IDLE = "idle"        # sortie pas encore démarrée
    RUNNING = "running"
    PAUSED = "paused"    # pause manuelle


class Ride:
    def __init__(self, auto_pause: bool = True, max_hr: float = DEFAULT_MAX_HR):
        self.auto_pause = auto_pause
        self.max_hr = max_hr
        self.state = State.IDLE
        self.auto_paused = False
        self.total = Segment()
        self.laps = [Segment()]
        self.elapsed_s = 0.0  # temps écoulé depuis le départ, pauses comprises
        self.current: Sample | None = None
        self.grade_pct: float | None = None
        self.hr_zone_s = [0.0] * 5  # temps passé dans chaque zone cardio
        self.hr_history: deque[float] = deque(maxlen=HR_HISTORY_S)
        self.hr_count = 0  # mesures cardio reçues depuis le départ : numérote celles de hr_history
        self.track: list[tuple[float, float]] = []    # (lat, lon) de la trace, tous les 10 m
        self.profile: list[tuple[float, float]] = []  # (distance, altitude) tous les 50 m
        self.records: list[Record] = []               # mesures comptées, pour l'enregistrement
        self.timer_events: list[tuple[float, bool]] = []  # (t, en marche) : départs et arrêts du chrono
        self._timer_running = False
        self._climb = Climb()
        self._odometer_m = 0.0  # distance parcourue même chrono arrêté, pour la pente
        self._grade_window: deque[tuple[float, float]] = deque()
        self._track_distance_m = 0.0
        self._last_t: float | None = None
        self._stopped_since: float | None = None
        # Reçoit chaque entrée, une fois comptée : ("u", mesure), ("p",) pour Start/Pause, ("l",) pour Lap. Les rejouer
        # dans l'ordre sur un moteur neuf redonne la même sortie (voir journal.py).
        self.on_input: Callable[[tuple], None] | None = None

    def _notify(self, entry: tuple) -> None:
        if self.on_input is not None:
            self.on_input(entry)

    @property
    def current_lap(self) -> Segment:
        return self.laps[-1]

    @property
    def last_t(self) -> float:
        """Heure de la dernière mesure (horloge des mesures ; 0 avant la première)."""
        return self._last_t if self._last_t is not None else 0.0

    def hr_zone(self, heart_rate: float | None) -> int | None:
        """Zone cardio de 1 à 5 (en % de la FC max : <60, 60-70, 70-80, 80-90, >90)."""
        if heart_rate is None:
            return None
        return 1 + sum(heart_rate >= bound * self.max_hr for bound in HR_ZONE_BOUNDS)

    def start_pause(self) -> None:
        """Bouton Start/Pause : démarre, met en pause ou reprend."""
        if self.state == State.IDLE:
            self.total.start_t = self.current_lap.start_t = self.last_t
        self.state = State.PAUSED if self.state == State.RUNNING else State.RUNNING
        self.auto_paused = False
        self._stopped_since = None
        self._note_timer(self.last_t)
        self._notify(("p",))

    def lap(self) -> Segment | None:
        """Bouton Lap : clôt le tour en cours et en démarre un nouveau. Renvoie le tour clos."""
        if self.state == State.IDLE:
            return None
        done = self.current_lap
        self.laps.append(Segment(number=done.number + 1, start_t=self.last_t))
        self._notify(("l",))
        return done

    def update(self, sample: Sample) -> None:
        """À appeler à chaque nouvelle mesure (en général une fois par seconde). Une valeur qui n'est pas un nombre fini
        (capteur en défaut) compte comme absente."""
        sample = finite(sample)
        self._update(sample)
        self._notify(("u", sample))

    def _update(self, sample: Sample) -> None:
        gap = 0.0 if self._last_t is None else max(sample.t - self._last_t, 0.0)
        dt = min(gap, MAX_GAP_S)
        self._last_t = sample.t
        self.current = sample
        if sample.speed_mps is not None:
            self._odometer_m += sample.speed_mps * dt
        self._update_grade(sample)
        if sample.heart_rate is not None:
            self.hr_history.append(sample.heart_rate)
            self.hr_count += 1

        if self.state == State.IDLE:
            return
        self.elapsed_s += gap  # le temps total compte tout, comme le fichier FIT : c'est l'heure qui passe
        if self.state == State.PAUSED:
            return
        self._update_auto_pause(sample)
        self._note_timer(sample.t)
        if not self.auto_paused:
            self._record(sample, dt)

    def _note_timer(self, t: float) -> None:
        """Note chaque départ et arrêt du chrono (pause, auto-pause), pour l'enregistrement."""
        running = self.state == State.RUNNING and not self.auto_paused
        if running != self._timer_running:
            self._timer_running = running
            self.timer_events.append((t, running))

    def _record(self, sample: Sample, dt: float) -> None:
        climb = self._climb.add(sample.altitude_m) if sample.altitude_m is not None else (0.0, 0.0)
        self.total.add(sample, dt, climb)
        self.current_lap.add(sample, dt, climb)
        zone = self.hr_zone(sample.heart_rate)
        if zone is not None:
            self.hr_zone_s[zone - 1] += dt
        distance = self.total.distance_m
        self.records.append(Record(sample, distance))
        if sample.lat is not None and sample.lon is not None:
            if not self.track or distance - self._track_distance_m >= TRACK_STEP_M:
                self.track.append((sample.lat, sample.lon))
                self._track_distance_m = distance
        if sample.altitude_m is not None:
            if not self.profile or distance - self.profile[-1][0] >= PROFILE_STEP_M:
                self.profile.append((distance, sample.altitude_m))

    def _update_auto_pause(self, sample: Sample) -> None:
        if not self.auto_pause or sample.speed_mps is None:
            return  # vitesse inconnue (GPS perdu...) : on ne change rien
        if sample.speed_mps >= AUTO_PAUSE_SPEED_MPS:
            self.auto_paused = False
            self._stopped_since = None
        elif self._stopped_since is None:
            self._stopped_since = sample.t
        elif sample.t - self._stopped_since >= AUTO_PAUSE_DELAY_S:
            self.auto_paused = True

    def _update_grade(self, sample: Sample) -> None:
        window = self._grade_window
        if sample.altitude_m is None or (window and window[-1][0] == self._odometer_m):
            return  # pas d'altitude, ou à l'arrêt : on garde la dernière pente
        window.append((self._odometer_m, sample.altitude_m))
        while len(window) > 2 and self._odometer_m - window[1][0] >= GRADE_DISTANCE_M:
            window.popleft()
        run = self._odometer_m - window[0][0]
        if run >= GRADE_DISTANCE_M / 2:
            self.grade_pct = (sample.altitude_m - window[0][1]) / run * 100
