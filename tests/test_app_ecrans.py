"""L'appli entière, hors écran : touches qui quittent, Éteindre, écrans Batterie et GPS, vrai GPS."""

from pilote import launch


def test_echap_et_q_ne_quittent_qu_a_l_accueil(tmp_path):
    process, state = launch("""
        c = open_app()
        def flow():
            activate(c)
            state = {}
            c.session.start(0)
            c.window.setProperty("screen", "ride")
            for key in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
                QTest.keyClick(c.window, key)
            wait(100)
            state["ride"] = [c.quit_requested == [], c.window.property("screen")]
            c.model.startPause()
            QTest.keyClick(c.window, Qt.Key.Key_E)  # Terminer : le résumé
            for key in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
                QTest.keyClick(c.window, key)
            wait(100)
            state["summary"] = [c.quit_requested == [], c.window.property("screen")]
            QTest.keyClick(c.window, Qt.Key.Key_Backspace)  # Supprimer : retour à l'accueil
            QTest.keyClick(c.window, Qt.Key.Key_Q)
            wait(100)
            state["home"] = [c.quit_requested == [True], c.window.property("screen")]
            report(state)
        run(c, flow)
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert state == {"ride": [True, "ride"], "summary": [True, "summary"], "home": [True, "home"]}


def test_eteindre_refuse_puis_accepte(tmp_path):
    process, state = launch("""
        c = open_app()
        refusals, quits = [], []
        c.session.powerOffFailed.connect(refusals.append)
        def flow():
            pi.on_raspberry_pi = lambda *args: True  # comme sur le Pi
            c.app.quit = lambda: quits.append(True)
            c.window.setProperty("screen", "menu")
            pi.POWER_OFF = [sys.executable, "-c", "import sys; sys.exit(1)"]  # polkit refuse
            c.session.powerOff()
            state = {"refusals": list(refusals), "quits": list(quits)}
            pi.POWER_OFF = [sys.executable, "-c", "pass"]  # le système accepte : il s'arrête, l'appli se ferme
            c.session.powerOff()
            state["quitsAfter"] = list(quits)
            del c.app.quit
            report(state)
        run(c, flow)
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert state == {"refusals": ["le système refuse l'arrêt"], "quits": [], "quitsAfter": [True]}
    assert "Arrêt refusé (1)" in process.stderr


def test_batterie_depuis_les_reglages(tmp_path):
    """Réglages, ↓ jusqu'à Batterie puis Entrée : l'écran Batterie, avec la batterie simulée ; Échap : les réglages.
    La barre d'état suit la même batterie, et montre la charge (chargeur branché : temps avant d'être pleine)."""
    process, state = launch("""
        c = open_app()
        def flow():
            activate(c)
            for _ in range(20 * 60):  # 20 min de mise en route
                c.step()
            c.refresh()
            c.window.setProperty("screen", "settings")
            for _ in range(3):
                QTest.keyClick(c.window, Qt.Key.Key_Down)
            QTest.keyClick(c.window, Qt.Key.Key_Return)
            wait(100)
            values = c.battery.values
            state = {"screen": c.window.property("screen"), "source": values["source"], "state": values["state"],
                     "percent": round(values["percent"], 1), "barPct": c.model.values["batteryPct"],
                     "autonomyH": round(values["autonomyS"] / 3600, 2), "curve": len(c.battery.curve)}
            state["barCharging"] = c.model.values["batteryCharging"]
            from compteur.battery import Reading, Supply
            c.battery.update(1300, Reading(50.0, 3.9, rate_pct_h=20.0), Supply())  # chargeur branché
            c.refresh()
            values = c.battery.values
            state["charging"] = [values["state"], round(values["fullInS"] / 3600, 2), c.model.values["batteryCharging"],
                                 c.model.values["batteryPct"]]
            QTest.keyClick(c.window, Qt.Key.Key_Escape)
            wait(100)
            state["back"] = c.window.property("screen")
            report(state)
        run(c, flow)
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert state == {"screen": "battery", "source": "Simulation", "state": "decharge", "percent": 94.4, "barPct": 94,
                     "autonomyH": 5.67, "curve": 41, "barCharging": False,
                     "charging": ["charge", 2.5, True, 50], "back": "settings"}


def test_gps_depuis_les_reglages(tmp_path):
    """Réglages, ↓ jusqu'à GPS puis Entrée : l'écran GPS, avec le GPS simulé, qui a trouvé sa position ; ↓ fait
    défiler la page ; Échap : les réglages."""
    process, state = launch("""
        c = open_app()
        def flow():
            activate(c)
            for _ in range(30):
                c.step()
            c.refresh()
            c.window.setProperty("screen", "settings")
            for _ in range(4):
                QTest.keyClick(c.window, Qt.Key.Key_Down)
            QTest.keyClick(c.window, Qt.Key.Key_Return)
            wait(400)
            values = c.gps_model.values
            page = c.window.findChild(QObject, "gpsPage")
            QTest.keyClick(c.window, Qt.Key.Key_Down)
            wait(100)
            state = {"screen": c.window.property("screen"), "source": values["source"], "state": values["state"],
                     "used": values["used"], "inView": values["inView"],
                     "constellations": [k["name"] for k in values["constellations"]],
                     "shown": len(page.property("satellites")), "firstFixS": values["firstFixS"],
                     "scrolled": page.findChild(QObject, "gpsScroll").property("contentY") > 0}
            QTest.keyClick(c.window, Qt.Key.Key_Escape)
            wait(100)
            state["back"] = c.window.property("screen")
            report(state)
        run(c, flow)
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert state == {"screen": "gps", "source": "Simulation", "state": "3d", "used": 10, "inView": 15,
                     "constellations": ["GPS", "GLONASS", "Galileo", "SBAS"], "shown": 15, "firstFixS": 4.0,
                     "scrolled": True, "back": "settings"}


def test_avec_le_vrai_gps_la_sortie_ne_suit_plus_le_cycliste_simule(tmp_path):
    """Sur le Pi, toutes les mesures viennent du GPS branché — y compris une fois la sortie lancée. Ici il ne répond
    pas (pas de bus) : rien n'est inventé, et l'accueil ne dit pas « Prêt »."""
    rides = tmp_path / "sorties"
    rides.mkdir()
    process, result = launch("""
        pi.on_raspberry_pi = lambda *args: True  # l'appli se croit sur le Pi : elle cherche le vrai GPS
        c = open_app()
        def flow():
            at_home = type(c.rider).__name__
            c.session.start(0)  # départ sur le premier parcours
            for _ in range(5):
                c.tick()
            report({"atHome": at_home, "riding": type(c.rider).__name__, "ride": ride_state(c),
                    "speedKmh": c.model.values.get("speedKmh"), "heartRate": c.model.values.get("heartRate"),
                    "gpsFix": c.model.values.get("gpsFix"), "gpsBars": c.model.values.get("gpsBars"),
                    "hrConnected": c.model.values.get("hrConnected")})
        run(c, flow)
    """, rides)
    assert process.returncode == 0
    assert result["atHome"] == "GpsRider" and result["riding"] == "GpsRider"  # le départ ne remet pas la simulation
    assert result["speedKmh"] is None and result["heartRate"] is None
    assert result["ride"]["distance"] == 0 and result["ride"]["state"] == "running"
    assert result["gpsFix"] is False and result["gpsBars"] == 0 and result["hrConnected"] is False


def test_fleches_haut_et_bas_dans_les_reglages(tmp_path):
    """↑ remonte d'une ligne (de la première, on passe à la dernière) ; ↓ descend."""
    process, rows = launch("""
        c = open_app()
        def flow():
            activate(c)
            c.window.setProperty("screen", "settings")
            wait(400)
            page = [p for p in c.window.findChildren(QObject) if p.metaObject().className().startswith("SettingsPage")][0]
            rows = []
            for key in (Qt.Key_Up, Qt.Key_Up, Qt.Key_Down, Qt.Key_Down, Qt.Key_Down):
                QTest.keyClick(c.window, key)
                wait(60)
                rows.append(page.property("focusRow"))
            report(rows)
        run(c, flow)
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert rows == [4, 3, 4, 0, 1]
