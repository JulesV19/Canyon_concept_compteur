"""Réglages du compteur : gardés d'une mise en route à l'autre, dans un petit fichier JSON."""

import json
import sys
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot

from .ride import DEFAULT_MAX_HR, HR_ZONE_BOUNDS
from .storage import write_atomic

SETTINGS_FILE = Path.home() / ".config" / "canyon-compteur" / "reglages.json"
BACKLIGHT_DIR = Path("/sys/class/backlight")  # rétroéclairage de l'écran, sur le Pi
MAX_HR_RANGE = (120, 220)
BRIGHTNESS_RANGE = (10, 100)  # en %, l'écran n'est jamais complètement éteint


def _clamp(value: int, bounds: tuple[int, int]) -> int:
    return min(max(value, bounds[0]), bounds[1])


@dataclass(frozen=True)
class Settings:
    max_hr: int = DEFAULT_MAX_HR  # FC max, d'où découlent les zones cardio
    auto_pause: bool = True
    brightness: int = 80          # rétroéclairage, en %

    def checked(self) -> "Settings":
        """Les mêmes réglages, ramenés dans les limites permises (ValueError, TypeError ou OverflowError s'ils sont
        illisibles)."""
        return Settings(max_hr=_clamp(int(self.max_hr), MAX_HR_RANGE),
                        auto_pause=bool(self.auto_pause),
                        brightness=_clamp(int(self.brightness), BRIGHTNESS_RANGE))

    @classmethod
    def load(cls, path: Path = SETTINGS_FILE) -> "Settings":
        """Réglages enregistrés ; ceux par défaut si le fichier manque ou est illisible."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = {field.name for field in fields(cls)}
            return cls(**{key: value for key, value in data.items() if key in known}).checked()
        except (OSError, ValueError, TypeError, AttributeError, OverflowError):
            return cls()

    def save(self, path: Path = SETTINGS_FILE) -> None:
        """Écrit les réglages d'un coup et les force sur la carte : jamais de fichier vide ou à moitié écrit, même si
        le courant est coupé."""
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(path, json.dumps(asdict(self), indent=2).encode("utf-8"))


def apply_brightness(percent: int, root: Path = BACKLIGHT_DIR) -> bool:
    """Règle le rétroéclairage de l'écran (Pi). Sans écran réglable (Mac), ne fait rien et renvoie False."""
    for device in sorted(root.glob("*")):
        try:
            maximum = int((device / "max_brightness").read_text())
            (device / "brightness").write_text(str(round(maximum * percent / 100)))
            return True
        except (OSError, ValueError):
            continue
    return False


class SettingsModel(QObject):
    """Expose les réglages à QML : `settings.values.maxHr`, `settings.set("maxHr", 185)`...
    `preview` change un réglage sans l'enregistrer (curseur en cours de glissement, bouton maintenu)."""

    changed = Signal()
    KEYS = {"maxHr": "max_hr", "autoPause": "auto_pause", "brightness": "brightness"}

    def __init__(self, path: Path = SETTINGS_FILE, parent: QObject | None = None):
        super().__init__(parent)
        self._path = path
        self.current = Settings.load(path)

    def _get_values(self) -> dict:
        s = self.current
        return {
            "maxHr": s.max_hr,
            "autoPause": s.auto_pause,
            "brightness": s.brightness,
            "zoneBounds": [round(bound * s.max_hr) for bound in HR_ZONE_BOUNDS],  # début des zones 2 à 5
        }

    values = Property("QVariantMap", _get_values, notify=changed)

    @Slot(str, "QVariant")
    def preview(self, key: str, value) -> None:
        try:
            self.current = replace(self.current, **{self.KEYS[key]: value}).checked()
        except (ValueError, TypeError, OverflowError):
            return  # valeur illisible : le réglage ne change pas
        self.changed.emit()

    @Slot(str, "QVariant")
    def set(self, key: str, value) -> None:
        self.preview(key, value)
        try:
            self.current.save(self._path)
        except OSError as error:  # carte pleine ou en lecture seule : le réglage vaut jusqu'à l'arrêt
            print(f"Réglages non enregistrés : {error}", file=sys.stderr)
