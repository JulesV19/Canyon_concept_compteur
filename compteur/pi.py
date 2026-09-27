"""Ce qui est propre au Raspberry Pi : le reconnaître, l'environnement Qt de son écran, l'arrêt du système."""

import subprocess
import sys
from pathlib import Path

PI_MODEL_FILE = Path("/proc/device-tree/model")  # modèle de la carte électronique, sur le Pi
# Sur le Pi, sans bureau : l'interface va droit à l'écran (linuxfb, par DRM), sans curseur, et c'est le processeur qui
# dessine : le pilote du GPU des Pi 0 à 3 (vc4) corrompt la mémoire avec cette appli (voir le README)
PI_QT_ENV = {
    "QT_QPA_PLATFORM": "linuxfb",
    "QT_QPA_FB_DRM": "1",
    "QT_QPA_FB_HIDECURSOR": "1",
    "QT_QUICK_BACKEND": "software",
}
# Éteindre : l'arrêt du système, sans jamais attendre de mot de passe (le droit est donné par tools/pi/installer.sh)
POWER_OFF = ["systemctl", "--no-ask-password", "poweroff"]


def on_raspberry_pi(model_file: Path = PI_MODEL_FILE) -> bool:
    """Vrai sur le Pi, faux sur le Mac."""
    try:
        return model_file.read_text(errors="ignore").startswith("Raspberry Pi")
    except OSError:
        return False


def shutdown() -> str | None:
    """Arrête le système proprement. None s'il accepte ; sinon, pourquoi, en quelques mots."""
    try:
        result = subprocess.run(POWER_OFF, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"Arrêt impossible : {error}", file=sys.stderr)
        return "arrêt impossible"
    if result.returncode != 0:
        print(f"Arrêt refusé ({result.returncode}) : {result.stderr.strip()}", file=sys.stderr)
        return "le système refuse l'arrêt"
    return None
