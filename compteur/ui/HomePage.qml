import QtQuick
import QtQuick.Shapes
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
        font { family: Theme.sans; pixelSize: 15; weight: Font.DemiBold; italic: true; letterSpacing: 1.5 }
    }

    // Parcours à balayer, puis la sortie libre. Les éléments arrivent en glissant dans l'oblique du logo.
    ListView {
        id: carousel
        readonly property real entry: home.enter(0.05, 0.45)
        y: 102
        width: parent.width
        height: 290
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
        y: 424
        width: parent.width - 32
        height: 58
        opacity: entry
        transform: Translate { x: (1 - sensors.entry) * 14 * Theme.lean; y: (1 - sensors.entry) * 14 }

        Sensor {
            x: 8
            width: parent.width / 2 - 8
            height: parent.height
            label: "GPS"
            ready: home.gpsReady
            value: home.gpsReady ? "Prêt" : "Recherche…"
            beat: home.values.tick ?? 0
        }

        // Filet penché comme le logo
        Shape {
            x: parent.width / 2
            height: parent.height
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Theme.hairline
                strokeWidth: 1
                fillColor: "transparent"
                startX: -Theme.lean * sensors.height / 2; startY: 0
                PathLine { x: Theme.lean * sensors.height / 2; y: sensors.height }
            }
        }

        Sensor {
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

    // Menu (Mes sorties, Réglages, Éteindre) : trois traits taillés et étagés dans l'oblique du logo,
    // qui se resserrent sous le doigt
    Panel {
        id: menuButton
        readonly property real entry: home.enter(0.6, 1)
        x: 16
        width: 68
        height: 68
        y: parent.height - height - 18
        color: menuTap.pressed ? Theme.ash : Theme.carbonRaised
        woven: false
        opacity: entry
        transform: Translate { x: (1 - menuButton.entry) * 14 * Theme.lean; y: (1 - menuButton.entry) * 14 }

        Item {
            id: glyph
            anchors.centerIn: parent
            width: 34
            height: 26
            property real spread: menuTap.pressed ? 6.5 : 9  // écart entre deux traits
            Behavior on spread { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

            Repeater {
                model: 3
                delegate: Shape {
                    id: bar
                    required property int index
                    readonly property real rise: (1 - index) * glyph.spread  // hauteur au-dessus du trait du milieu
                    width: 22
                    height: 4
                    x: (glyph.width - width) / 2 - rise * Theme.lean
                    y: (glyph.height - height) / 2 - rise
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        fillColor: menuTap.pressed ? Theme.graphite : Theme.lacquer
                        strokeColor: "transparent"
                        startX: 0; startY: 0
                        PathLine { x: bar.width - Theme.lean * bar.height; y: 0 }
                        PathLine { x: bar.width; y: bar.height }
                        PathLine { x: Theme.lean * bar.height; y: bar.height }
                        PathLine { x: 0; y: 0 }
                    }
                }
            }
        }

        TapHandler {
            id: menuTap
            onTapped: home.menuRequested()
        }
    }

    Panel {
        id: startButton
        readonly property real entry: home.enter(0.6, 1)
        x: menuButton.x + menuButton.width + 10
        width: parent.width - x - 16
        height: 68
        y: parent.height - height - 18
        color: tap.pressed ? Qt.darker(Theme.lacquer, 1.15) : Theme.lacquer
        woven: false
        outline: "transparent"
        opacity: entry
        scale: tap.pressed ? 0.97 : 1
        Behavior on scale { NumberAnimation { duration: 120 } }
        transform: Translate { x: (1 - startButton.entry) * 14 * Theme.lean; y: (1 - startButton.entry) * 14 }

        Row {
            anchors.centerIn: parent
            spacing: 14

            Item {
                width: 20
                height: 20
                anchors.verticalCenter: parent.verticalCenter

                // Triangle « lecture »
                Shape {
                    x: 2
                    width: 17
                    height: 20
                    visible: !home.armed
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        fillColor: Theme.graphite
                        strokeColor: "transparent"
                        startX: 0; startY: 0
                        PathLine { x: 17; y: 10 }
                        PathLine { x: 0; y: 20 }
                        PathLine { x: 0; y: 0 }
                    }
                }
                // Anneau d'attente du signal GPS
                Shape {
                    anchors.fill: parent
                    visible: home.armed
                    preferredRendererType: Shape.CurveRenderer
                    RotationAnimation on rotation {
                        running: home.armed
                        from: 0
                        to: 360
                        duration: 900
                        loops: Animation.Infinite
                    }
                    ShapePath {
                        strokeColor: Theme.graphite
                        strokeWidth: 3
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        PathAngleArc { centerX: 10; centerY: 10; radiusX: 8; radiusY: 8; startAngle: 0; sweepAngle: 270 }
                    }
                }
            }
            Text {
                text: home.armed ? "Départ au signal GPS" : "Démarrer"
                color: Theme.graphite
                font { family: Theme.sans; pixelSize: 24; weight: Font.DemiBold }
            }
        }

        TapHandler {
            id: tap
            onTapped: home.requestStart()
        }
    }

    // État d'un capteur : nom, pastille (verte : prêt ; ambre qui clignote : pas encore) et valeur
    component Sensor: Item {
        id: sensor
        property string label
        property string value
        property string unit
        property bool ready
        property bool numeric: false
        property int beat  // numéro de la mise à jour : la pastille ambre clignote au rythme des secondes

        Text {
            text: sensor.label
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 14; weight: Font.Medium }
        }
        Row {
            anchors.bottom: parent.bottom
            spacing: 8

            Rectangle {
                id: dot
                anchors.verticalCenter: valueText.verticalCenter
                width: 8
                height: 8
                radius: 4
                color: sensor.ready ? Theme.ok : Theme.warning
                opacity: !sensor.ready && sensor.beat % 2 === 1 ? 0.25 : 1
            }
            Text {
                id: valueText
                text: sensor.value
                color: Theme.lacquer
                font {
                    family: sensor.numeric ? Theme.numbers : Theme.sans
                    pixelSize: sensor.numeric ? 28 : 20
                    weight: Font.DemiBold
                    italic: sensor.numeric
                    features: ({ "tnum": 1 })
                }
            }
            Text {
                anchors.baseline: valueText.baseline
                text: sensor.unit
                color: Theme.ash
                font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
            }
        }
    }
}
