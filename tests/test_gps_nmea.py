"""Lecture des lignes NMEA du GPS : somme de contrôle, position, satellites, ciel, lignes coupées."""

from datetime import datetime, timezone

import pytest

from compteur.gps import OUTPUT, NmeaReader, Satellite, command, coordinate, parse
from nmea_samples import GGA, RMC, feed, sentence


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


def test_phrase_completee_par_du_remplissage_au_milieu():
    """Le GPS rend toujours autant d'octets qu'on lui en demande : à court de texte, il complète par des sauts de ligne
    même au milieu d'une phrase. Celle-ci ne doit pas être jetée : sa fin arrive à la lecture suivante."""
    reader = NmeaReader()
    data = f"{GGA}\r\n".encode()
    assert reader.feed(data[:40] + b"\n" * 24)  # lecture pleine : 40 octets utiles, puis du remplissage
    assert reader.lines == [] and reader.fix.altitude_m is None
    assert reader.feed(data[40:] + b"\n" * 40)  # la fin de la phrase, puis du remplissage
    assert reader.lines == [GGA] and reader.fix.altitude_m == 545.4


def test_debut_de_phrase_perdu_le_lecteur_se_raccroche_au_dollar():
    """Des octets perdus sur le bus laissent un morceau de phrase en plan : le « $ » suivant repart à zéro, sinon les
    deux phrases se colleraient et seraient perdues toutes les deux."""
    reader = NmeaReader()
    assert reader.feed(b"038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n" + f"{RMC}\r\n".encode())
    assert reader.lines == [RMC] and reader.fix.valid


def test_satellites_en_vue_toutes_constellations():
    reader = NmeaReader()
    for body in ("GPGSV,3,1,11,01,40,083,46", "GPGSV,3,2,11,02,17,308,41", "GLGSV,2,1,06,65,64,037,33"):
        reader.feed((sentence(body) + "\r\n").encode())
    assert reader.fix.in_view == 17


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


def test_une_constellation_sans_position_n_efface_pas_l_autre():
    """GLONASS peut annoncer « aucune position » (mode 1) juste après une ligne GPS en 3D : c'est la meilleure des
    deux qui vaut pour la seconde, sinon le compteur se croirait sans position alors qu'il en a une."""
    reader = NmeaReader()
    feed(reader, "GNGGA,123519,4807.038,N,01131.000,E,1,05,0.9,545.4,M,46.9,M,,",
         "GPGSA,A,3,01,12,14,,,,,,,,,,1.6,0.9,1.3", "GLGSA,A,1,,,,,,,,,,,,,,,")
    assert reader.fix.fix_type == 3 and reader.fix.used == {1, 12, 14}


def test_serie_gsv_amputee_le_ciel_precedent_est_garde():
    """Une ligne perdue au milieu d'une série : mieux vaut le ciel d'il y a cinq secondes qu'un ciel amputé, qui
    ferait mentir le compte des satellites de la page GPS."""
    reader = NmeaReader()
    feed(reader, "GPGSV,2,1,05,01,40,083,46,02,17,308,,12,07,344,39,40,30,150,35", "GPGSV,2,2,05,14,22,228,45")
    assert [sat.prn for sat in reader.fix.sky] == [1, 2, 12, 40, 14]
    feed(reader, "GPGSV,3,1,09,03,40,083,46,04,17,308,,05,07,344,39,06,30,150,35",  # la ligne 2 se perd...
         "GPGSV,3,3,09,11,22,228,45")                                               # ... la série est incomplète
    assert [sat.prn for sat in reader.fix.sky] == [1, 2, 12, 40, 14]  # le ciel précédent tient


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
