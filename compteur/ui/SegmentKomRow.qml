import QtQuick
import "Format.js" as Format

// KOM (ou QOM) : son temps, et l'écart à son allure au même point
Item {
    id: kom
    property var seg: ({})
    width: parent.width
    height: 60
    visible: seg.komS !== null && seg.komS !== undefined

    Text {
        id: komLabel
        x: 22
        anchors { baseline: parent.top; baselineOffset: 38 }
        text: kom.seg.komLabel ?? "KOM"
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5 }
    }
    Text {
        anchors { left: komLabel.right; leftMargin: 10; baseline: parent.top; baselineOffset: 38 }
        text: Format.clock(kom.seg.komS)
        color: Theme.lacquer
        font { family: Theme.numbers; pixelSize: 34; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
    }
    Text {
        anchors { right: parent.right; rightMargin: 22; baseline: parent.top; baselineOffset: 38 }
        text: Format.gap(kom.seg.komGapS)
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 34; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
    }
}
