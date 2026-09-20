#!/usr/bin/env python3
"""Essai des capteurs du bus I2C, sur le Pi : jauge de batterie et GPS. Liste les modules trouvés, puis affiche chaque
seconde ce qu'ils mesurent. Ctrl+C pour arrêter.

    ssh -4 julesvide@compteur.local 'cd compteur && .venv/bin/python tools/pi/essai_capteurs.py'
    … essai_capteurs.py --nmea   # avec les lignes brutes du GPS

Le bus est posé par tools/pi/bus_capteurs.sh. Le GPS trouve sa position en une demi-minute environ, dehors ou collé à
une fenêtre ; rarement à l'intérieur.
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from compteur import battery, gps, i2c  # noqa: E402

KNOWN = {0x10: "GPS PA1010D", 0x14: "tactile GT911", 0x20: "boutons MCP23017", 0x36: "jauge MAX17048",
         0x5D: "tactile GT911", 0x68: "horloge DS3231", 0x77: "baromètre BMP390"}


def scan() -> None:
    numbers = i2c.bus_numbers()
    if not numbers:
        print("Aucun bus I2C : lancer tools/pi/bus_capteurs.sh, puis sudo reboot")
    for number in numbers:
        name = Path(f"/sys/class/i2c-dev/i2c-{number}/name")
        label = name.read_text().strip() if name.exists() else "?"
        try:
            bus = i2c.Bus(number)
        except OSError as error:
            print(f"i2c-{number} ({label}) : illisible ({error.strerror})")
            continue
        found = [f"0x{address:02x} {module}" for address, module in KNOWN.items() if bus.answers(address)]
        bus.close()
        print(f"i2c-{number} ({label}) : {', '.join(found) or 'aucun module connu'}")


def gps_text(fix: gps.Fix) -> str:
    if not fix.valid:
        return f"GPS cherche : {fix.in_view} satellites en vue, {fix.satellites} utilisés"
    altitude = f"{fix.altitude_m:.0f} m" if fix.altitude_m is not None else "altitude ?"
    heading = f"cap {fix.heading_deg:.0f}°" if fix.heading_deg is not None else "cap ?"
    speed = f"{fix.speed_mps * 3.6:.1f} km/h" if fix.speed_mps is not None else "vitesse ?"
    return (f"GPS {fix.lat:.6f}, {fix.lon:.6f} · {altitude} · {speed} · {heading} · "
            f"{fix.satellites} sat. (HDOP {fix.hdop})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nmea", action="store_true", help="affiche aussi les lignes brutes du GPS")
    args = parser.parse_args()

    scan()
    gauge_bus = i2c.find(battery.ADDRESS)
    gauge = battery.Gauge(gauge_bus) if gauge_bus else None
    gps_bus = i2c.find(gps.ADDRESS)
    receiver = gps.Receiver(gps_bus).start() if gps_bus else None
    if gauge is None and receiver is None:
        print("Ni jauge ni GPS : vérifier les 4 fils (3,3 V, masse, SDA sur GPIO 10, SCL sur GPIO 11)")
        return

    started = time.monotonic()
    found_after = None
    try:
        while True:
            elapsed = time.monotonic() - started
            parts = [f"{elapsed:4.0f} s"]
            if gauge is not None:
                try:
                    reading = gauge.read()
                    parts.append(f"batterie {reading.percent:.1f} % · {reading.voltage:.3f} V · "
                                 f"{reading.rate_pct_h:+.1f} %/h")
                except OSError as error:
                    parts.append(f"jauge muette ({error.strerror})")
            if receiver is not None:
                if args.nmea:
                    for line in receiver.take_lines():
                        print(f"      {line}")
                fix = receiver.fix()
                parts.append(gps_text(fix))
                if fix.valid and found_after is None:
                    found_after = elapsed
                    print(f"      Position trouvée en {found_after:.0f} s")
                if fix.utc is not None:
                    offset = (datetime.now(timezone.utc) - fix.utc).total_seconds()
                    parts.append(f"{fix.utc:%H:%M:%S} UTC (horloge du Pi {offset:+.0f} s)")
                if receiver.errors:
                    parts.append(f"{receiver.errors} erreurs de bus")
            print(" | ".join(parts), flush=True)
            time.sleep(1 - (time.monotonic() - started) % 1)
    except KeyboardInterrupt:
        pass
    finally:
        if receiver is not None:
            receiver.stop()


if __name__ == "__main__":
    main()
