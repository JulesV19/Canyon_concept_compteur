"""L'heure du GPS contre l'horloge du système."""

from datetime import datetime, timedelta

from .fix import Fix

# Écart toléré entre l'horloge du système et l'heure du GPS : au-delà, on remet l'horloge à l'heure. Large devant le
# retard des lignes NMEA (0,15 à 0,5 s mesurés sur le Pi), pour ne jamais contrarier NTP quand il y a du réseau
CLOCK_TOLERANCE_S = 2.0
CLOCK_SAMPLES = 10       # lignes RMC par estimation de l'écart


class ClockCheck:
    """Écart entre l'heure du GPS et l'horloge du système, estimé sur CLOCK_SAMPLES lignes RMC. Une ligne lue en retard
    (au démarrage de l'appli, le fil du GPS attend son tour : 3 s mesurées sur le Pi) fait paraître le GPS en retard,
    jamais en avance : l'écart retenu est donc le plus grand. Rien sans position : avant, le module peut donner l'heure
    de sa propre horloge, pas toujours juste."""

    def __init__(self):
        self.samples: list[float] = []
        self.last: datetime | None = None  # heure de la dernière ligne comptée : chaque ligne ne compte qu'une fois

    def offset(self, fix: Fix, now: float, system_utc: datetime) -> float | None:
        """Écart en s (positif : l'horloge du système retarde) une fois assez de lignes vues, sinon None. `now` :
        horloge monotone, celle de `fix.received`."""
        if not fix.valid or fix.utc is None or fix.received is None or fix.utc == self.last:
            return None
        self.last = fix.utc
        gps_utc = fix.utc + timedelta(seconds=now - fix.received)
        self.samples.append((gps_utc - system_utc).total_seconds())
        if len(self.samples) < CLOCK_SAMPLES:
            return None
        offset, self.samples = max(self.samples), []
        return offset
