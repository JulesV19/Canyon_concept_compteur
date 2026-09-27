import QtQuick
import "Format.js" as Format

// Accueil : le logo (où l'intro se pose), les parcours à balayer, l'état des capteurs, le menu et le départ.
Item {
    id: home
    required property var session
    required property var values
    property real reveal: 1           // 0 → 1 : entrée des éléments, orchestrée par l'intro
    property bool logoShown: true     // pendant l'intro, c'est le logo de l'intro qui est ici
    property alias logo: logo
    property alias currentIndex: carousel.currentIndex
    property bool armed: false        // départ demandé, en attente du signal GPS
    signal startRequested(int index)  // parcours choisi, ou −1 pour une sortie libre
    signal menuRequested

    readonly property bool gpsReady: values.gpsFix === true
    readonly property bool hrReady: values.hrConnected === true
    readonly property int routeCount: session.routes.length
    readonly property int selectedRoute: carousel.currentIndex < routeCount ? carousel.currentIndex : -1

    // Démarrer : tout de suite si le GPS capte ; sinon au premier signal, ou au deuxième appui
    function requestStart() {
        if (gpsReady || armed) {
            armed = false
            startRequested(selectedRoute)
        } else {
            armed = true
        }
    }
    // Au premier signal : départ juste après la mise à jour des valeurs (le départ les remet à jour)
    onGpsReadyChanged: if (gpsReady && armed) Qt.callLater(requestStart)

    function next() {
        carousel.incrementCurrentIndex()
    }
    function previous() {
        carousel.decrementCurrentIndex()
    }
    // Carte affichée, dans les coordonnées de la fenêtre (point de départ de la transition)
    function cardRect() {
        const card = carousel.currentItem
        if (!card)
            return Qt.rect(0, 0, width, height)
        const p = card.mapToItem(null, 0, 0)
        return Qt.rect(p.x, p.y, card.width, card.height)
    }
    // Retour d'une sortie : l'accueil se redessine
    function replay() {
        armed = false
        replayAnimation.restart()
    }

    property real replayed: 1
    readonly property real shown: Math.min(reveal, replayed)
    NumberAnimation {
        id: replayAnimation
        target: home
        property: "replayed"
        from: 0
        to: 1
        duration: 1000
    }

    function span(a, b) {
        return Math.max(0, Math.min(1, (shown - a) / (b - a)))
    }
    // Entrée d'un élément entre a et b (fractions de `shown`), freinée à l'arrivée
    function enter(a, b) {
        return 1 - Math.pow(1 - span(a, b), 3)
    }

    Logo {
        id: logo
        anchors.horizontalCenter: parent.horizontalCenter
        y: 18
        width: 272
        opacity: home.logoShown ? 1 : 0
    }

    Text {
        anchors { horizontalCenter: parent.horizontalCenter; top: logo.bottom; topMargin: 10 }
        text: "Ultimate CF SL 7"
        color: Theme.ash
        opacity: home.enter(0, 0.3)
        font { family: Theme.sans; pixelSize: 18; weight: Font.DemiBold; italic: true; letterSpacing: 1.5 }
    }

    // Parcours à balayer, puis la sortie libre. Les éléments arrivent en glissant dans l'oblique du logo.
    ListView {
        id: carousel
        readonly property real entry: home.enter(0.05, 0.45)
        y: 96
        width: parent.width
        height: 284
        opacity: entry
        transform: Translate { x: (1 - carousel.entry) * 18 * Theme.lean; y: (1 - carousel.entry) * 18 }

        orientation: ListView.Horizontal
        spacing: 12
        snapMode: ListView.SnapOneItem
        highlightRangeMode: ListView.StrictlyEnforceRange
        preferredHighlightBegin: 20
        preferredHighlightEnd: width - 20
        highlightMoveDuration: 350
        boundsBehavior: Flickable.StopAtBounds
        model: home.session.routes.concat([{ free: true }])
        onCurrentIndexChanged: home.armed = false

        delegate: Item {
            id: slot
            required property var modelData
            required property int index
            readonly property bool current: ListView.isCurrentItem
            // La carte qui arrive se redessine : le mouvement répond au geste
            property real drawn: 1
            readonly property real draw: Math.min(drawn, home.span(0.15, 1))
            onCurrentChanged: if (current && home.shown >= 1) redraw.restart()
            NumberAnimation {
                id: redraw
                target: slot
                property: "drawn"
                from: 0
                to: 1
                duration: 700
            }

            width: carousel.width - 40
            height: carousel.height

            Loader {
                anchors.fill: parent
                active: !slot.modelData.free
                sourceComponent: RouteCard {
                    name: slot.modelData.name
                    distanceKm: slot.modelData.distanceKm
                    ascentM: slot.modelData.ascentM
                    outline: slot.modelData.outline
                    profile: slot.modelData.profile
                    draw: slot.draw
                }
            }
            Loader {
                anchors.fill: parent
                active: slot.modelData.free === true
                sourceComponent: FreeRideCard { draw: slot.draw }
            }
        }
    }

    // Où l'on est dans les cartes
    Dashes {
        anchors.horizontalCenter: parent.horizontalCenter
        y: carousel.y + carousel.height + 12
        count: carousel.count
        currentIndex: carousel.currentIndex
        opacity: home.enter(0.3, 0.7)
    }

    Item {
        id: sensors
        readonly property real entry: home.enter(0.4, 0.8)
        x: 16
        y: 420
        width: parent.width - 32
        height: 68
        opacity: entry
        transform: Translate { x: (1 - sensors.entry) * 14 * Theme.lean; y: (1 - sensors.entry) * 14 }

        HomeSensor {
            x: 8
            width: parent.width / 2 - 8
            height: parent.height
            label: "GPS"
            ready: home.gpsReady
            value: home.gpsReady ? "Prêt" : "Recherche…"
            beat: home.values.tick ?? 0
        }

        // Filet penché comme le logo
        SlantRule {
            x: parent.width / 2
            height: parent.height
        }

        HomeSensor {
            x: parent.width / 2 + 28
            width: parent.width / 2 - 28
            height: parent.height
            label: "Cardio"
            ready: home.hrReady
            value: home.hrReady ? Format.number(home.values.heartRate) : "Non connectée"
            unit: home.hrReady ? "bpm" : ""
            numeric: home.hrReady
            beat: home.values.tick ?? 0
        }
    }

    MenuButton {
        id: menuButton
        entry: home.enter(0.6, 1)
        x: 16
        y: parent.height - height - 18
        onTapped: home.menuRequested()
    }

    StartButton {
        entry: home.enter(0.6, 1)
        x: menuButton.x + menuButton.width + 10
        width: parent.width - x - 16
        y: parent.height - height - 18
        armed: home.armed
        onTapped: home.requestStart()
    }
}
