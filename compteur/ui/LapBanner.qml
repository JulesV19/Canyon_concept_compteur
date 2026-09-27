import QtQuick
import "Format.js" as Format

// Bandeau de fin de tour : il glisse dans l'oblique du logo sur la vitesse, quelques secondes,
// et un reflet de laque le traverse à son arrivée. Il annonce aussi une sortie reprise après une coupure, avec ses
// chiffres depuis le départ.
Panel {
    id: banner
    property var lap: ({})
    property string title
    property bool shown: false
    property real entry: shown ? 1 : 0

    // Chiffres d'un tour (temps, distance, moyenne, cardio), sous ce titre (par défaut « Tour n terminé »)
    function show(summary, heading, holdMs) {
        lap = summary
        title = heading ?? "Tour " + (summary.number ?? "") + " terminé"
        shown = true
        sheenAnimation.restart()
        hideTimer.interval = holdMs ?? 4000
        hideTimer.restart()
    }

    height: 190
    color: Theme.carbonRaised
    opacity: entry
    visible: entry > 0
    transform: Translate { x: -(1 - banner.entry) * 36 * Theme.lean; y: -(1 - banner.entry) * 36 }
    Behavior on entry { NumberAnimation { duration: 380; easing.type: Easing.OutCubic } }

    Timer {
        id: hideTimer
        interval: 4000
        onTriggered: banner.shown = false
    }

    Text {
        x: 22
        y: 12
        text: banner.title
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 24; weight: Font.DemiBold }
    }

    // Temps du tour, en grand
    Text {
        x: 22
        anchors { baseline: parent.top; baselineOffset: 102 }
        text: Format.duration(banner.lap.timerS)
        color: Theme.lacquer
        font { family: Theme.numbers; pixelSize: 76; weight: Font.Bold; italic: true; features: ({ "tnum": 1 }) }
    }

    Row {
        x: 22
        y: 124
        width: parent.width - 44

        Repeater {
            model: [
                { label: "DISTANCE", value: Format.number(banner.lap.distanceKm, 2), unit: "km" },
                { label: "MOYENNE", value: Format.number(banner.lap.avgSpeedKmh, 1), unit: "km/h" },
                { label: "CARDIO", value: Format.number(banner.lap.avgHeartRate), unit: "bpm" }
            ]

            delegate: Item {
                required property var modelData
                width: parent.width / 3
                height: 58

                Text {
                    text: modelData.label
                    color: Theme.ash
                    font { family: Theme.numbers; pixelSize: 20; weight: Font.DemiBold; letterSpacing: 1.5 }
                }
                Text {
                    id: statValue
                    anchors { baseline: parent.bottom; baselineOffset: -6 }
                    text: modelData.value
                    color: Theme.lacquer
                    font { family: Theme.numbers; pixelSize: 36; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                }
                Text {
                    x: statValue.implicitWidth + 5
                    anchors.baseline: statValue.baseline
                    text: modelData.unit
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 20; weight: Font.DemiBold }
                }
            }
        }
    }

    // Reflet de laque, penché comme le logo, qui traverse le bandeau à son arrivée
    Item {
        anchors.fill: parent
        clip: true

        Rectangle {
            id: sheen
            property real travel: 0
            x: -260 + travel * (banner.width + 360)
            y: -banner.height / 2
            width: 90
            height: 2 * banner.height
            rotation: -Math.atan(Theme.lean) * 180 / Math.PI
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Qt.rgba(1, 1, 1, 0) }
                GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.12) }
                GradientStop { position: 1; color: Qt.rgba(1, 1, 1, 0) }
            }
        }
    }
    SequentialAnimation {
        id: sheenAnimation
        PropertyAction { target: sheen; property: "travel"; value: 0 }
        PauseAnimation { duration: 200 }
        NumberAnimation { target: sheen; property: "travel"; to: 1; duration: 900; easing.type: Easing.InOutCubic }
    }
}
