"""Cycliste simulé : il suit un parcours GPX avec des mesures réalistes, pour tester sans matériel."""

import math

from .ride import Sample
from .route import Route

STOP_EVERY_S = 300    # un arrêt (feu rouge) toutes les 5 minutes...
STOP_DURATION_S = 15  # ... de 15 s, pour voir l'auto-pause
FLAT_SPEED_KMH = 29
RESTING_HR = 72
GPS_FIX_S = 4.0       # le GPS capte les satellites 4 s après la mise en route


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
            "batteryPct": max(0, round(100 - t / 216)),
        }
