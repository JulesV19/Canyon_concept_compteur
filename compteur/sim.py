"""Cycliste simulé : il suit un parcours GPX avec des mesures réalistes, pour tester sans matériel."""

import math
from datetime import datetime, timedelta, timezone

from .battery import Reading, Supply
from .gps import Fix, Satellite, Status
from .ride import Sample
from .route import Route
from .segments import START_RADIUS_M, Best, StarredSegment

STOP_EVERY_S = 300    # un arrêt (feu rouge) toutes les 5 minutes...
STOP_DURATION_S = 15  # ... de 15 s, pour voir l'auto-pause
FLAT_SPEED_KMH = 29
RESTING_HR = 72
GPS_FIX_S = 4.0       # le GPS capte les satellites 4 s après la mise en route
BATTERY_HOURS = 6.0   # batterie simulée : pleine à la mise en route, vide 6 h plus tard
# Tension d'une LiPo au repos selon sa charge (%, V), à peu près
LIPO_VOLTS = [(0, 3.30), (5, 3.55), (10, 3.65), (20, 3.72), (30, 3.77), (40, 3.80), (50, 3.84), (60, 3.87),
              (70, 3.93), (80, 4.00), (90, 4.08), (100, 4.18)]
SIMULATED_SUPPLY = Supply(undervoltage=False, cpu_temp_c=47.0)
# Ciel du GPS simulé : (constellation, numéro, élévation, azimut, signal en dB-Hz ; 0 : en vue, pas capté)
SKY = [("GPS", 2, 71, 40, 45), ("GPS", 5, 48, 128, 42), ("GPS", 12, 33, 205, 38), ("GPS", 13, 62, 292, 44),
       ("GPS", 15, 18, 330, 31), ("GPS", 18, 24, 76, 35), ("GPS", 25, 9, 165, 21), ("GPS", 29, 41, 255, 40),
       ("SBAS", 36, 31, 158, 34), ("GLONASS", 66, 55, 95, 39), ("GLONASS", 67, 28, 20, 33),
       ("GLONASS", 76, 37, 235, 36), ("GLONASS", 82, 6, 300, 0), ("Galileo", 7, 22, 115, 29),
       ("Galileo", 26, 14, 268, 0)]


class SimulatedRider:
    def __init__(self, route: Route):
        self.route = route
        self.distance_m = 0.0
        self._speed_kmh = 0.0
        self._heart_rate = float(RESTING_HR)
        self._last_t: float | None = None

    def sample(self, t: float, riding: bool = True) -> Sample:
        """Mesures à l'instant t. `riding` : faux tant que la sortie n'est pas lancée (ou en pause)."""
        dt = 0.0 if self._last_t is None else t - self._last_t
        self._last_t = t
        grade = self.route.grade_at(self.distance_m)

        if not riding or t % STOP_EVERY_S >= STOP_EVERY_S - STOP_DURATION_S:
            target = 0.0
        else:
            # Plus lent en montée, plus rapide en descente
            target = FLAT_SPEED_KMH - (2.4 if grade > 0 else 1.3) * grade + 1.5 * math.sin(t / 9)
            target = min(max(target, 9.0), 52.0)
        if target > self._speed_kmh:
            self._speed_kmh = min(target, self._speed_kmh + 4 * dt)  # accélère
        else:
            self._speed_kmh = max(target, self._speed_kmh - 8 * dt)  # freine
        speed_mps = self._speed_kmh / 3.6
        # Le parcours est bouclé : arrivé au bout, on repart du début
        self.distance_m = (self.distance_m + speed_mps * dt) % self.route.length_m

        # Le cœur suit l'effort (pente, vitesse) avec retard
        if self._speed_kmh > 1:
            effort = 118 + 5.5 * max(grade, 0) + 0.9 * (self._speed_kmh - 25)
        else:
            effort = RESTING_HR if not riding else 100
        self._heart_rate += (min(max(effort, 60), 188) - self._heart_rate) * min(1.0, 0.04 * dt)

        point = self.route.point_at(self.distance_m)
        return Sample(t=t, speed_mps=speed_mps, heart_rate=round(self._heart_rate),
                      lat=point.lat, lon=point.lon, altitude_m=point.ele,
                      heading_deg=self.route.heading_at(self.distance_m))

    def device_status(self, t: float) -> dict:
        """État du boîtier simulé (t : secondes depuis la mise en route) : GPS qui cherche les satellites
        puis capte, ceinture cardio, batterie (environ 6 h d'autonomie)."""
        half = GPS_FIX_S / 2
        return {
            "gpsBars": max(0, min(4, round((t - half) * 4 / half))),
            "gpsFix": t >= GPS_FIX_S,
            "hrConnected": True,
            "batteryPct": round(battery_percent(t)),
        }


def battery_percent(t: float) -> float:
    """Charge de la batterie simulée, t secondes après la mise en route."""
    return max(0.0, 100 - t / (BATTERY_HOURS * 36))


def battery_reading(t: float) -> Reading:
    """Ce que la jauge dirait de la batterie simulée, t secondes après la mise en route."""
    percent = battery_percent(t)
    below = max((p, v) for p, v in LIPO_VOLTS if p <= percent)
    above = min((p, v) for p, v in LIPO_VOLTS if p >= percent)
    share = (percent - below[0]) / (above[0] - below[0]) if above[0] > below[0] else 0.0
    return Reading(percent=percent, voltage=below[1] + share * (above[1] - below[1]),
                   rate_pct_h=-100 / BATTERY_HOURS if percent > 0 else 0.0)


DEMO_SEGMENT_M = 1000.0       # côte d'essai : le kilomètre qui grimpe le plus sur le parcours...
DEMO_SEGMENT_FROM_M = 1000.0  # ... passé le premier kilomètre (le temps de l'annoncer)
DEMO_RECORD_KMH = 13.0        # son record : à peu près l'allure du cycliste simulé dans une côte
DEMO_KOM_KMH = 22.0


def passes_by(route: Route, segment: StarredSegment) -> bool:
    """Le parcours passe-t-il par le départ et l'arrivée du segment ?"""
    try:
        for point in (segment.route.points[0], segment.route.points[-1]):
            route.rewind()
            if route.locate(point.lat, point.lon).offset_m > START_RADIUS_M:
                return False
        return True
    finally:
        route.rewind()


def demo_segments(route: Route, starred: list[StarredSegment] = ()) -> list[StarredSegment]:
    """Une côte d'essai sur le parcours du cycliste simulé, avec un record et un KOM, pour voir l'annonce, la page
    segment et l'arrivée ; aucune si le parcours passe déjà par un segment en favori (`starred`)."""
    if any(passes_by(route, segment) for segment in starred):
        return []
    length = min(DEMO_SEGMENT_M, route.length_m / 4)
    last = route.length_m - length
    best, best_gain = 0.0, -math.inf
    start = min(DEMO_SEGMENT_FROM_M, last)
    while start <= last:
        low, high = route.point_at(start).ele, route.point_at(start + length).ele
        gain = high - low if low is not None and high is not None else 0.0
        if gain > best_gain:
            best, best_gain = start, gain
        start += 50
    points = [route.point_at(best + i * 10) for i in range(int(length // 10) + 1)]
    name = "Côte d'essai"
    return [StarredSegment(0, name, Route(name, points), pr=Best(length / (DEMO_RECORD_KMH / 3.6)),
                           kom=Best(length / (DEMO_KOM_KMH / 3.6)))]


def gps_status(t: float, sample: Sample) -> Status:
    """Ce que le GPS dirait, t secondes après la mise en route, le cycliste simulé étant là où est `sample` : il
    cherche, puis trouve sa position au bout de 4 s. Les satellites tournent lentement dans le ciel."""
    found = t >= GPS_FIX_S
    strength = min(1.0, t / GPS_FIX_S)
    sky = tuple(Satellite(system, prn, elevation, round(azimuth + t / 240) % 360, round(snr * strength) or None)
                for system, prn, elevation, azimuth, snr in SKY)
    used = frozenset(sat.prn for sat in sky if found and sat.snr and sat.snr >= 30 and sat.system != "SBAS")
    age = 0.3
    fix = Fix(in_view=len(sky), sky=sky, firmware=None)
    if found:
        fix = Fix(valid=True, lat=sample.lat, lon=sample.lon, speed_mps=sample.speed_mps, heading_deg=sample.heading_deg,
                  altitude_m=sample.altitude_m, utc=datetime.now(timezone.utc) - timedelta(seconds=age),
                  satellites=len(used), in_view=len(sky), hdop=0.8, quality=2, fix_type=3, pdop=1.5, vdop=1.2,
                  used=used, sky=sky)
    return Status(fix, present=True, age_s=age, first_fix_s=GPS_FIX_S if found else None)
