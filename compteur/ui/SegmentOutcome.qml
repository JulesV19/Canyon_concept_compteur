import QtQuick
import "Format.js" as Format

// À l'arrivée : l'écart au record, et ce record
Item {
    required property var view  // la page segment : le segment et les mesures
    x: 24
    y: 230
    width: parent.width - 48
    height: 48
    visible: view.finished

    Row {
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8
        visible: view.hasRecord

        Text {
            id: resultGap
            text: Format.gap(view.seg.gapS) + (Math.abs(view.gap) < 60 ? " s" : "")
            color: view.gapColor
            font { family: Theme.numbers; pixelSize: 40; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            anchors.baseline: resultGap.baseline
            text: "SUR TON RECORD"
            color: Theme.ash
            font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5 }
        }
    }
    Text {
        anchors.verticalCenter: parent.verticalCenter
        visible: !view.hasRecord
        text: "Premier temps : il devient ta référence"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
    }
    // L'ancien record (le haut de la page montre l'étiquette « Nouveau record »), ou la date du record gardé
    Text {
        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
        visible: view.hasRecord && (view.seg.newRecord === true || !!view.seg.prDate)
        text: view.seg.newRecord === true ? "Ancien record " + Format.clock(view.seg.prS)
            : "Record du " + Format.dayMonth(view.seg.prDate)
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
    }
}
