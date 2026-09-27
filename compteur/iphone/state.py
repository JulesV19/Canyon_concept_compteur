"""État partagé entre le fil Bluetooth et l'interface : ce que l'iPhone a envoyé."""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from .ams import Music, apply_update
from .ancs import Notification


@dataclass
class State:
    connected: bool = False
    name: str = ""          # nom de l'iPhone, ex. « iPhone de Jules »
    notifications: dict[int, Notification] = field(default_factory=dict)  # celles encore sur l'iPhone
    music: Music = field(default_factory=Music)
    # Ce que l'écran montre : tout ce qui est arrivé depuis la connexion, même retiré depuis du centre de notifications
    # (message lu sur l'iPhone, appel terminé), dans l'ordre d'arrivée
    history: dict[int, Notification] = field(default_factory=dict)
    read: set[int] = field(default_factory=set)  # vus sur le compteur
    battery: int = -1  # charge de l'iPhone, % ; -1 : inconnue
    version: int = 0  # augmente à chaque changement : l'écran ne se redessine que s'il a bougé


class PhoneState:
    """Ce que l'iPhone a envoyé, lu par l'interface ; les événements partent vers `listener`, depuis le fil Bluetooth."""

    def __init__(self, listener: Callable[[str, object], None] | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self.lock = threading.Lock()
        self.state = State()
        self.arrivals: list[Notification] = []
        self.listener = listener
        self.clock = clock

    def _emit(self, kind: str, data: object) -> None:
        if self.listener:
            self.listener(kind, data)

    def connection(self, connected: bool, name: str = "") -> None:
        with self.lock:
            self.state.connected, self.state.name = connected, name
            if not connected:
                self.state.notifications.clear()
                self.state.history.clear()
                self.state.read.clear()
                self.state.music = Music()
                self.state.battery = -1
                self.arrivals.clear()
            self.state.version += 1
        self._emit("connected" if connected else "disconnected", name)

    def notification(self, item: Notification) -> None:
        with self.lock:
            modified = item.uid in self.state.notifications
            self.state.notifications[item.uid] = item
            self.state.history[item.uid] = item
            if not modified and not item.pre_existing:
                self.arrivals.append(item)
            self.state.version += 1
        self._emit("modified" if modified else "added", item)

    def removed(self, uid: int) -> None:
        with self.lock:
            item = self.state.notifications.pop(uid, None)
            self.state.version += 1
        if item:
            self._emit("removed", item)

    def music_update(self, entity: int, attribute: int, value: str) -> None:
        with self.lock:
            self.state.music = apply_update(self.state.music, entity, attribute, value, self.clock())
            self.state.version += 1
            music = self.state.music
        self._emit("music", music)

    def battery(self, level: int) -> None:
        with self.lock:
            self.state.battery = level
            self.state.version += 1

    def mark_read(self, kind: str) -> None:
        """Tout ce que cette appli (« messages », « whatsapp », « phone ») a reçu est vu : ses pastilles s'effacent."""
        with self.lock:
            self.state.read.update(uid for uid, item in self.state.history.items() if item.kind == kind)
            self.state.version += 1

    def take_arrivals(self) -> list[Notification]:
        """Notifications arrivées depuis le dernier appel (pas celles déjà là à la connexion) : pour les bandeaux."""
        with self.lock:
            arrivals, self.arrivals = self.arrivals, []
        return arrivals

    def snapshot(self) -> State:
        with self.lock:
            state = self.state
            return State(connected=state.connected, name=state.name, notifications=dict(state.notifications),
                         music=state.music, history=dict(state.history), read=set(state.read), battery=state.battery,
                         version=state.version)
