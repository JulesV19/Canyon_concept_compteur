"""Hors de l'écran, la carte ne fait rien : ni son image, ni sa trace (voir MapView). En revenant, elle doit montrer la
carte du moment, pas celle d'avant. Chaque scénario compare l'écran à une image de la carte refaite pour l'occasion.

Réglée comme sur le Pi : dessin par le processeur, à la densité 1 (l'image de la carte ne sert que là), et la carte
glisse d'une mesure à l'autre."""

from pilote import launch

SCENARIOS = """
    c = open_app(software_rendering=False)
    cache = c.window.findChild(QObject, "cacheImage")
    view = cache.parentItem().parentItem()  # la carte (MapView)

    def ride(seconds):
        for _ in range(seconds):
            c.tick()
            wait(5)

    def settle():
        # Sortie en pause (le halo ne respire plus) et glissement fini : l'écran ne bouge plus
        if c.model.ride.state.value == "running":
            c.model.startPause()
        wait(1500)

    def resume():
        if c.model.ride.state.value == "paused":
            c.model.startPause()

    def differing(before, after):
        if before == after:
            return 0
        a, b = bytes(before.constBits()), bytes(after.constBits())
        return sum(a[i:i + 4] != b[i:i + 4] for i in range(0, len(a), 4))

    def tiles_waiting():
        # Tuiles de la carte pas encore affichées (en chargement, ou en train d'apparaître en fondu), et en tout
        def descendants(item):  # les tuiles viennent d'un Repeater : on les trouve par l'arbre des éléments
            for child in item.childItems():
                yield child
                yield from descendants(child)
        tiles = [item for item in descendants(view) if item.property("source") is not None
                 and item.property("source").toString().startswith("image://tiles/")]
        return sum(tile.property("progress") < 1 or tile.property("opacity") < 1 for tile in tiles), len(tiles)

    def stale():
        # Pixels de l'écran qui changent quand on refait l'image de la carte : 0 si elle était à jour
        before = c.window.grabWindow()
        QMetaObject.invokeMethod(cache, "scheduleUpdate")
        wait(200)
        return differing(before, c.window.grabWindow())

    def new_ride(index):
        if c.model.ride.state.value != "idle":
            if c.model.ride.state.value == "running":
                c.model.startPause()
            c.session.finish()
            c.session.discard()
        c.session.start(index)
        c.window.setProperty("screen", "ride")

    def flow():
        found = {}
        new_ride(0)
        c.window.setProperty("page", PAGES["carte"])
        ride(60)
        settle()
        found["à l'écran"] = stale()

        resume()
        c.window.setProperty("page", PAGES["principale"])
        ride(180)  # trois minutes ailleurs : la carte ne bouge pas pendant ce temps
        c.window.setProperty("page", PAGES["carte"])
        settle()
        found["retour sur la carte"] = stale()

        resume()
        c.window.setProperty("page", PAGES["principale"])
        ride(120)
        settle()
        QTest.mousePress(c.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(400, 300))
        for step in range(1, 16):  # le doigt tire la carte vers la gauche, sans la lâcher
            QTest.mouseMove(c.window, QPoint(400 - 10 * step, 300))
            wait(20)
        wait(300)
        found["pendant le balayage"] = stale()
        found["carte visible pendant le balayage"] = cache.isVisible() and c.window.property("page") == 0
        QTest.mouseRelease(c.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(250, 300))
        wait(500)

        c.window.setProperty("page", PAGES["carte"])
        view.setProperty("zoom", 14)
        settle()
        found["zoom"] = stale()
        view.setProperty("headingUp", False)
        settle()
        found["nord en haut"] = stale()
        view.setProperty("headingUp", True)
        view.setProperty("zoom", 16)

        view.setProperty("zoom", 13)  # nouvelles tuiles demandées...
        c.window.setProperty("page", PAGES["principale"])  # ... qui arrivent hors de l'écran
        wait(2500)
        c.window.setProperty("page", PAGES["carte"])
        settle()
        found["tuiles arrivées hors de l'écran"] = stale()
        view.setProperty("zoom", 16)

        resume()
        c.window.setProperty("page", PAGES["principale"])
        ride(300)  # 5 min ailleurs : 2 km plus loin, d'autres tuiles
        settle()
        c.window.setProperty("page", PAGES["carte"])
        waiting, total = tiles_waiting()  # à l'instant du retour, avant tout chargement
        found["tuiles pas prêtes au retour"] = waiting
        found["tuiles au retour, en tout"] = total

        new_ride(-1)  # sortie libre (pas d'image), puis de nouveau un parcours
        c.window.setProperty("page", PAGES["carte"])
        ride(60)
        new_ride(2)
        c.window.setProperty("page", PAGES["carte"])
        ride(30)
        settle()
        found["sortie libre puis parcours"] = stale()
        report(found)
    run(c, flow)
"""


def test_image_de_la_carte_toujours_a_jour(tmp_path):
    process, found = launch(SCENARIOS, tmp_path, QT_QUICK_BACKEND="software")
    assert process.returncode == 0, process.stderr
    assert found.pop("carte visible pendant le balayage") is True
    assert found.pop("tuiles au retour, en tout") > 0
    assert found == dict.fromkeys(found, 0), found
    assert "QML" not in process.stderr and "Warning" not in process.stderr, process.stderr
