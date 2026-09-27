"""Les mesures de la sortie prises sur le GPS."""

from ..ride import Sample
from .receiver import Receiver
from .status import bars


class GpsRider:
    """Les mesures de la sortie prises sur le GPS : vitesse, position, altitude et cap. Même forme que le cycliste
    simulé de sim.py, pour que l'appli prenne l'un ou l'autre selon ce qui est branché."""

    def __init__(self, receiver: Receiver):
        self.receiver = receiver

    def sample(self, t: float, riding: bool = True) -> Sample:
        """Mesures à l'instant t. Sans position (GPS en recherche, ou muet depuis 3 s), tout est absent : le compteur
        laisse alors la distance et le chrono où ils en sont (voir ride.py). `riding` ne sert qu'au cycliste simulé."""
        fix = self.receiver.fix()
        if not fix.valid:
            return Sample(t=t)
        return Sample(t=t, speed_mps=fix.speed_mps, lat=fix.lat, lon=fix.lon, altitude_m=fix.altitude_m,
                      heading_deg=fix.heading_deg)

    def device_status(self, t: float) -> dict:
        """État du boîtier pour l'accueil et la barre d'état. Pas de ceinture cardio branchée pour l'instant : le
        cardio reste « Non connectée », et la batterie est ajoutée par l'appli quand la jauge répond."""
        status = self.receiver.status()
        return {"gpsBars": bars(status), "gpsFix": status.fix.valid, "hrConnected": False}
