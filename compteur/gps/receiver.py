"""Le GPS lu en continu sur le bus I2C, dans un fil à part."""

import threading
import time
from collections.abc import Callable

from .fix import Fix
from .nmea import OUTPUT, QUERY_FIRMWARE
from .reader import NmeaReader
from .status import Status

ADDRESS = 0x10
CHUNK = 64               # octets lus par échange : le GPS en garde 255 au plus
IDLE_S = 0.25            # rien à lire : pause avant l'échange suivant (le GPS envoie ≈ 200 octets/s)
RETRY_S = 1.0            # bus en erreur : pause avant de réessayer
STALE_S = 3.0            # plus de position depuis 3 s : le GPS ne répond plus
SEARCH_S = 10.0          # GPS introuvable (pas encore branché) : on le cherche toutes les 10 s
CONFIGURE_EVERY_S = 10.0  # réglage des messages renvoyé au plus toutes les 10 s, s'il a été perdu


class Receiver:
    """Le GPS lu en continu par un fil à part. `fix()` et `status()` donnent le dernier état, sans attendre le bus.
    Sans `bus`, `find()` le cherche toutes les 10 s (GPS pas encore branché)."""

    def __init__(self, bus=None, clock: Callable[[], float] = time.monotonic,
                 find: Callable[[], object | None] | None = None):
        self.bus = bus
        self.clock = clock
        self.errors = 0  # échanges ratés depuis le départ (fils mal branchés, bus saturé)
        self._find = find
        self._searched_at: float | None = None
        self._reader = NmeaReader(clock)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._configured_at: float | None = None
        self._queried_at: float | None = None  # dernière demande de la version du micrologiciel
        self._started = clock()
        self._last_data: float | None = None   # dernier échange qui a apporté des octets
        self._first_fix: float | None = None
        self._thread = threading.Thread(target=self._run, name="gps", daemon=True)

    def start(self) -> "Receiver":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def fix(self) -> Fix:
        with self._lock:
            fix = self._reader.fix
        if fix.received is not None and self.clock() - fix.received > STALE_S:
            return Fix(in_view=fix.in_view, firmware=fix.firmware)  # plus rien depuis 3 s : position perdue
        return fix

    def status(self) -> Status:
        now = self.clock()
        with self._lock:
            received, last, first = self._reader.fix.received, self._last_data, self._first_fix
        present = last is not None and now - last <= STALE_S
        fix = self.fix() if present else Fix(firmware=self.fix().firmware)
        return Status(fix, present, now - received if received is not None else None, first, self.errors)

    def take_lines(self) -> list[str]:
        """Lignes NMEA reçues depuis le dernier appel."""
        with self._lock:
            lines, self._reader.lines = self._reader.lines, []
        return lines

    def _configure(self) -> None:
        now = self.clock()
        if self._configured_at is None or now - self._configured_at >= CONFIGURE_EVERY_S:
            self.bus.transfer(ADDRESS, OUTPUT)
            self._configured_at = now
            self._reader.unwanted = False

    def _query_firmware(self) -> None:
        now = self.clock()
        if self._reader.fix.firmware is None and (self._queried_at is None
                                                  or now - self._queried_at >= CONFIGURE_EVERY_S):
            self.bus.transfer(ADDRESS, QUERY_FIRMWARE)
            self._queried_at = now

    def _search(self) -> bool:
        """Le bus du GPS, cherché s'il manque ; faux tant qu'on ne l'a pas."""
        if self.bus is None and self._find is not None:
            now = self.clock()
            if self._searched_at is None or now - self._searched_at >= SEARCH_S:
                self._searched_at = now
                self.bus = self._find()
        return self.bus is not None

    def _run(self) -> None:
        while not self._stop.is_set():
            if not self._search():
                self._stop.wait(RETRY_S)
                continue
            try:
                if self._configured_at is None or self._reader.unwanted:
                    self._configure()
                self._query_firmware()
                data = self.bus.transfer(ADDRESS, read=CHUNK)
            except OSError:
                self.errors += 1
                self._stop.wait(RETRY_S)
                continue
            with self._lock:
                busy = self._reader.feed(data)
                if busy:
                    self._last_data = self.clock()
                if self._first_fix is None and self._reader.fix.valid:
                    self._first_fix = self.clock() - self._started
                if len(self._reader.lines) > 200:  # personne ne les prend : on garde les dernières
                    del self._reader.lines[:-50]
            if not busy:
                self._stop.wait(IDLE_S)
