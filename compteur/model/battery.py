"""BatteryModel : la batterie, exposée à QML."""

from datetime import datetime, timedelta

from PySide6.QtCore import Property, QObject, QPointF, Signal

from ..battery import CAPACITY_MAH, Reading, Supply, Trend, outlook


def clock(moment: datetime) -> str:
    return f"{moment:%H:%M}"


class BatteryModel(QObject):
    """Expose la batterie à QML : `battery.values` (charge, autonomie, mesures), mis à jour à chaque seconde (refresh),
    et `battery.curve`, la charge depuis la mise en route, un point toutes les 30 s."""

    changed = Signal()
    curveChanged = Signal()

    def __init__(self, source: str, capacity_mah: float = CAPACITY_MAH, parent: QObject | None = None):
        """`source` : d'où viennent les mesures (« MAX17048 », « Simulation »)."""
        super().__init__(parent)
        self.source = source
        self.capacity_mah = capacity_mah
        self.trend = Trend()
        self.reading: Reading | None = None
        self.supply = Supply()
        self.undervoltage_seen = False  # le 5 V est descendu trop bas depuis la mise en route
        self.now_s = 0.0
        self.state = "absente"  # "charge", "decharge", "pleine" ou "absente" : à la dernière mise à jour de l'écran
        self._values: dict = {}
        self._curve: list[QPointF] = []
        self.refresh()

    @property
    def percent(self) -> float | None:
        return self.reading.percent if self.reading is not None else None

    def update(self, now_s: float, reading: Reading | None, supply: Supply) -> None:
        """Nouvelle lecture (None : pas de jauge), `now_s` secondes après la mise en route."""
        self.now_s, self.reading, self.supply = now_s, reading, supply
        self.undervoltage_seen = self.undervoltage_seen or supply.undervoltage is True
        if reading is not None and self.trend.add(now_s, reading.percent):
            first = self.trend.points[0][0]
            self._curve = [QPointF(s - first, p) for s, p in self.trend.points]
            self.curveChanged.emit()

    def refresh(self) -> None:
        reading, supply = self.reading, self.supply
        view = outlook(reading, self.trend, self.now_s, self.capacity_mah)
        self.state = view.state
        now = datetime.now().astimezone()
        points = self.trend.points
        start = points[0][0] if points else self.now_s
        end = view.autonomy_s if view.autonomy_s is not None else view.full_in_s
        self._values = {
            "source": self.source,
            "state": view.state,
            "low": view.low,
            "percent": reading.percent if reading else None,
            "voltage": reading.voltage if reading else None,
            "ratePctH": reading.rate_pct_h if reading else None,
            "hibernating": reading.hibernating if reading else None,
            "currentMa": view.current_ma,
            "remainingMah": view.remaining_mah,
            "capacityMah": self.capacity_mah,
            "autonomyS": view.autonomy_s,
            "fullInS": view.full_in_s,
            "changePct": view.change_pct,
            "sinceS": view.since_s,
            "undervoltage": supply.undervoltage,
            "undervoltageSeen": self.undervoltage_seen,
            "cpuTempC": supply.cpu_temp_c,
            # Courbe : le temps compte depuis son premier point ; la prévision la prolonge jusqu'à vide (ou pleine)
            "nowS": self.now_s - start,
            "forecastS": end,
            "startClock": clock(now - timedelta(seconds=self.now_s - start)),
            "nowClock": clock(now),
            "endClock": clock(now + timedelta(seconds=end)) if end is not None else "",
        }
        self.changed.emit()

    def _get_values(self) -> dict:
        return self._values

    def _get_curve(self) -> list:
        return self._curve

    values = Property("QVariantMap", _get_values, notify=changed)
    curve = Property("QVariantList", _get_curve, notify=curveChanged)  # (s depuis le premier point, %)
