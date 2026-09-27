#!/bin/sh
# Télécharge les modèles 3D des composants dans modeles/brut/ (non suivis par git).
set -e
cd "$(dirname "$0")"
mkdir -p brut && cd brut
UA="Mozilla/5.0"
A=https://raw.githubusercontent.com/adafruit/Adafruit_CAD_Parts/main
curl -sfL -o ecran.zip "https://files.waveshare.com/upload/7/70/2.8inch_DPI_LCD_3D_Drawing.zip"
unzip -o -q -j ecran.zip "*.stp" -d . && mv 28inchdpilcd.stp ecran28dpi.step && rm ecran.zip
curl -sfL -A "$UA" -o pizero2w.step "https://wiki.geekworm.com/images/c/cc/Raspberry-Pi-Zero-2-W.STEP"
curl -sfL -o gps_pa1010d.step "$A/4415%20Mini%20GPS%20PA1010D/4415%20Mini%20GPS%20PA1010D.step"
curl -sfL -o max17048.step "$A/5580%20MAX17048/5580%20MAX17048.step"
curl -sfL -o powerboost1000c.step "$A/2465%20Powerboost%201000C/2465%20Adafruit%20PowerBoost%201000C%20Rev%20B.step"
curl -sfL -o batterie4400.step "$A/354%204400mah%20battery/354%204400mah%20battery.step"
curl -sfL -A "$UA" -o pololu2808.step "https://www.pololu.com/file/0J1308/mini-pushbutton-power-switch-with-reverse-voltage-protection.step"
ls -la
