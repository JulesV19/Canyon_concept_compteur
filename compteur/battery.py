"""Jauge de batterie MAX17048 (Adafruit 5580), sur le bus I2C : charge en %, tension, vitesse de charge.

La jauge est alimentée par la batterie elle-même et estime la charge d'après la tension seule (ModelGauge) : elle se
passe de résistance de mesure, et sa première estimation arrive quelques secondes après le branchement de la batterie.
Elle ne mesure donc pas le courant : il se déduit de la vitesse de charge et de la capacité de la batterie.

Sur le Pi, un fil à part lit la jauge et l'alimentation du Pi (baisse du 5 V, température du processeur) toutes les
2 s : l'écran ne touche jamais au bus.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ADDRESS = 0x36
VCELL = 0x02    # tension, 78,125 µV par unité
SOC = 0x04      # charge : l'octet haut en %, l'octet bas en 1/256 de %
MODE = 0x06     # bit HibStat : la jauge est en veille
VERSION = 0x08  # 0x001X
CRATE = 0x16    # vitesse de charge (> 0) ou de décharge (< 0), 0,208 %/h par unité, signée
STATUS = 0x1A   # alertes, dans l'octet haut
HIB_STAT = 0x1000  # MODE : en veille, la jauge ne mesure plus que toutes les 45 s (la charge bouge peu)
HD = 0x1000        # STATUS : charge sous le seuil d'alerte (4 % par défaut, registre CONFIG)

CAPACITY_MAH = 5000  # la LiPo 105080 du compteur (docs/achats.md)
POLL_S = 2.0         # lecture de la jauge et de l'alimentation
STALE_S = 10.0       # plus de lecture depuis 10 s : la jauge ne répond plus
LOST_AFTER = 3       # lectures ratées d'affilée avant de chercher la jauge à nouveau (batterie débranchée)
SEARCH_S = 10.0      # jauge introuvable : on la cherche toutes les 10 s

TREND_STEP_S = 30.0      # un point de la courbe toutes les 30 s...
TREND_KEEP = 24 * 120    # ... sur 24 h au plus
TREND_WINDOW_S = 900.0   # l'autonomie suit la pente de la charge sur les 15 dernières minutes...
TREND_MIN_S = 300.0      # ... dès qu'elle couvre 5 min ; avant, la vitesse donnée par la jauge
MOVING_PCT_H = 1.0       # sous 1 %/h, dans un sens ou dans l'autre, la batterie ne se charge pas
FULL_PCT = 99.5
LOW_PCT = 15.0
MAX_FORECAST_S = 48 * 3600  # au-delà, l'estimation ne veut plus rien dire


@dataclass(frozen=True)
class Reading:
    percent: float      # de 0 à 100
    voltage: float      # volts
    rate_pct_h: float   # % par heure : positif en charge, négatif en décharge
    hibernating: bool = False  # en veille : mesures espacées
    low_alert: bool = False    # alerte de la jauge : charge sous son seuil


def decode(soc: int, vcell: int, crate: int, mode: int = 0, status: int = 0) -> Reading:
    """Les registres bruts, en valeurs. La jauge peut annoncer un peu plus de 100 % en fin de charge."""
    signed = crate - 0x10000 if crate & 0x8000 else crate
    return Reading(percent=min(soc / 256, 100.0), voltage=vcell * 78.125e-6, rate_pct_h=signed * 0.208,
                   hibernating=bool(mode & HIB_STAT), low_alert=bool(status & HD))


class Gauge:
    def __init__(self, bus):
        self.bus = bus

    def register(self, register: int) -> int:
        return int.from_bytes(self.bus.transfer(ADDRESS, bytes([register]), 2), "big")

    def read(self) -> Reading:
        """Lève OSError si la jauge ne répond pas."""
        return decode(self.register(SOC), self.register(VCELL), self.register(CRATE), self.register(MODE),
                      self.register(STATUS))


@dataclass(frozen=True)
class Supply:
    """Alimentation du Pi. None : inconnu (hors du Pi)."""

    undervoltage: bool | None = None  # le 5 V est trop bas en ce moment
    cpu_temp_c: float | None = None


HWMON = Path("/sys/class/hwmon")


class SupplySensors:
    """Les fichiers du noyau qui donnent l'alimentation du Pi : l'alarme de baisse du 5 V (rpi_volt) et la température
    du processeur (cpu_thermal). Cherchés une fois ; lus sans lancer de programme (vcgencmd)."""

    def __init__(self, hwmon: Path = HWMON):
        self.alarm: Path | None = None
        self.temperature: Path | None = None
        for folder in sorted(hwmon.glob("hwmon*")):
            try:
                name = (folder / "name").read_text().strip()
            except OSError:
                continue
            if name == "rpi_volt":
                self.alarm = folder / "in0_lcrit_alarm"
            elif name == "cpu_thermal":
                self.temperature = folder / "temp1_input"

    def read(self) -> Supply:
        undervoltage = temperature = None
        try:
            if self.alarm is not None:
                undervoltage = self.alarm.read_text().strip() == "1"
        except OSError:
            pass
        try:
            if self.temperature is not None:
                temperature = int(self.temperature.read_text()) / 1000
        except (OSError, ValueError):
            pass
        return Supply(undervoltage, temperature)


class Monitor:
    """La jauge et l'alimentation du Pi, lues par un fil à part toutes les 2 s. `latest()` donne la dernière lecture,
    sans attendre le bus. La jauge peut manquer au démarrage (batterie pas branchée) ou disparaître : on la cherche
    à nouveau toutes les 10 s."""

    def __init__(self, find: Callable[[], object | None] | None = None, sensors: SupplySensors | None = None,
                 clock: Callable[[], float] = time.monotonic):
        if find is None:
            from . import i2c
            find = lambda: i2c.find(ADDRESS)  # noqa: E731
        self._find = find
        self._sensors = sensors if sensors is not None else SupplySensors()
        self.clock = clock
        self.errors = 0  # lectures ratées depuis le départ
        self._gauge: Gauge | None = None
        self._failed = 0
        self._searched_at: float | None = None
        self._reading: tuple[Reading, float] | None = None  # dernière lecture et son heure
        self._supply = Supply()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="batterie", daemon=True)

    def start(self) -> "Monitor":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def latest(self) -> tuple[Reading | None, Supply]:
        with self._lock:
            reading, supply = self._reading, self._supply
        if reading is None or self.clock() - reading[1] > STALE_S:
            return None, supply
        return reading[0], supply

    def poll(self) -> None:
        """Une lecture : la jauge (cherchée si besoin), puis l'alimentation."""
        now = self.clock()
        if self._gauge is None and (self._searched_at is None or now - self._searched_at >= SEARCH_S):
            self._searched_at = now
            bus = self._find()
            if bus is not None:
                self._gauge, self._failed = Gauge(bus), 0
        reading = None
        if self._gauge is not None:
            try:
                reading = self._gauge.read()
                self._failed = 0
            except OSError:
                self.errors += 1
                self._failed += 1
                if self._failed >= LOST_AFTER:
                    self._drop()
        supply = self._sensors.read()
        with self._lock:
            if reading is not None:
                self._reading = (reading, self.clock())
            self._supply = supply

    def _drop(self) -> None:
        bus, self._gauge = self._gauge.bus, None
        self._searched_at = self.clock()
        try:
            bus.close()
        except (AttributeError, OSError):
            pass

    def _run(self) -> None:
        while not self._stop.is_set():
            self.poll()
            self._stop.wait(POLL_S)


class Trend:
    """La charge au fil du temps, un point toutes les 30 s : la courbe de l'écran, et la pente d'où vient l'autonomie.
    Le temps est en secondes, compté par l'appelant."""

    def __init__(self):
        self.points: list[tuple[float, float]] = []  # (s, %)
        self.first: tuple[float, float] | None = None  # première lecture, pour « depuis la mise en route »

    def add(self, s: float, percent: float) -> bool:
        """Garde la lecture si le dernier point date de 30 s ; renvoie vrai si la courbe a un point de plus."""
        if self.first is None:
            self.first = (s, percent)
        if self.points and s - self.points[-1][0] < TREND_STEP_S:
            return False
        self.points.append((s, percent))
        if len(self.points) > TREND_KEEP:
            del self.points[0]
        return True

    def slope_pct_h(self) -> float | None:
        """Pente de la charge (moindres carrés) sur les 15 dernières minutes, en %/h ; None sur moins de 5 min."""
        if not self.points:
            return None
        end = self.points[-1][0]
        window = [(s, p) for s, p in self.points[-int(TREND_WINDOW_S / TREND_STEP_S) - 1:] if end - s <= TREND_WINDOW_S]
        if end - window[0][0] < TREND_MIN_S:
            return None
        mean_s = sum(s for s, _ in window) / len(window)
        mean_p = sum(p for _, p in window) / len(window)
        spread = sum((s - mean_s) ** 2 for s, _ in window)
        return sum((s - mean_s) * (p - mean_p) for s, p in window) / spread * 3600


@dataclass(frozen=True)
class Outlook:
    """Ce que l'écran déduit d'une lecture et de la courbe."""

    state: str                     # "charge", "decharge", "pleine", ou "absente" (pas de lecture)
    low: bool = False              # charge faible
    current_ma: float | None = None     # courant estimé : vitesse de la jauge × capacité
    remaining_mah: float | None = None
    autonomy_s: float | None = None     # en décharge : temps avant d'être vide
    full_in_s: float | None = None      # en charge : temps avant d'être pleine
    change_pct: float | None = None     # depuis la première lecture...
    since_s: float | None = None        # ... il y a tant de secondes


def outlook(reading: Reading | None, trend: Trend, now_s: float, capacity_mah: float = CAPACITY_MAH) -> Outlook:
    if reading is None:
        return Outlook("absente")
    rate = reading.rate_pct_h
    if rate >= MOVING_PCT_H and reading.percent < FULL_PCT:
        state = "charge"
    elif reading.percent >= FULL_PCT and rate > -MOVING_PCT_H:
        state = "pleine"
    else:
        state = "decharge"
    # Les estimations suivent la pente des 15 dernières minutes, plus stable que la vitesse de la jauge ; mais juste
    # après avoir branché ou débranché le chargeur, la pente va encore dans l'autre sens : la jauge d'abord
    slope = trend.slope_pct_h()
    if slope is not None and (slope > 0) == (state == "charge"):
        rate = slope
    autonomy = full_in = None
    if state == "decharge" and rate < -0.1:
        autonomy = min(reading.percent / -rate * 3600, MAX_FORECAST_S)
    elif state == "charge" and rate > 0.1:
        full_in = min((100 - reading.percent) / rate * 3600, MAX_FORECAST_S)
    first = trend.first
    return Outlook(
        state=state,
        low=reading.percent <= LOW_PCT or reading.low_alert,
        current_ma=abs(reading.rate_pct_h) * capacity_mah / 100,
        remaining_mah=reading.percent * capacity_mah / 100,
        autonomy_s=autonomy,
        full_in_s=full_in,
        change_pct=reading.percent - first[1] if first else None,
        since_s=now_s - first[0] if first else None,
    )
