#!/bin/bash
# Sur le Pi (Raspberry Pi OS Lite 64 bits), dans ~/compteur copié par tools/pi/envoyer.sh :
# bibliothèques graphiques du système et environnement Python avec PySide6. L'appli s'affiche sans bureau, dessinée
# par le processeur (réglages dans compteur/app.py) : le GPU des Pi 0 à 3 corrompt la mémoire (voir le README).
set -euo pipefail
cd "$(dirname "$0")/../.."

sudo apt-get update
# Noyau et firmware à jour (servent au prochain démarrage). Le pilote du GPU (vc4) laisse encore le GPU écrire hors
# de sa mémoire, même avec le noyau le plus récent essayé : l'appli ne s'en sert pas.
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y linux-image-rpi-v8 raspi-firmware
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libegl1 libgl1 libgbm1 libfontconfig1 libfreetype6 libxkbcommon0 libarchive-tools

# Réserve mémoire du GPU à 128 Mo : avec les 256 Mo par défaut, le Pi se figeait au changement de page quand le GPU
# dessinait (la mémoire ordinaire remplit la réserve, et le noyau s'enlise à la libérer)
config=/boot/firmware/config.txt
if grep -q "^dtoverlay=vc4-kms-v3d$" "$config"; then
    sudo sed -i "s/^dtoverlay=vc4-kms-v3d$/dtoverlay=vc4-kms-v3d,cma-128/" "$config"
    echo "Réserve du GPU réglée à 128 Mo : à prendre en compte au prochain démarrage (sudo reboot)"
fi

# « Éteindre » dans l'appli : son utilisateur peut arrêter le système sans mot de passe. Sans cette règle, polkit en
# demande un, et l'appli ne peut pas éteindre le Pi.
user=$(id -un)
sudo tee /etc/polkit-1/rules.d/50-compteur.rules > /dev/null <<EOF
// Posé par tools/pi/installer.sh : ${user} peut éteindre le compteur depuis l'appli, sans mot de passe
polkit.addRule(function (action, subject) {
    if ((action.id === "org.freedesktop.login1.power-off" ||
         action.id === "org.freedesktop.login1.power-off-multiple-sessions") && subject.user === "${user}") {
        return polkit.Result.YES;
    }
});
EOF

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --disable-pip-version-check -r requirements.txt
echo "Prêt : .venv/bin/python -m compteur"
