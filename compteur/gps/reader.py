"""Lecture des octets du GPS : les lignes NMEA, puis le Fix qu'elles décrivent."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from .fix import Fix, Satellite
from .nmea import KNOT_MPS, MAX_LINE, UNWANTED, coordinate, number, parse, satellite_system

# Heure plausible : avant d'avoir l'heure d'un satellite, le GPS part du 5 janvier 1980, soit « 80 », lu 2080
YEARS = range(2024, 2080)


@dataclass
class NmeaReader:
    """Assemble les lignes à partir des octets lus et tient le Fix à jour."""

    clock: Callable[[], float] = time.monotonic
    fix: Fix = Fix()
    unwanted: bool = False  # un message non voulu est arrivé : le réglage est à renvoyer
    _pending: bytearray = field(default_factory=bytearray)
    _in_view: dict[str, int] = field(default_factory=dict)  # satellites en vue, par constellation
    _sky: dict[str, list[Satellite]] = field(default_factory=dict)      # satellites en vue, par émetteur...
    _sky_next: dict[str, list[Satellite]] = field(default_factory=dict)  # ... et ceux de la série GSV en cours
    _gsa_open: bool = False  # une ligne GSA est arrivée depuis la dernière GGA (début de chaque seconde)
    lines: list[str] = field(default_factory=list)  # lignes valides reçues depuis la dernière lecture (pour l'essai)

    def feed(self, data: bytes) -> bool:
        """Ajoute les octets lus ; renvoie faux s'il n'y avait rien (que des sauts de ligne de remplissage).

        Le GPS rend toujours autant d'octets qu'on lui en demande : quand il n'a plus rien à dire, il complète par des
        sauts de ligne, y compris au milieu d'une phrase. Seule la fin de ligne de la norme NMEA, « \r\n », termine donc
        une phrase ; un saut de ligne seul est du remplissage, et la suite de la phrase arrive à la lecture suivante.
        """
        for byte in data:
            if byte == 0x0A:
                if self._pending.endswith(b"\r"):
                    self._line_end()
            elif byte == 0x24:  # « $ » : début d'une phrase ; ce qui précède est resté en plan, on repart de là
                self._pending.clear()
                self._pending.append(byte)
            elif len(self._pending) < MAX_LINE:
                self._pending.append(byte)
            else:
                self._pending.clear()  # bruit sans fin de ligne
        return bool(data.strip(b"\n"))

    def _line_end(self) -> None:
        text = self._pending.decode("ascii", errors="replace")
        self._pending.clear()
        if (parsed := parse(text)) is None:
            return
        self.lines.append(text.strip())
        kind, fields = parsed
        if kind == "RMC" and len(fields) >= 9:
            self._rmc(fields)
        elif kind == "GGA" and len(fields) >= 9:
            self._gga(fields)
        elif kind == "GSV" and len(fields) >= 3:
            talker = text.strip()[1:3]
            if fields[1] == "1" and (count := number(fields[2])) is not None:
                self._in_view[talker] = int(count)
                self.fix = replace(self.fix, in_view=sum(self._in_view.values()))
            self._gsv(talker, fields)
        elif kind == "GSA" and len(fields) >= 17:
            self._gsa(fields)
        elif kind == "PMTK705" and fields:
            self.fix = replace(self.fix, firmware=fields[0])
        elif kind in UNWANTED:
            self.unwanted = True

    def _rmc(self, fields: list[str]) -> None:
        valid = fields[1] == "A"
        utc = None
        clock, day = fields[0], fields[8]
        if len(clock) >= 6 and len(day) == 6 and clock[:6].isdigit() and day.isdigit():
            try:
                utc = datetime(2000 + int(day[4:6]), int(day[2:4]), int(day[0:2]), int(clock[0:2]), int(clock[2:4]),
                               int(clock[4:6]), tzinfo=timezone.utc)
            except ValueError:
                pass
            if utc is not None and utc.year not in YEARS:
                utc = None  # horloge du GPS pas encore réglée
        speed = number(fields[6])
        self.fix = replace(
            self.fix, valid=valid, utc=utc, received=self.clock(),
            lat=coordinate(fields[2], fields[3]) if valid else None,
            lon=coordinate(fields[4], fields[5]) if valid else None,
            speed_mps=speed * KNOT_MPS if valid and speed is not None else None,
            heading_deg=number(fields[7]) if valid else None)

    def _gga(self, fields: list[str]) -> None:
        used = number(fields[6])
        quality = number(fields[5]) or 0
        self.fix = replace(self.fix, satellites=int(used) if used is not None else 0, hdop=number(fields[7]),
                           altitude_m=number(fields[8]) if quality > 0 else None, quality=int(quality))
        self._gsa_open = False

    def _gsv(self, talker: str, fields: list[str]) -> None:
        """Une ligne d'une série GSV (4 satellites au plus par ligne) ; la série finie remplace la précédente."""
        total, index = number(fields[0]), number(fields[1])
        if total is None or index is None:
            return
        if index == 1:
            self._sky_next[talker] = []
        batch = self._sky_next.get(talker)
        if batch is None:
            return  # série prise en cours de route
        for i in range(3, len(fields) - 3, 4):
            prn = number(fields[i])
            if prn is None:
                continue
            elevation, azimuth, snr = (number(value) for value in fields[i + 1:i + 4])
            batch.append(Satellite(satellite_system(talker, int(prn)), int(prn),
                                   None if elevation is None else int(elevation),
                                   None if azimuth is None else int(azimuth), None if snr is None else int(snr)))
        if index == total:
            batch = self._sky_next.pop(talker)
            expected = number(fields[2])
            if expected is not None and len(batch) < int(expected):
                return  # une ligne de la série s'est perdue : on garde le ciel précédent plutôt qu'un ciel tronqué
            self._sky[talker] = batch
            self.fix = replace(self.fix, sky=tuple(sat for sats in self._sky.values() for sat in sats))

    def _gsa(self, fields: list[str]) -> None:
        """Satellites utilisés : une ligne GSA par constellation, à réunir dans la même seconde."""
        prns = {int(value) for value in fields[2:14] if value.isdigit()}
        used = prns if not self._gsa_open else self.fix.used | prns
        fix_type = number(fields[1])
        fix_type = int(fix_type) if fix_type else 1
        if self._gsa_open:
            fix_type = max(fix_type, self.fix.fix_type)  # GLONASS sans position n'efface pas celle trouvée par le GPS
        self._gsa_open = True
        self.fix = replace(self.fix, used=frozenset(used), fix_type=fix_type,
                           pdop=number(fields[14]), vdop=number(fields[16]))
