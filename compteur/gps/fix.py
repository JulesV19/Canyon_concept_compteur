"""Ce que le GPS sait : satellites en vue et dernier état (position, vitesse, heure, précision)."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Satellite:
    system: str               # GPS, GLONASS, Galileo, BeiDou, QZSS, SBAS
    prn: int                  # numéro du satellite
    elevation: int | None     # degrés au-dessus de l'horizon
    azimuth: int | None       # degrés depuis le nord
    snr: int | None           # signal en dB-Hz ; None : en vue, mais pas capté


@dataclass(frozen=True)
class Fix:
    """Dernier état connu du GPS. `valid` : position trouvée (sinon position, vitesse et cap sont absents)."""

    valid: bool = False
    lat: float | None = None
    lon: float | None = None
    speed_mps: float | None = None
    heading_deg: float | None = None
    altitude_m: float | None = None
    utc: datetime | None = None
    satellites: int = 0  # utilisés pour la position
    in_view: int = 0     # en vue, toutes constellations
    hdop: float | None = None  # dispersion horizontale : < 1 excellent, > 5 médiocre
    received: float | None = None  # horloge monotone de la dernière position (RMC)
    quality: int = 0           # GGA : 0 aucune position, 1 GPS, 2 corrigée par SBAS (EGNOS)…
    fix_type: int = 1          # GSA : 1 aucune position, 2 en 2D (sans altitude), 3 en 3D
    pdop: float | None = None  # dispersion en 3D
    vdop: float | None = None  # dispersion verticale
    used: frozenset[int] = frozenset()   # numéros des satellites utilisés (GSA)
    sky: tuple[Satellite, ...] = ()      # satellites en vue, avec leur place et leur signal (GSV)
    firmware: str | None = None          # version du micrologiciel (PMTK705)
