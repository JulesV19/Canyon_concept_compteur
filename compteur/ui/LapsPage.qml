import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Page tours : le tour en cours en grand (son chrono, qui clignote en pause, sa distance, sa moyenne et son
// cardio), les tours finis du plus récent au plus ancien, et « Nouveau tour », comme le bouton Lap.
// Le tour qui vient de finir arrive en haut de la liste, en glissant dans l'oblique du logo (pas de bandeau ici).
Item {
    id: page
    required property var ride     // RideModel : tours finis, nouveau tour
    required property var values
    readonly property bool showsLaps: true  // la page montre elle-même le tour fini

    readonly property var lap: values.lap ?? ({})
    readonly property var laps: ride.laps
    readonly property bool paused: values.state === "paused" || values.autoPaused === true
    readonly property var columns: [22, 86, 206, 326]  // tour, temps, distance, moyenne

    // 0 → 1 : entrée du dernier tour fini dans la liste
    property real arrival: 1
    onLapsChanged: if (laps.length > 0) arrive.restart()
    NumberAnimation {
        id: arrive
        target: page
        property: "arrival"
        from: 0
        to: 1
        duration: 600
        easing.type: Easing.OutCubic
    }

    Text {
        id: lapTitle
        x: 24
        y: 8
        text: "Tour " + (page.lap.number ?? 1)
        color: Theme.lacquer
        font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
    }
    Text {
        anchors { left: lapTitle.right; leftMargin: 10; baseline: lapTitle.baseline }
        text: "en cours"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
    }

    // Chrono du tour, en grand
    Text {
        id: lapTime
        x: 20
        anchors { baseline: parent.top; baselineOffset: 142 }
        text: Format.duration(page.lap.timerS)
        color: Theme.lacquer
        // En pause, il clignote au rythme des mises à jour : aucune image de plus à dessiner
        opacity: page.paused && (page.values.tick ?? 0) % 2 === 1 ? 0.3 : 1
        font { family: Theme.numbers; pixelSize: 116; weight: Font.Bold; italic: true; features: ({ "tnum": 1 }) }
    }

    Row {
        id: lapStats
        x: 24
        y: 158
        width: parent.width - 48

        Repeater {
            model: [
                { label: "Distance", value: Format.number(page.lap.distanceKm, 2), unit: "km" },
                { label: "Moyenne", value: Format.number(page.lap.avgSpeedKmh, 1), unit: "km/h" },
                { label: "Cardio", value: Format.number(page.lap.avgHeartRate), unit: "bpm" }
            ]

            delegate: Item {
                id: stat
                required property var modelData
                width: lapStats.width / 3
                height: 58

                Text {
                    text: stat.modelData.label
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
                }
                Text {
                    id: statValue
                    anchors { baseline: parent.top; baselineOffset: 48 }
                    text: stat.modelData.value
                    color: Theme.lacquer
                    font { family: Theme.numbers; pixelSize: 32; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                }
                Text {
                    x: statValue.implicitWidth + 5
                    anchors.baseline: statValue.baseline
                    text: stat.modelData.unit
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
                }
            }
        }
    }

    // Tours finis, du plus récent au plus ancien
    Panel {
        id: history
        x: 16
        y: 228
        width: parent.width - 32
        height: lapButton.y - y - 10

        Repeater {
            model: ["Tour", "Temps", "Distance", "Moyenne"]
            delegate: Text {
                required property int index
                required property string modelData
                x: page.columns[index]
                y: 14
                text: modelData
                color: Theme.ash
                font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
            }
        }
        Rectangle {
            x: 20
            y: 38
            width: parent.width - 40
            height: 1
            color: Theme.hairline
        }
        ListView {
            id: lapList
            y: 39
            width: parent.width
            height: parent.height - y - 6
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: page.laps

            delegate: Item {
                id: lapRow
                required property int index
                required property var modelData
                readonly property real entry: index === 0 ? page.arrival : 1
                width: lapList.width
                height: 44
                opacity: entry
                transform: Translate { x: (1 - lapRow.entry) * 16 * Theme.lean; y: (1 - lapRow.entry) * 16 }

                Text {
                    x: page.columns[0]
                    anchors.verticalCenter: parent.verticalCenter
                    text: lapRow.modelData.number
                    color: Theme.ash
                    font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                }
                Text {
                    x: page.columns[1]
                    anchors.verticalCenter: parent.verticalCenter
                    text: Format.duration(lapRow.modelData.timerS)
                    color: Theme.lacquer
                    font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                }
                Figure {
                    x: page.columns[2]
                    anchors.verticalCenter: parent.verticalCenter
                    value: Format.number(lapRow.modelData.distanceKm, 2)
                    unit: "km"
                }
                Figure {
                    x: page.columns[3]
                    anchors.verticalCenter: parent.verticalCenter
                    value: Format.number(lapRow.modelData.avgSpeedKmh, 1)
                    unit: "km/h"
                }
                Rectangle {
                    x: 20
                    anchors.bottom: parent.bottom
                    width: parent.width - 40
                    height: 1
                    color: Theme.hairline
                    visible: lapRow.index < lapList.count - 1
                }
            }
        }
        Text {
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 28 }
            visible: page.laps.length === 0
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: "Aucun tour fini. Le bouton Lap, ou « Nouveau tour » ci-dessous, clôt le tour en cours."
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
    }

    // Nouveau tour : un simple toucher, comme le bouton Lap (un tour de plus n'efface rien)
    Panel {
        id: lapButton
        x: 16
        y: parent.height - height - 8
        width: parent.width - 32
        height: 68
        cut: 18
        color: lapTap.pressed ? Theme.ash : Theme.carbonRaised
        woven: false
        scale: lapTap.pressed ? 0.97 : 1
        Behavior on scale { NumberAnimation { duration: 120 } }

        Text {
            anchors.centerIn: parent
            text: "Nouveau tour"
            color: lapTap.pressed ? Theme.graphite : Theme.lacquer
            font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
        }
        TapHandler {
            id: lapTap
            onTapped: page.ride.lap()
        }
    }

    // Un chiffre et son unité, sur une ligne
    component Figure: Row {
        id: figure
        property string value
        property string unit
        spacing: 4

        Text {
            id: figureValue
            text: figure.value
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            anchors.baseline: figureValue.baseline
            text: figure.unit
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
        }
    }
}
