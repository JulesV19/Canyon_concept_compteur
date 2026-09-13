"""Enregistrement d'une sortie au format FIT (Garmin), celui qu'attendent Strava et Garmin Connect.

Le compteur écrit lui-même ce qu'il faut du protocole FIT pour une activité vélo, sans dépendance :
en-tête, messages de définition puis de données, CRC. Messages écrits : identité du fichier,
départs et arrêts du chrono, une mesure par seconde, tours, séance et activité.
"""

import math
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .ride import Ride, Segment

FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)  # origine des dates FIT
PROTOCOL_VERSION = 0x10  # FIT 1.0 : lu partout
PROFILE_VERSION = 2132
SEMICIRCLES_PER_DEGREE = 2**31 / 180  # les positions FIT sont en « semicercles »

# Valeurs du profil FIT
FILE_ACTIVITY = 4
MANUFACTURER_DEVELOPMENT = 255
SPORT_CYCLING = 2
SUB_SPORT_ROAD = 7
EVENT_TIMER, EVENT_SESSION, EVENT_LAP, EVENT_ACTIVITY = 0, 8, 9, 26
EVENT_START, EVENT_STOP, EVENT_STOP_ALL = 0, 1, 4
LAP_MANUAL, LAP_SESSION_END = 0, 7


@dataclass(frozen=True)
class BaseType:
    """Type de base FIT : code, format `struct` (petit-boutiste) et valeur « absente »."""

    code: int
    fmt: str
    invalid: int

    @property
    def size(self) -> int:
        return struct.calcsize("<" + self.fmt)

    def valid(self, value: int) -> bool:
        """Vrai si le type sait écrire cette valeur, autre que sa valeur « absente »."""
        bits = 8 * self.size
        low, high = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if self.fmt.islower() else (0, (1 << bits) - 1)
        return low <= value <= high and value != self.invalid


ENUM = BaseType(0x00, "B", 0xFF)
UINT8 = BaseType(0x02, "B", 0xFF)
UINT16 = BaseType(0x84, "H", 0xFFFF)
SINT32 = BaseType(0x85, "i", 0x7FFFFFFF)
UINT32 = BaseType(0x86, "I", 0xFFFFFFFF)
UINT32Z = BaseType(0x8C, "I", 0)

# Messages écrits : numéro global FIT, puis leurs champs (nom, numéro, type) dans l'ordre d'écriture
MESSAGES = {
    "file_id": (0, [("type", 0, ENUM), ("manufacturer", 1, UINT16), ("product", 2, UINT16),
                    ("serial_number", 3, UINT32Z), ("time_created", 4, UINT32)]),
    "event": (21, [("timestamp", 253, UINT32), ("event", 0, ENUM), ("event_type", 1, ENUM)]),
    "record": (20, [("timestamp", 253, UINT32), ("position_lat", 0, SINT32), ("position_long", 1, SINT32),
                    ("altitude", 2, UINT16), ("heart_rate", 3, UINT8), ("distance", 5, UINT32),
                    ("speed", 6, UINT16)]),
    "lap": (19, [("timestamp", 253, UINT32), ("message_index", 254, UINT16), ("event", 0, ENUM),
                 ("event_type", 1, ENUM), ("start_time", 2, UINT32), ("total_elapsed_time", 7, UINT32),
                 ("total_timer_time", 8, UINT32), ("total_distance", 9, UINT32), ("avg_speed", 13, UINT16),
                 ("max_speed", 14, UINT16), ("avg_heart_rate", 15, UINT8), ("max_heart_rate", 16, UINT8),
                 ("total_ascent", 21, UINT16), ("total_descent", 22, UINT16), ("lap_trigger", 24, ENUM),
                 ("sport", 25, ENUM)]),
    "session": (18, [("timestamp", 253, UINT32), ("message_index", 254, UINT16), ("event", 0, ENUM),
                     ("event_type", 1, ENUM), ("start_time", 2, UINT32), ("sport", 5, ENUM),
                     ("sub_sport", 6, ENUM), ("total_elapsed_time", 7, UINT32), ("total_timer_time", 8, UINT32),
                     ("total_distance", 9, UINT32), ("avg_speed", 14, UINT16), ("max_speed", 15, UINT16),
                     ("avg_heart_rate", 16, UINT8), ("max_heart_rate", 17, UINT8), ("total_ascent", 22, UINT16),
                     ("total_descent", 23, UINT16), ("first_lap_index", 25, UINT16), ("num_laps", 26, UINT16),
                     ("trigger", 28, ENUM)]),
    "activity": (34, [("timestamp", 253, UINT32), ("total_timer_time", 0, UINT32), ("num_sessions", 1, UINT16),
                      ("type", 2, ENUM), ("event", 3, ENUM), ("event_type", 4, ENUM),
                      ("local_timestamp", 5, UINT32)]),
}

_CRC_TABLE = (0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
              0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400)


def crc16(data: bytes, crc: int = 0) -> int:
    """CRC du protocole FIT."""
    for byte in data:
        for nibble in (byte & 0x0F, byte >> 4):
            tmp = _CRC_TABLE[crc & 0x0F]
            crc = (crc >> 4) & 0x0FFF
            crc ^= tmp ^ _CRC_TABLE[nibble]
    return crc


class FitWriter:
    """Assemble un fichier FIT. Chaque sorte de message reçoit un numéro local (0 à 15),
    et sa définition est écrite juste avant son premier message."""

    def __init__(self):
        self._data = bytearray()
        self._local: dict[str, int] = {}

    def write(self, name: str, **values: int | None) -> None:
        """Ajoute un message ; les valeurs sont déjà à l'échelle FIT, None pour « absente ». Une valeur que le champ ne
        sait pas écrire (pic GPS, défaut d'un capteur) est écrite « absente » : elle ne peut pas empêcher d'enregistrer
        la sortie."""
        number, fields = MESSAGES[name]
        unknown = values.keys() - {key for key, _, _ in fields}
        if unknown:
            raise ValueError(f"champs inconnus pour {name} : {sorted(unknown)}")
        if name not in self._local:
            local = self._local[name] = len(self._local)
            self._data += struct.pack("<BBBHB", 0x40 | local, 0, 0, number, len(fields))
            for _, field, base in fields:
                self._data += struct.pack("<BBB", field, base.size, base.code)
        self._data.append(self._local[name])
        for key, _, base in fields:
            value = values.get(key)
            self._data += struct.pack("<" + base.fmt, value if value is not None and base.valid(value) else base.invalid)

    def to_bytes(self) -> bytes:
        header = struct.pack("<BBHI4s", 14, PROTOCOL_VERSION, PROFILE_VERSION, len(self._data), b".FIT")
        header += struct.pack("<H", crc16(header))
        content = header + self._data
        return content + struct.pack("<H", crc16(content))


def _timestamp(when: datetime) -> int:
    """Date FIT : secondes depuis le 31 décembre 1989 (UTC)."""
    return round((when - FIT_EPOCH).total_seconds())


def _scaled(value: float | None, scale: float, offset: float = 0.0) -> int | None:
    """Valeur à l'échelle FIT ; None si elle manque ou n'est pas un nombre fini."""
    if value is None:
        return None
    scaled = (value + offset) * scale
    return round(scaled) if math.isfinite(scaled) else None


def _rounded(value: float | None) -> int | None:
    return _scaled(value, 1)


def _totals(segment: Segment) -> dict:
    """Compteurs communs aux tours et à la séance."""
    return {
        "total_timer_time": _scaled(segment.timer_s, 1000),
        "total_distance": _scaled(segment.distance_m, 100),
        "avg_speed": _scaled(segment.avg_speed_mps, 1000),
        "max_speed": _scaled(segment.max_speed_mps, 1000),
        "avg_heart_rate": _rounded(segment.heart_rate.mean),
        "max_heart_rate": _rounded(segment.heart_rate.max),
        "total_ascent": _rounded(segment.ascent_m),
        "total_descent": _rounded(segment.descent_m),
    }


def encode_activity(ride: Ride, started_at: datetime) -> bytes:
    """La sortie au format FIT. `started_at` : date et heure du départ, avec son fuseau."""
    t0 = ride.total.start_t if ride.total.start_t is not None else 0.0
    end_t = ride.last_t
    start = _timestamp(started_at)

    def when(t: float) -> int:
        return start + round(t - t0)

    fit = FitWriter()
    fit.write("file_id", type=FILE_ACTIVITY, manufacturer=MANUFACTURER_DEVELOPMENT, product=0,
              serial_number=1, time_created=start)

    # Mesures, départs et arrêts du chrono, dans l'ordre. À la même seconde, un départ passe avant
    # la mesure et un arrêt après.
    timeline = [(t, 0 if running else 2, running) for t, running in ride.timer_events]
    timeline += [(record.sample.t, 1, record) for record in ride.records]
    for t, _, item in sorted(timeline, key=lambda entry: entry[:2]):
        if isinstance(item, bool):
            fit.write("event", timestamp=when(t), event=EVENT_TIMER,
                      event_type=EVENT_START if item else EVENT_STOP_ALL)
        else:
            sample = item.sample
            fit.write("record", timestamp=when(t),
                      position_lat=_scaled(sample.lat, SEMICIRCLES_PER_DEGREE),
                      position_long=_scaled(sample.lon, SEMICIRCLES_PER_DEGREE),
                      altitude=_scaled(sample.altitude_m, 5, 500), heart_rate=_rounded(sample.heart_rate),
                      distance=_scaled(item.distance_m, 100), speed=_scaled(sample.speed_mps, 1000))
    if ride.timer_events and ride.timer_events[-1][1]:
        fit.write("event", timestamp=when(end_t), event=EVENT_TIMER, event_type=EVENT_STOP_ALL)

    for index, lap in enumerate(ride.laps):
        last = index == len(ride.laps) - 1
        lap_start = lap.start_t if lap.start_t is not None else t0
        lap_end = end_t if last else ride.laps[index + 1].start_t
        fit.write("lap", timestamp=when(lap_end), message_index=index, event=EVENT_LAP, event_type=EVENT_STOP,
                  start_time=when(lap_start), total_elapsed_time=_scaled(lap_end - lap_start, 1000),
                  lap_trigger=LAP_SESSION_END if last else LAP_MANUAL, sport=SPORT_CYCLING, **_totals(lap))

    total = ride.total
    fit.write("session", timestamp=when(end_t), message_index=0, event=EVENT_SESSION, event_type=EVENT_STOP,
              start_time=start, sport=SPORT_CYCLING, sub_sport=SUB_SPORT_ROAD,
              total_elapsed_time=_scaled(end_t - t0, 1000), first_lap_index=0, num_laps=len(ride.laps),
              trigger=0, **_totals(total))
    local_offset = round((started_at.utcoffset() or timedelta()).total_seconds())
    fit.write("activity", timestamp=when(end_t), total_timer_time=_scaled(total.timer_s, 1000), num_sessions=1,
              type=0, event=EVENT_ACTIVITY, event_type=EVENT_STOP, local_timestamp=when(end_t) + local_offset)
    return fit.to_bytes()
