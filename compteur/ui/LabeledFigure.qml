import QtQuick

// Un chiffre du bas : libellé, valeur en chiffres penchés, unité
Item {
    id: small
    property string label
    property string value
    property string unit
    width: Math.max(smallLabel.implicitWidth, smallValue.implicitWidth + 5 + smallUnit.implicitWidth)
    height: 96

    Text {
        id: smallLabel
        text: small.label
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5 }
    }
    Text {
        id: smallValue
        anchors { baseline: parent.top; baselineOffset: 74 }
        text: small.value
        color: Theme.lacquer
        font { family: Theme.numbers; pixelSize: 52; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
    }
    Text {
        id: smallUnit
        x: smallValue.implicitWidth + 5
        anchors.baseline: smallValue.baseline
        text: small.unit
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
    }
}
