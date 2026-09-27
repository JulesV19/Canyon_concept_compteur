import QtQuick
import "Format.js" as Format

// En grand : l'écart au record, ou le chrono
Item {
    id: hero
    required property var view  // la page segment : le segment et les mesures
    readonly property bool showsGap: !view.finished && view.hasRecord
    readonly property bool seconds: showsGap && Math.abs(view.gap) < 60
    y: 74
    width: parent.width
    height: 150

    Text {
        id: heroValue
        x: (hero.width - implicitWidth - (hero.seconds ? 10 + heroUnit.implicitWidth : 0)) / 2
        anchors { baseline: parent.top; baselineOffset: 142 }
        text: hero.showsGap ? Format.gap(view.seg.gapS) : Format.clock(view.seg.elapsedS)
        color: hero.showsGap ? view.gapColor : Theme.lacquer
        font {
            family: Theme.numbers; pixelSize: text.length > 5 ? 120 : 168; weight: Font.Bold; italic: true
            features: ({ "tnum": 1 })
        }
    }
    Text {
        id: heroUnit
        visible: hero.seconds
        x: heroValue.x + heroValue.implicitWidth + 10
        anchors.baseline: heroValue.baseline
        text: "s"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 30; weight: Font.DemiBold }
    }

    // Record battu : un reflet de laque, penché comme le logo, traverse le temps
    Item {
        anchors.fill: parent
        clip: true
        visible: sheenBand.travel > 0 && sheenBand.travel < 1

        Rectangle {
            id: sheenBand
            property real travel: 0
            x: -200 + travel * (hero.width + 300)
            y: -hero.height / 2
            width: 90
            height: 2 * hero.height
            rotation: -Math.atan(Theme.lean) * 180 / Math.PI
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Qt.rgba(1, 1, 1, 0) }
                GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.18) }
                GradientStop { position: 1; color: Qt.rgba(1, 1, 1, 0) }
            }
        }
    }
    function shine() {
        heroSheen.restart()
    }
    SequentialAnimation {
        id: heroSheen
        PropertyAction { target: sheenBand; property: "travel"; value: 0 }
        PauseAnimation { duration: 300 }
        NumberAnimation { target: sheenBand; property: "travel"; to: 1; duration: 900; easing.type: Easing.InOutCubic }
    }
}
