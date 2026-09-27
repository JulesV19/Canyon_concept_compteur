import pytest

from compteur.battery import (ADDRESS, CRATE, HIBRT, MODE, SOC, STATUS, VCELL, Gauge, Monitor, Reading, Supply,
                              SupplySensors, Trend, decode, outlook)


def test_registres_en_valeurs():
    reading = decode(soc=0x4B80, vcell=0xC4E0, crate=0xFFF6)
    assert reading.percent == pytest.approx(75.5)
    assert reading.voltage == pytest.approx(0xC4E0 * 78.125e-6)  # ≈ 3,94 V
    assert reading.rate_pct_h == pytest.approx(-2.08)
    assert decode(soc=0x6680, vcell=0, crate=0x0010).percent == 100.0  # 102,5 % en fin de charge
    assert decode(soc=0, vcell=0, crate=0x0010).rate_pct_h == pytest.approx(3.328)
    # Relevés sur le Pi : en veille (MODE 0x1000), sans alerte (STATUS 0x01ff : seul le bit « redémarrée »)
    assert decode(0, 0, 0, mode=0x1000, status=0x01FF) == Reading(0, 0, 0, hibernating=True, low_alert=False)
    assert decode(0, 0, 0, mode=0, status=0x1100).low_alert


class FakeBus:
    def __init__(self, registers):
        self.registers = registers
        self.closed = False
        self.written = []

    def transfer(self, address, write=b"", read=0):
        assert address == ADDRESS
        if self.registers is None:
            raise OSError("pas de réponse")
        if read == 0:  # écriture d'un registre
            self.written.append((write[0], int.from_bytes(write[1:], "big")))
            return b""
        assert read == 2
        return self.registers[write[0]]

    def close(self):
        self.closed = True


REGISTERS = {SOC: b"\x32\x00", VCELL: b"\xb6\x00", CRATE: b"\x00\x00", MODE: b"\x10\x00", STATUS: b"\x01\xff"}


def test_lecture_sur_le_bus():
    reading = Gauge(FakeBus(REGISTERS)).read()
    assert reading.percent == 50.0
    assert reading.voltage == pytest.approx(3.64)
    assert reading.hibernating


def test_jauge_reveillee_des_qu_elle_est_trouvee():
    """En veille la jauge ne mesure que toutes les 45 s : on met ses seuils de veille à zéro en la trouvant."""
    bus = FakeBus(REGISTERS)
    Gauge(bus).wake()
    assert bus.written == [(HIBRT, 0)]

    class Sensors:
        def read(self):
            return Supply()

    bus = FakeBus(REGISTERS)
    monitor = Monitor(lambda: bus, Sensors(), clock=lambda: 0.0)
    monitor.poll()
    assert bus.written == [(HIBRT, 0)]  # réveillée une seule fois, à la découverte
    monitor.poll()
    assert bus.written == [(HIBRT, 0)]


def test_jauge_cherchee_trouvee_puis_perdue():
    """Sans batterie, la jauge ne répond pas : on la cherche toutes les 10 s. Perdue (3 lectures ratées), on la
    cherche à nouveau ; la dernière lecture compte encore 10 s."""
    now = [0.0]
    bus = FakeBus(REGISTERS)
    found = [None]
    searches = []

    def find():
        searches.append(now[0])
        return found[0]

    class Sensors:
        def read(self):
            return Supply(undervoltage=False, cpu_temp_c=40.0)

    monitor = Monitor(find, Sensors(), clock=lambda: now[0])
    monitor.poll()
    assert monitor.latest() == (None, Supply(False, 40.0))
    found[0] = bus
    now[0] = 5.0
    monitor.poll()  # pas encore l'heure de chercher
    assert searches == [0.0]
    now[0] = 10.0
    monitor.poll()
    assert searches == [0.0, 10.0]
    assert monitor.latest()[0].percent == 50.0

    bus.registers = None  # batterie débranchée
    for t in (12.0, 14.0, 16.0):
        now[0] = t
        monitor.poll()
    assert monitor.errors == 3 and bus.closed
    assert monitor.latest()[0].percent == 50.0  # lue à 10 s : encore valable
    now[0] = 21.0
    assert monitor.latest()[0] is None
    monitor.poll()  # cherchée à 16 s, en la perdant : pas avant 26 s
    assert searches == [0.0, 10.0]


def test_alimentation_du_pi(tmp_path):
    for name, files in {"hwmon0": {"name": "cpu_thermal\n", "temp1_input": "48312\n"},
                        "hwmon1": {"name": "rpi_volt\n", "in0_lcrit_alarm": "1\n"}}.items():
        (tmp_path / name).mkdir()
        for file, text in files.items():
            (tmp_path / name / file).write_text(text)
    assert SupplySensors(tmp_path).read() == Supply(undervoltage=True, cpu_temp_c=pytest.approx(48.312))
    assert SupplySensors(tmp_path / "absent").read() == Supply()  # hors du Pi


def test_courbe_un_point_toutes_les_30_s_et_sa_pente():
    trend = Trend()
    for s in range(0, 241):
        trend.add(s, 80 - s / 360)  # −10 %/h
    assert [s for s, _ in trend.points] == [0, 30, 60, 90, 120, 150, 180, 210, 240]
    assert trend.slope_pct_h() is None  # moins de 5 min
    for s in range(241, 1801):
        trend.add(s, 80 - s / 360 if s < 900 else 80 - 900 / 360 - (s - 900) / 180)  # puis −20 %/h
    assert trend.slope_pct_h() == pytest.approx(-20)  # les 15 dernières minutes seulement
    assert trend.first == (0, 80)


def test_autonomie_en_decharge():
    trend = Trend()
    for s in range(0, 1801, 30):
        trend.add(s, 60 - s / 360)  # −10 %/h depuis 30 min
    view = outlook(Reading(55.0, 3.8, rate_pct_h=-12.0), trend, 1800, capacity_mah=5000)
    assert view.state == "decharge" and not view.low
    assert view.autonomy_s == pytest.approx(5.5 * 3600)  # d'après la pente : 55 % à 10 %/h
    assert view.full_in_s is None
    assert view.current_ma == pytest.approx(600)  # d'après la jauge : 12 % de 5000 mAh par heure
    assert view.remaining_mah == pytest.approx(2750)
    assert view.change_pct == pytest.approx(-5) and view.since_s == 1800


def test_charge_pleine_faible_absente():
    trend = Trend()
    for s in range(0, 1801, 30):
        trend.add(s, 60 - s / 360)  # la pente descend encore : le chargeur vient d'être branché
    charging = outlook(Reading(50.0, 3.9, rate_pct_h=25.0), trend, 1800)
    assert charging.state == "charge"
    assert charging.full_in_s == pytest.approx(2 * 3600)  # d'après la jauge
    assert charging.autonomy_s is None
    assert outlook(Reading(100.0, 4.2, rate_pct_h=0.2), Trend(), 0).state == "pleine"
    assert outlook(Reading(100.0, 4.2, rate_pct_h=-5.0), Trend(), 0).state == "decharge"
    assert outlook(Reading(12.0, 3.6, rate_pct_h=-5.0), Trend(), 0).low
    assert outlook(Reading(30.0, 3.7, rate_pct_h=-5.0, low_alert=True), Trend(), 0).low
    assert outlook(None, Trend(), 0).state == "absente"
    stable = outlook(Reading(70.0, 3.9, rate_pct_h=0.0), Trend(), 0)
    assert stable.state == "decharge" and stable.autonomy_s is None
