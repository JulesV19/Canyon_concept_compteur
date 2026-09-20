#!/bin/bash
# Sur le Pi : le bus I2C des capteurs (jauge, GPS…), sur les GPIO 10 (SDA, broche 19) et 11 (SCL, broche 23). Avec
# l'écran Waveshare, c'est le bus de son tactile, créé par son overlay ; en attendant l'écran, ce script pose le même
# bus en logiciel (i2c-gpio). Jamais i2c_arm : ses GPIO 2 et 3 portent l'image de l'écran. À prendre en compte au
# prochain démarrage (sudo reboot).
set -euo pipefail

config=/boot/firmware/config.txt
line="dtoverlay=i2c-gpio,bus=3,i2c_gpio_sda=10,i2c_gpio_scl=11"
if grep -q "^dtoverlay=.*touch-28dpi" "$config"; then
    # Deux bus sur les mêmes broches se gêneraient : celui du tactile suffit
    sudo sed -i "/^# Bus des capteurs, en attendant l'écran/d; \|^${line}\$|d" "$config"
    echo "Écran présent : les capteurs passent par le bus de son tactile"
elif ! grep -qx "$line" "$config"; then
    printf "\n# Bus des capteurs, en attendant l'écran (tools/pi/bus_capteurs.sh)\n[all]\n%s\n" "$line" \
        | sudo tee -a "$config" > /dev/null
    echo "Bus des capteurs ajouté : /dev/i2c-3 au prochain démarrage (sudo reboot)"
fi

# /dev/i2c-N, pour lire le bus depuis l'appli (groupe i2c)
echo i2c-dev | sudo tee /etc/modules-load.d/i2c-dev.conf > /dev/null
sudo usermod -aG i2c "$(id -un)"
