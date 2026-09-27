"""AMS (Apple Media Service) : le morceau en cours et les commandes de lecture."""

from dataclasses import dataclass, replace


AMS_SERVICE = "89d3502b-0f36-433a-8ef4-c502ad55f8dc"
AMS_REMOTE_COMMAND = "9b3c81d8-57b1-4a8a-b8df-0e56f7ca51c2"
AMS_ENTITY_UPDATE = "2f7cabce-808d-411f-9a0c-bb92ba96c102"
AMS_ENTITY_ATTRIBUTE = "c6b2f38c-23ab-46d8-a6ab-a3a870bbd5d7"

PLAYER, QUEUE, TRACK = 0, 1, 2
PLAYER_NAME, PLAYER_PLAYBACK, PLAYER_VOLUME = 0, 1, 2
QUEUE_SHUFFLE, QUEUE_REPEAT = 2, 3  # 0 : non ; 1 : un seul (morceau, album) ; 2 : tout
TRACK_ARTIST, TRACK_ALBUM, TRACK_TITLE, TRACK_DURATION = 0, 1, 2, 3
# Abonnements : une écriture par entité, suivie des attributs voulus
SUBSCRIPTIONS = [bytes([PLAYER, PLAYER_NAME, PLAYER_PLAYBACK, PLAYER_VOLUME]),
                 bytes([QUEUE, QUEUE_SHUFFLE, QUEUE_REPEAT]),
                 bytes([TRACK, TRACK_ARTIST, TRACK_ALBUM, TRACK_TITLE, TRACK_DURATION])]
FLAG_TRUNCATED = 1
COMMANDS = {"play": 0, "pause": 1, "toggle": 2, "next": 3, "previous": 4, "volume_up": 5, "volume_down": 6,
            "repeat": 7, "shuffle": 8}  # repeat, shuffle : passent au mode suivant

# Service Batterie : l'iPhone y donne sa charge
BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb"


@dataclass(frozen=True)
class Music:
    player: str = ""       # nom de l'appli qui joue, ex. « Musique »
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0  # s
    playing: bool = False
    rate: float = 0.0
    elapsed: float = 0.0   # s, à l'instant `at`
    at: float = 0.0        # horloge monotone de la dernière position reçue
    volume: float = 0.0    # 0 à 1
    shuffle: int = 0       # QUEUE_SHUFFLE
    repeat: int = 0        # QUEUE_REPEAT

    def position(self, now: float) -> float:
        """Position dans le morceau maintenant : l'iPhone n'envoie la position qu'aux changements (pause, saut)."""
        value = self.elapsed + self.rate * (now - self.at)
        return min(max(value, 0.0), self.duration) if self.duration else max(value, 0.0)


@dataclass(frozen=True)
class EntityUpdate:
    entity: int
    attribute: int
    truncated: bool
    value: str


def parse_entity_update(data: bytes) -> EntityUpdate | None:
    if len(data) < 3:
        return None
    return EntityUpdate(data[0], data[1], bool(data[2] & FLAG_TRUNCATED), data[3:].decode("utf-8", "replace"))


def number(text: str) -> float:
    try:
        return float(text)
    except ValueError:
        return 0.0


def apply_update(music: Music, entity: int, attribute: int, value: str, now: float) -> Music:
    if entity == PLAYER and attribute == PLAYER_NAME:
        return replace(music, player=value)
    if entity == PLAYER and attribute == PLAYER_PLAYBACK:
        # « état,vitesse,écoulé » ; état 0 pause, 1 lecture, 2 retour rapide, 3 avance rapide
        parts = value.split(",")
        if len(parts) != 3:
            return music
        return replace(music, playing=parts[0] in ("1", "2", "3"), rate=number(parts[1]),
                       elapsed=number(parts[2]), at=now)
    if entity == PLAYER and attribute == PLAYER_VOLUME:
        return replace(music, volume=number(value))
    if entity == QUEUE and attribute == QUEUE_SHUFFLE:
        return replace(music, shuffle=int(number(value)))
    if entity == QUEUE and attribute == QUEUE_REPEAT:
        return replace(music, repeat=int(number(value)))
    if entity == TRACK:
        if attribute == TRACK_TITLE:
            return replace(music, title=value)
        if attribute == TRACK_ARTIST:
            return replace(music, artist=value)
        if attribute == TRACK_ALBUM:
            return replace(music, album=value)
        if attribute == TRACK_DURATION:
            return replace(music, duration=number(value))
    return music
