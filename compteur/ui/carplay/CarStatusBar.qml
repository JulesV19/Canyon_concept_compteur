import QtQuick

// Barre d'état de CarPlay : l'heure à gauche ; à droite, un point rouge tant que la sortie enregistre (il clignote au tic
// de chaque seconde, comme le feu arrière du compteur) et la batterie du compteur, à la manière d'iOS.
Item {
    id: bar
    required property var values  // RideModel.values : état de la sortie, batterie
    property bool active: true    // à l'écran : le point clignote
    property int phoneBattery: -1 // charge de l'iPhone, % ; -1 : inconnue
    height: 58

    property date now: new Date()
    Timer {
        interval: 1000
        running: bar.active
        repeat: true
        triggeredOnStart: true
        onTriggered: bar.now = new Date()
    }

    Text {
        anchors { left: parent.left; leftMargin: CarTheme.pt(14); verticalCenter: parent.verticalCenter }
        text: Qt.formatTime(bar.now, "HH:mm")
        color: CarTheme.label
        font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(16); features: ({ "tnum": 1 }) }
    }

    Row {
        anchors { right: parent.right; rightMargin: CarTheme.pt(14); verticalCenter: parent.verticalCenter }
        spacing: CarTheme.pt(7)

        // L'iPhone et sa charge, discrets, avant la batterie du compteur
        Row {
            anchors.verticalCenter: parent.verticalCenter
            visible: bar.phoneBattery >= 0
            spacing: CarTheme.pt(2)
            CarGlyph {
                anchors.verticalCenter: parent.verticalCenter
                size: CarTheme.pt(14)
                color: bar.phoneBattery <= 20 ? CarTheme.red : CarTheme.secondary
                path: "M8.5 1.5 H15.5 A2.5 2.5 0 0 1 18 4 V20 A2.5 2.5 0 0 1 15.5 22.5 H8.5 A2.5 2.5 0 0 1 6 20 V4 A2.5 2.5 0 0 1 8.5 1.5 Z M10 3.5 V4.5 H14 V3.5 Z"
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: bar.phoneBattery + " %"
                color: bar.phoneBattery <= 20 ? CarTheme.red : CarTheme.secondary
                font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(12); features: ({ "tnum": 1 }) }
            }
        }

        Rectangle {
            readonly property string state: bar.values.state ?? "idle"
            readonly property bool recording: state !== "idle" && state !== "paused" && !(bar.values.autoPaused ?? false)
            anchors.verticalCenter: parent.verticalCenter
            visible: state !== "idle"
            width: CarTheme.pt(7)
            height: width
            radius: width / 2
            color: recording ? CarTheme.red : CarTheme.gray
            opacity: recording && (bar.values.tick ?? 0) % 2 === 1 ? 0.3 : 1
        }

        // Pile d'iOS : le pourcentage dans la pile, qui se remplit ; rouge sous 20 %, verte en charge
        Item {
            readonly property int percent: bar.values.batteryPct ?? -1
            readonly property bool charging: bar.values.batteryCharging === true
            anchors.verticalCenter: parent.verticalCenter
            width: CarTheme.pt(27)
            height: CarTheme.pt(13)

            Rectangle {
                id: body
                width: CarTheme.pt(25)
                height: parent.height
                radius: CarTheme.pt(4)
                color: "#59000000"

                Rectangle {
                    width: parent.width * Math.max(0, parent.parent.percent) / 100
                    height: parent.height
                    radius: parent.radius
                    color: parent.parent.charging ? CarTheme.green : parent.parent.percent <= 20 ? CarTheme.red
                        : CarTheme.label
                }
                Text {
                    anchors.centerIn: parent
                    text: parent.parent.percent < 0 ? "–" : parent.parent.percent
                    color: "white"
                    font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(10); features: ({ "tnum": 1 }) }
                }
            }
            Rectangle {
                x: body.width + CarTheme.pt(0.5)
                anchors.verticalCenter: body.verticalCenter
                width: CarTheme.pt(1.5)
                height: CarTheme.pt(4.5)
                radius: width / 2
                color: "#59000000"
            }
        }
    }
}
