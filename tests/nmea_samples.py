"""Pour les essais du GPS : lignes NMEA d'exemple, et un faux bus I2C."""

from compteur import gps
from compteur.gps import command

# Exemples classiques de la norme NMEA 0183, avec leur somme de contrôle
RMC = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
GGA = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"


def sentence(body: str) -> str:
    return command(body).decode().strip()


def feed(reader, *bodies):
    for body in bodies:
        reader.feed((sentence(body) + "\r\n").encode())


class FakeBus:
    """Le GPS vu du bus : il rend ses lignes par morceaux, puis des sauts de ligne."""

    def __init__(self, text: str):
        self.data = bytearray(text.encode())
        self.written = []

    def transfer(self, address, write=b"", read=0):
        assert address == gps.ADDRESS
        if write:
            self.written.append(write)
        chunk = bytes(self.data[:read])
        del self.data[:read]
        return chunk + b"\n" * (read - len(chunk))
