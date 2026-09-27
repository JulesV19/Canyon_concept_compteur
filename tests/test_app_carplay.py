"""L'appli entière, hors écran : la page CarPlay, musique, appel et message."""

from pilote import launch


def test_carplay_musique_depuis_le_menu(tmp_path):
    """Menu, ↓ ↓ jusqu'à CarPlay puis Entrée : l'accueil de CarPlay, avec l'iPhone simulé. ⏯ du widget met en pause
    (puis relance) ; glisser vers les applis, toucher Musique, puis ⏯ : le morceau se met en pause (l'iPhone simulé a reçu la commande) ; ‹ ramène à l'accueil, Compteur au menu."""
    process, state = launch("""
        from PySide6.QtCore import QPointF

        c = open_app()
        def find(item, name):
            # Par les enfants visuels : ceux d'un Repeater n'ont pas de parent QObject
            if item.objectName() == name and item.isVisible():
                return item
            return next((found for child in item.childItems() if (found := find(child, name))), None)

        def tap(page, name):
            item = find(page, name)
            point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
            QTest.mouseClick(c.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
            wait(100)

        def flow():
            activate(c)
            c.window.setProperty("screen", "menu")
            for _ in range(2):
                QTest.keyClick(c.window, Qt.Key.Key_Down)
            QTest.keyClick(c.window, Qt.Key.Key_Return)
            wait(400)
            page = c.window.findChild(QObject, "menuCarPlay")
            state = {"screen": c.window.property("screen"), "playing": c.phone.values["music"]["playing"]}
            # ⏯ du widget, sur l'accueil : pause, puis lecture
            tap(page, "carPlayWidget-toggle")
            c.refresh()
            state["widget"] = c.phone.values["music"]["playing"]
            tap(page, "carPlayWidget-toggle")
            c.refresh()
            state["again"] = c.phone.values["music"]["playing"]
            # Les applis sont sur la deuxième page de l'accueil
            QTest.mousePress(c.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(400, 500))
            for step in range(1, 13):
                QTest.mouseMove(c.window, QPoint(400 - 25 * step, 500))
                wait(16)
            QTest.mouseRelease(c.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(100, 500))
            wait(600)
            state["pages"] = find(page, "carPlayHomePages").property("currentIndex")
            tap(page, "carPlayIcon-music")
            wait(700)  # l'écran arrive par la droite
            state["app"] = page.property("app")
            tap(page, "carPlay-toggle")
            c.refresh()
            state["paused"] = not c.phone.values["music"]["playing"]
            tap(page, "carPlayBack")
            wait_for(lambda: page.property("app") == "")  # l'appli se ferme en glissant à droite
            state["back"] = page.property("app")
            tap(page, "carPlayIcon-compteur")
            wait(400)
            state["exit"] = c.window.property("screen")
            report(state)
        run(c, flow)
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert state == {"screen": "carplay", "playing": True, "widget": False, "again": True, "pages": 1, "app": "music", "paused": True, "back": "",
                     "exit": "menu"}


def test_carplay_appel_refuse_et_message_ouvert(tmp_path):
    """Sur la page CarPlay du menu, l'iPhone simulé sonne : le bandeau d'appel, Refuser, il part. Puis un message :
    son bandeau ; le toucher ouvre la conversation, et la pastille de Messages s'efface."""
    process, state = launch("""
        from PySide6.QtCore import QPointF

        c = open_app()
        def tap(item):
            point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
            QTest.mouseClick(c.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
            wait(100)

        def find(item, name):
            if item.objectName() == name and item.isVisible():
                return item
            return next((found for child in item.childItems() if (found := find(child, name))), None)

        def flow():
            activate(c)
            c.window.setProperty("screen", "carplay")
            wait(400)
            call = c.window.findChild(QObject, "callBanner")
            message = c.window.findChild(QObject, "messageBanner")
            page = c.window.findChild(QObject, "menuCarPlay")
            c.phone_sim.ring("Léa")
            c.refresh()
            wait(100)
            state = {"ringing": call.isVisible()}
            tap(find(call, "carPlayDecline"))
            c.refresh()
            wait(100)
            state["declined"] = not call.isVisible()
            c.phone_sim.message("messages", "Léa", "J'arrive")
            c.refresh()
            wait(100)
            state["banner"] = message.isVisible()
            state["badge"] = c.phone.values["unread"]["messages"]
            tap(message)
            c.refresh()
            state["open"] = [page.property("app"), page.property("conversation")]
            state["read"] = c.phone.values["unread"]["messages"]
            state["hidden"] = not message.isVisible()
            report(state)
        run(c, flow)
    """, tmp_path)
    assert process.returncode == 0, process.stderr
    assert state == {"ringing": True, "declined": True, "banner": True, "badge": 3, "open": ["messages", "Léa"],
                     "read": 0, "hidden": True}
