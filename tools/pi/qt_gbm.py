"""PySide6 sait afficher en plein écran sans bureau (eglfs), mais il lui manque une pièce pour les écrans pilotés
par le noyau (KMS, le cas du Pi) : libQt6EglFsKmsGbmSupport. On la prend dans la distribution officielle de Qt pour
ARM64, dont PySide6 reprend les binaires : même version, même compilation, vérifiée sur une bibliothèque voisine.

Seulement pour des essais au GPU : l'appli dessine par le processeur, le GPU des Pi 0 à 3 corrompant la mémoire (voir le
README). À lancer avec le Python de l'environnement du compteur : .venv/bin/python tools/pi/qt_gbm.py
"""

import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import PySide6

REPO = "https://download.qt.io/online/qtsdkrepository/linux_arm64/desktop"
MISSING = "libQt6EglFsKmsGbmSupport"
NEIGHBOUR = "libQt6EglFSDeviceIntegration"  # fournie par PySide6 : doit être identique à celle de Qt


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    lib = Path(PySide6.__file__).parent / "Qt" / "lib"
    if (lib / f"{MISSING}.so.6").exists():
        print(f"{MISSING} : déjà là")
        return
    version = PySide6.__version__.split("+")[0]  # ex. 6.11.2
    tag = "qt6_" + version.replace(".", "")
    folder = f"{REPO}/{tag}/{tag}"
    package = f"qt.qt6.{version.replace('.', '')}.linux_gcc_arm64"

    # Paquet de Qt pour ARM64, sa compilation et son archive de base
    updates = urllib.request.urlopen(f"{folder}/Updates.xml", timeout=60).read().decode()
    block = next(b for b in re.findall(r"<PackageUpdate>(.*?)</PackageUpdate>", updates, re.S)
                 if f"<Name>{package}</Name>" in b)
    build = re.search(r"<Version>(.*?)</Version>", block).group(1)
    archives = re.search(r"<DownloadableArchives>(.*?)</DownloadableArchives>", block, re.S).group(1)
    archive = next(a.strip() for a in archives.split(",") if a.strip().startswith("qtbase-"))

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "qtbase.7z"
        print(f"Téléchargement de {archive}…")
        urllib.request.urlretrieve(f"{folder}/{package}/{build}{archive}", path)
        subprocess.run(["bsdtar", "-xf", str(path), "-C", tmp, f"lib/{MISSING}.so.*", f"lib/{NEIGHBOUR}.so.*"],
                       check=True)
        if sha256(Path(tmp) / "lib" / f"{NEIGHBOUR}.so.{version}") != sha256(lib / f"{NEIGHBOUR}.so.6"):
            sys.exit(f"Qt {build} n'est pas la compilation de PySide6 {version} : rien n'est copié")
        shutil.copyfile(Path(tmp) / "lib" / f"{MISSING}.so.{version}", lib / f"{MISSING}.so.6")
    print(f"{MISSING} : copiée depuis Qt {build}")


if __name__ == "__main__":
    main()
