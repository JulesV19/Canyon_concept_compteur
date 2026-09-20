from datetime import datetime, timezone

import pytest

from compteur import gps
from compteur.gps import (OUTPUT, QUERY_FIRMWARE, STALE_S, NmeaReader, Receiver, Satellite, command, coordinate,
                          parse)

# Exemples classiques de la norme NMEA 0183, avec leur somme de contrôle
RMC = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
GGA = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"


def sentence(body: str) -> str:
    return command(body).decode().strip()


def test_somme_de_controle():
    # Commande d'Adafruit pour n'avoir que RMC et GGA
    assert command("PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0") == \
        b"$PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*28\r\n"
    assert OUTPUT.startswith(b"$PMTK314,0,1,0,1,5,5,") and OUTPUT.endswith(b"\r\n")
    assert parse(RMC)[0] == "RMC"
    assert parse(RMC.replace("4807", "4808")) is None  # un caractère abîmé
    assert parse("$GPRMC,123519,A") is None
    assert parse("\xff\xff\xff") is None


def test_coordonnees():
    assert coordinate("4807.038", "N") == pytest.approx(48 + 7.038 / 60)
    assert coordinate("01131.000", "W") == pytest.approx(-(11 + 31 / 60))
    assert coordinate("", "N") is None


def test_position_vitesse_altitude():
    reader = NmeaReader(clock=lambda: 10.0)
    assert reader.feed(f"{RMC}\r\n{GGA}\r\n".encode())
    fix = reader.fix
    assert fix.valid
    assert fix.lat == pytest.approx(48.1173) and fix.lon == pytest.approx(11.516667)
    assert fix.speed_mps == pytest.approx(22.4 * 1852 / 3600)
    assert fix.heading_deg == 84.4
    assert fix.altitude_m == 545.4
    assert fix.satellites == 8 and fix.hdop == 0.9
    assert fix.utc is None  # 23/03/94 dans l'exemple de la norme : lu 2094, écarté (voir le test de l'heure)
    assert fix.received == 10.0


def test_sans_position_l_heure_arrive_quand_meme():
    reader = NmeaReader()
    reader.feed((sentence("GNRMC,080102.000,V,,,,,0.00,0.00,160926,,,N") + "\r\n").encode())
    reader.feed((sentence("GNGGA,080102.000,,,,,0,0,,,M,,M,,") + "\r\n").encode())
    assert not reader.fix.valid
    assert reader.fix.lat is None and reader.fix.speed_mps is None and reader.fix.altitude_m is None
    assert reader.fix.utc == datetime(2026, 9, 16, 8, 1, 2, tzinfo=timezone.utc)


def test_lignes_coupees_entre_deux_lectures_et_remplissage():
    reader = NmeaReader()
    data = f"{RMC}\r\n".encode()
    assert reader.feed(data[:30])
    assert not reader.fix.valid
    assert reader.feed(data[30:-1])  # tout sauf le dernier saut de ligne
    assert not reader.feed(b"\n" * 64)  # remplissage : rien de neuf, mais il termine la ligne
    assert reader.fix.valid
    assert reader.lines == [RMC]


def test_satellites_en_vue_toutes_constellations():
    reader = NmeaReader()
    for body in ("GPGSV,3,1,11,01,40,083,46", "GPGSV,3,2,11,02,17,308,41", "GLGSV,2,1,06,65,64,037,33"):
        reader.feed((sentence(body) + "\r\n").encode())
    assert reader.fix.in_view == 17


def feed(reader, *bodies):
    for body in bodies:
        reader.feed((sentence(body) + "\r\n").encode())


def test_ciel_satellite_par_satellite():
    """Une série GSV complète remplace la précédente ; un satellite en vue mais pas capté n'a pas de signal."""
    reader = NmeaReader()
    feed(reader, "GPGSV,2,1,05,01,40,083,46,02,17,308,,12,07,344,39,40,30,150,35",
         "GPGSV,2,2,05,14,22,228,45", "GLGSV,1,1,01,65,64,037,33")
    assert reader.fix.sky == (Satellite("GPS", 1, 40, 83, 46), Satellite("GPS", 2, 17, 308, None),
                              Satellite("GPS", 12, 7, 344, 39), Satellite("SBAS", 40, 30, 150, 35),
                              Satellite("GPS", 14, 22, 228, 45), Satellite("GLONASS", 65, 64, 37, 33))
    feed(reader, "GPGSV,1,1,01,01,41,084,47")
    assert [sat.prn for sat in reader.fix.sky] == [1, 65]
    feed(reader, "GPGSV,2,2,05,14,22,228,45")  # fin d'une série prise en cours de route : ignorée
    assert [sat.prn for sat in reader.fix.sky] == [1, 65]


def test_satellites_utilises_et_precision():
    """Une ligne GSA par constellation dans la même seconde : leurs satellites s'ajoutent ; la seconde suivante
    (après une GGA) les remplace."""
    reader = NmeaReader()
    feed(reader, "GNGGA,123519,4807.038,N,01131.000,E,2,05,0.9,545.4,M,46.9,M,,",
         "GNGSA,A,3,01,12,14,,,,,,,,,,1.6,0.9,1.3", "GNGSA,A,3,65,66,,,,,,,,,,,1.6,0.9,1.3")
    assert reader.fix.used == {1, 12, 14, 65, 66}
    assert (reader.fix.fix_type, reader.fix.pdop, reader.fix.hdop, reader.fix.vdop) == (3, 1.6, 0.9, 1.3)
    assert reader.fix.quality == 2  # corrigée par SBAS
    feed(reader, "GNGGA,123520,4807.038,N,01131.000,E,1,03,2.1,545.4,M,46.9,M,,", "GNGSA,A,2,01,12,14,,,,,,,,,,2.5,2.1,1.0")
    assert reader.fix.used == {1, 12, 14} and reader.fix.fix_type == 2


def test_heure_pas_encore_reglee_ignoree():
    """Tout juste allumé, le GPS donne l'heure de son horloge, partie du 5 janvier 1980 : ce n'est pas l'heure."""
    reader = NmeaReader()
    feed(reader, "GNRMC,235943.000,V,,,,,0.00,0.00,050180,,,N")
    assert reader.fix.utc is None
    feed(reader, "GNRMC,145000.000,V,,,,,0.00,0.00,180926,,,N")  # l'heure d'un satellite, avant la position
    assert reader.fix.utc == datetime(2026, 9, 18, 14, 50, tzinfo=timezone.utc)


def test_version_du_micrologiciel():
    reader = NmeaReader()
    feed(reader, "PMTK705,AXN_5.1.7_3333_19020118,0027,PA1010D,1.0", "PMTK001,314,3")
    assert reader.fix.firmware == "AXN_5.1.7_3333_19020118"
    assert parse(sentence("PMTK001,314,3")) == ("PMTK001", ["314", "3"])


def test_gps_branche_apres_le_demarrage(monkeypatch):
    """Sans GPS au démarrage, le fil le cherche toutes les 10 s ; trouvé, il le lit. L'état dit s'il répond, et quand
    la première position est arrivée."""
    now = [0.0]
    bus = FakeBus(f"{RMC}\r\n{GGA}\r\n")
    found = [None]
    searches = []

    def find():
        searches.append(now[0])
        return found[0]

    receiver = Receiver(clock=lambda: now[0], find=find)
    for t in (0.0, 5.0):
        now[0] = t
        assert not receiver._search()
    found[0] = bus
    now[0] = 10.0
    assert receiver._search()
    assert searches == [0.0, 10.0]  # une recherche toutes les 10 s, pas plus
    assert not receiver.status().present
    monkeypatch.setattr(receiver._stop, "wait", lambda _: receiver._stop.set())  # s'arrête au premier temps mort
    receiver._run()
    status = receiver.status()
    assert status.present and status.fix.valid and status.first_fix_s == 10.0
    now[0] += STALE_S + 1
    assert not receiver.status().present  # plus rien depuis 3 s


def test_message_non_voulu_le_reglage_est_a_renvoyer():
    reader = NmeaReader()
    reader.feed((sentence("GNVTG,0.00,T,,M,0.00,N,0.00,K,N") + "\r\n").encode())
    assert reader.unwanted


class FakeBus:
    """Le GPS vu du bus : il rend ses lignes par morceaux, puis des sauts de ligne."""

    def __init__(self, text: str):
        self.data = bytearray(text.encode())
        self.written = []

    def transfer(self, address, write=b"", read=0):
        assert address == gps.ADDRESS
        if write:
            self.written.append(write)
        chunk = bytes(self.data[:read])
        del self.data[:read]
        return chunk + b"\n" * (read - len(chunk))


def test_le_fil_regle_le_gps_puis_lit_la_position(monkeypatch):
    now = [0.0]
    bus = FakeBus(f"{RMC}\r\n{GGA}\r\n" * 3)
    receiver = Receiver(bus, clock=lambda: now[0])
    monkeypatch.setattr(receiver._stop, "wait", lambda _: receiver._stop.set())  # s'arrête au premier temps mort
    receiver._run()
    assert bus.written == [OUTPUT, QUERY_FIRMWARE]  # la version n'est redemandée que 10 s plus tard
    assert receiver.fix().valid and receiver.fix().altitude_m == 545.4
    assert receiver.take_lines()[:2] == [RMC, GGA]
    now[0] = STALE_S + 1
    assert not receiver.fix().valid  # plus rien depuis 3 s
