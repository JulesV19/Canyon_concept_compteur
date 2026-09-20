"""Bus I2C de Linux (/dev/i2c-N), sans bibliothèque : chaque échange passe par l'ioctl I2C_RDWR.

Sur le compteur, tous les modules (jauge, GPS, puis baromètre…) partagent un bus logiciel (i2c-gpio) sur les GPIO 10
et 11 : celui du tactile de l'écran, ou, en attendant l'écran, celui posé par tools/pi/bus_capteurs.sh.
"""

import ctypes
import fcntl
import os
from pathlib import Path

I2C_RDWR = 0x0707  # plusieurs messages dans une même transaction, avec redémarrage entre eux
I2C_M_RD = 0x0001  # message en lecture


class _Message(ctypes.Structure):
    _fields_ = [("addr", ctypes.c_uint16), ("flags", ctypes.c_uint16), ("len", ctypes.c_uint16),
                ("buf", ctypes.POINTER(ctypes.c_uint8))]


class _Transfer(ctypes.Structure):
    _fields_ = [("msgs", ctypes.POINTER(_Message)), ("nmsgs", ctypes.c_uint32)]


class Bus:
    def __init__(self, number: int):
        self.number = number
        self._fd = os.open(f"/dev/i2c-{number}", os.O_RDWR)

    def close(self) -> None:
        os.close(self._fd)

    def transfer(self, address: int, write: bytes = b"", read: int = 0) -> bytes:
        """Écrit `write`, puis lit `read` octets, dans une seule transaction. Lève OSError si le module ne répond pas."""
        buffers = []
        if write:
            buffers.append((0, (ctypes.c_uint8 * len(write)).from_buffer_copy(write)))
        if read:
            buffers.append((I2C_M_RD, (ctypes.c_uint8 * read)()))
        messages = (_Message * len(buffers))(
            *(_Message(address, flags, len(buf), ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint8)))
              for flags, buf in buffers))
        fcntl.ioctl(self._fd, I2C_RDWR, _Transfer(messages, len(buffers)))
        return bytes(buffers[-1][1]) if read else b""

    def answers(self, address: int) -> bool:
        """Un module répond-il à cette adresse ? (lecture d'un octet, comme i2cdetect -r)"""
        try:
            self.transfer(address, read=1)
            return True
        except OSError:
            return False


def bus_numbers(dev: Path = Path("/dev")) -> list[int]:
    """Numéros des bus I2C ouverts par le noyau (module i2c-dev chargé)."""
    return sorted(int(path.name.removeprefix("i2c-")) for path in dev.glob("i2c-*")
                  if path.name.removeprefix("i2c-").isdigit())


def find(address: int) -> Bus | None:
    """Le premier bus où un module répond à `address`, ou None (pas de bus, pas de droit, module absent)."""
    for number in bus_numbers():
        try:
            bus = Bus(number)
        except OSError:
            continue
        if bus.answers(address):
            return bus
        bus.close()
    return None
