import QtQuick
import "Format.js" as Format

// Annonce d'un segment en favori, à 300 m de son départ : le bandeau glisse dans l'oblique du logo, le logo Strava se
// dessine, puis un reflet de laque traverse le bandeau. La distance décroît à chaque seconde ; le bandeau s'en va au
// départ du segment, ou si l'on s'en éloigne.
Panel {
    id: banner
    required property var values
    required property var profile          // (km, m) du segment annoncé
    readonly property var approach: values.segmentApproach
    readonly property bool shown: approach !== undefined
    property var card: ({})                // dernier segment annoncé : il reste affiché pendant que le bandeau s'en va
    property real entry: shown ? 1 : 0

    onApproachChanged: {
        if (approach !== undefined)
            card = approach
    }
    onShownChanged: {
        if (shown) {
            mark.play()
            sheenAnimation.restart()
        }
    }

    height: 190
    color: Theme.carbonRaised
    opacity: entry
    visible: entry > 0
    transform: Translate { x: -(1 - banner.entry) * 36 * Theme.lean; y: -(1 - banner.entry) * 36 }
    Behavior on entry { NumberAnimation { duration: 380; easing.type: Easing.OutCubic } }

    StravaMark {
        id: mark
        x: 22
        y: 15
        width: 18
    }
    Text {
        id: title
        x: 48
        y: 14
        text: "Segment dans"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
    }
    Text {
        x: title.x + title.implicitWidth + 6
        anchors.baseline: title.baseline
        text: Format.number(Math.round((banner.card.distanceM ?? 0) / 10) * 10) + " m"
        color: Theme.lacquer
        font { family: Theme.numbers; pixelSize: 20; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
    }
    Text {
        x: 22
        y: 42
        width: parent.width - 44
        elide: Text.ElideRight
        text: banner.card.name ?? ""
        color: Theme.lacquer
        font { family: Theme.sans; pixelSize: 28; weight: Font.DemiBold }
    }
    SegmentProfile {
        x: 22
        y: 88
        width: parent.width - 44
        height: 26
        points: banner.profile
        axis: false
        showPosition: false
        lineWidth: 1.5
    }

    Row {
        x: 22
        y: 124
        width: parent.width - 44

        Repeater {
            model: [
                { label: "Distance", value: Format.number(banner.card.lengthKm, 1), unit: "km" },
                { label: "Pente moy.", value: Format.number(banner.card.gradePct, 1), unit: "%" },
                { label: "Record", value: Format.clock(banner.card.prS), unit: "" }
            ]

            delegate: Item {
                required property var modelData
                width: parent.width / 3
                height: 50

                Text {
                    text: modelData.label
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
                }
                Text {
                    id: statValue
                    anchors { baseline: parent.bottom; baselineOffset: -6 }
                    text: modelData.value
                    color: Theme.lacquer
                    font { family: Theme.numbers; pixelSize: 27; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                }
                Text {
                    x: statValue.implicitWidth + 5
                    anchors.baseline: statValue.baseline
                    text: modelData.unit
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
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
