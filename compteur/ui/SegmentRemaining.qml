import QtQuick
import "Format.js" as Format

// En cours : ce qui reste du segment
Item {
    required property var view  // la page segment : le segment et les mesures
    x: 24
    y: 230
    width: parent.width - 48
    height: 48
    visible: !view.finished

    Text {
        id: remainingLabel
        anchors.verticalCenter: parent.verticalCenter
        text: "RESTANT"
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 24; weight: Font.DemiBold; letterSpacing: 1.5 }
    }
    SlantedBar {
        anchors {
            left: remainingLabel.right; right: remaining.left; verticalCenter: parent.verticalCenter
            leftMargin: 14; rightMargin: 14
        }
        height: 10
        progress: view.seg.progress ?? 0
    }
    Row {
        id: remaining
        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
        spacing: 5

        Text {
            id: remainingValue
            text: view.remainingM < 1000 ? Format.number(Math.round(view.remainingM / 10) * 10)
                                         : Format.number(view.seg.remainingKm, 1)
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 40; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            anchors.baseline: remainingValue.baseline
            text: view.remainingM < 1000 ? "m" : "km"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
        }
    }
}
