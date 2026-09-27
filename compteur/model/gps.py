"""GpsModel : l'état du GPS, exposé à QML."""

from datetime import datetime, timezone

from PySide6.QtCore import Property, QObject, Signal

from ..gps import ACCURACY_M_PER_HDOP, Fix, Status
from .units import kmh

SYSTEM_ORDER = ["GPS", "GLONASS", "Galileo", "BeiDou", "QZSS", "SBAS"]


def gps_state(status: Status) -> str:
    """"absent" (le GPS ne répond pas), "recherche", "2d" (position sans altitude) ou "3d"."""
    fix = status.fix
    if not status.present:
        return "absent"
    if not fix.valid:
        return "recherche"
    return "3d" if fix.fix_type == 3 or (fix.fix_type != 2 and fix.satellites >= 4) else "2d"


class GpsModel(QObject):
    """Expose l'état du GPS à QML : `gps.values` (réception, position, précision, heure), mis à jour à chaque seconde
    (refresh), et `gps.satellites`, le ciel satellite par satellite, qui ne change qu'avec lui (toutes les 5 s)."""

    changed = Signal()
    satellitesChanged = Signal()

    def __init__(self, source: str, parent: QObject | None = None):
        """`source` : d'où viennent les mesures (« PA1010D », « Simulation »)."""
        super().__init__(parent)
        self.source = source
        self.state = "absent"
        self._values: dict = {}
        self._satellites: list[dict] = []
        self.refresh(Status(fix=Fix()))

    def refresh(self, status: Status) -> None:
        fix = status.fix
        self.state = gps_state(status)
        located = self.state in ("2d", "3d")
        satellites = sorted(
            ({"system": sat.system, "prn": sat.prn, "elevation": sat.elevation, "azimuth": sat.azimuth,
              "snr": sat.snr or 0, "used": sat.prn in fix.used}
             for sat in fix.sky),
            key=lambda sat: (SYSTEM_ORDER.index(sat["system"]) if sat["system"] in SYSTEM_ORDER else 99, sat["prn"]))
        if satellites != self._satellites:
            self._satellites = satellites
            self.satellitesChanged.emit()
        constellations = [{"name": name, "inView": sum(1 for sat in satellites if sat["system"] == name),
                           "used": sum(1 for sat in satellites if sat["system"] == name and sat["used"])}
                          for name in SYSTEM_ORDER if any(sat["system"] == name for sat in satellites)]
        signals = [sat["snr"] for sat in satellites if sat["used"] and sat["snr"]]
        offset = None
        if fix.utc is not None and status.age_s is not None:
            offset = (datetime.now(timezone.utc) - fix.utc).total_seconds() - status.age_s
        self._values = {
            "source": self.source,
            "state": self.state,
            "sbas": fix.quality == 2,
            "used": fix.satellites if status.present else 0,
            "inView": fix.in_view if status.present else 0,
            "constellations": constellations,
            "signalDb": sum(signals) / len(signals) if signals else None,  # moyen, sur les satellites utilisés
            "hdop": fix.hdop if located else None,
            "pdop": fix.pdop if located else None,
            "vdop": fix.vdop if located else None,
            "accuracyM": fix.hdop * ACCURACY_M_PER_HDOP if located and fix.hdop is not None else None,
            "lat": fix.lat,
            "lon": fix.lon,
            "altitudeM": fix.altitude_m if located else None,
            "speedKmh": kmh(fix.speed_mps),
            "headingDeg": fix.heading_deg,
            "utcTime": f"{fix.utc:%H:%M:%S}" if fix.utc else "",
            "utcDate": f"{fix.utc:%Y-%m-%d}" if fix.utc else "",
            "clockOffsetS": offset,  # horloge du Pi moins l'heure du GPS
            "fixAgeS": status.age_s if located else None,
            "firstFixS": status.first_fix_s,
            "errors": status.errors,
            "firmware": fix.firmware or "",
        }
        self.changed.emit()

    def _get_values(self) -> dict:
        return self._values

    def _get_satellites(self) -> list:
        return self._satellites

    values = Property("QVariantMap", _get_values, notify=changed)
    satellites = Property("QVariantList", _get_satellites, notify=satellitesChanged)
