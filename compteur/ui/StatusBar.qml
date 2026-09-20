import QtQuick
import QtQuick.Shapes

// Barre d'état : heure à gauche, état de la sortie au centre, GPS et batterie à droite.
Item {
    id: bar
    required property var values
    property bool showRideState: true  // pas d'état de sortie sur l'accueil
    height: 44

    property date now: new Date()
    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: bar.now = new Date()
    }

    Text {
        anchors { left: parent.left; leftMargin: 20; verticalCenter: parent.verticalCenter }
        text: Qt.formatTime(bar.now, "HH:mm")
        color: Theme.lacquer
        font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold; features: ({ "tnum": 1 }) }
    }

    RideState {
        anchors.centerIn: parent
        visible: bar.showRideState
        rideState: bar.values.state ?? "idle"
        autoPaused: bar.values.autoPaused ?? false
        lapNumber: bar.values.lap ? bar.values.lap.number : 1
        beat: bar.values.tick ?? 0
    }

    Row {
        anchors { right: parent.right; rightMargin: 20; verticalCenter: parent.verticalCenter }
        spacing: 14

        SignalBars { bars: bar.values.gpsBars ?? 0; anchors.verticalCenter: parent.verticalCenter }
        Battery {
            percent: bar.values.batteryPct ?? 0
            charging: bar.values.batteryCharging === true
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    // État de la sortie sur une étiquette penchée comme le logo : Prêt, Tour n, Pause, Auto-pause.
    // Pendant l'enregistrement, un point rouge clignote comme un feu arrière, au rythme des mises à jour de chaque
    // seconde : pas d'animation, donc aucune image de plus à dessiner.
    component RideState: Item {
        id: tag
        property string rideState
        property bool autoPaused
        property int lapNumber
        property int beat  // numéro de la mise à jour

        readonly property bool recording: rideState !== "idle" && rideState !== "paused" && !autoPaused
        readonly property var info: {
            if (rideState === "idle")
                return { text: "Prêt", color: Theme.ash }
            if (rideState === "paused")
                return { text: "Pause", color: Theme.warning }
            if (autoPaused)
                return { text: "Auto-pause", color: Theme.warning }
            return { text: "Tour " + lapNumber, color: Theme.taillight }
        }
        readonly property real slant: Theme.lean * height

        width: tagRow.implicitWidth + 2 * slant + 10
        height: 26

        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: Theme.carbonRaised
                strokeColor: "transparent"
                startX: 0; startY: 0
                PathLine { x: tag.width - tag.slant; y: 0 }
                PathLine { x: tag.width; y: tag.height }
                PathLine { x: tag.slant; y: tag.height }
                PathLine { x: 0; y: 0 }
            }
        }
        Row {
            id: tagRow
            anchors.centerIn: parent
            spacing: 7

            Rectangle {
                id: light
                width: 8
                height: 8
                radius: 4
                color: tag.info.color
                opacity: tag.recording && tag.beat % 2 === 1 ? 0.3 : 1
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: tag.info.text
                color: Theme.lacquer
                font { family: Theme.sans; pixelSize: 15; weight: Font.DemiBold }
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    // Qualité du signal GPS : 4 barres de hauteur croissante
    component SignalBars: Row {
        property int bars: 0
        spacing: 5

        Text {
            text: "GPS"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 13; weight: Font.DemiBold; letterSpacing: 0.5 }
            anchors.verticalCenter: parent.verticalCenter
        }
        Row {
            height: 13
            spacing: 2
            Repeater {
                model: 4
                Rectangle {
                    required property int index
                    anchors.bottom: parent.bottom
                    width: 3.5
                    height: 4 + index * 3
                    radius: 1
                    color: Theme.lacquer
                    opacity: index < bars ? 1 : 0.3
                }
            }
        }
    }

    // Batterie : pourcentage + pile qui se vide ; en charge, un éclair et la pile en vert
    component Battery: Row {
        property int percent: 100
        property bool charging: false
        spacing: 6

        Text {
            text: percent + " %"
            color: Theme.lacquer
            font { family: Theme.sans; pixelSize: 16; weight: Font.DemiBold; features: ({ "tnum": 1 }) }
            anchors.verticalCenter: parent.verticalCenter
        }
        Bolt {
            visible: charging
            anchors.verticalCenter: parent.verticalCenter
        }
        Item {
            width: 27
            height: 13
            anchors.verticalCenter: parent.verticalCenter

            Rectangle {
                width: 24
                height: 13
                radius: 3
                color: "transparent"
                border { color: Qt.rgba(1, 1, 1, 0.4); width: 1 }

                Rectangle {
                    x: 2
                    y: 2
                    width: Math.max(2, (parent.width - 4) * percent / 100)
                    height: parent.height - 4
                    radius: 1.5
                    color: charging ? Theme.ok : percent <= 20 ? Theme.danger : Theme.lacquer
                }
            }
            Rectangle {
                x: 25
                y: 4.5
                width: 2
                height: 4
                radius: 1
                color: Qt.rgba(1, 1, 1, 0.4)
            }
        }
    }
}
