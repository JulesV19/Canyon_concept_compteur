import QtQuick

// Grande mesure en tête de page : libellé en cendre, valeur en grands chiffres penchés, unité
Item {
    id: figure
    property string label
    property color labelColor: Theme.ash
    property string value
    property string unit
    readonly property real valueEnd: unitText.x + unitText.implicitWidth
    readonly property real valueBaseline: valueText.y + valueText.baselineOffset
    width: valueEnd
    height: 120

    Text {
        y: 8
        text: figure.label
        color: figure.labelColor
        font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
    }
    Text {
        id: valueText
        anchors { baseline: parent.top; baselineOffset: 102 }
        text: figure.value
        color: Theme.lacquer
        font { family: Theme.numbers; pixelSize: 84; weight: Font.Bold; italic: true; features: ({ "tnum": 1 }) }
    }
    Text {
        id: unitText
        x: valueText.implicitWidth + 8
        anchors.baseline: valueText.baseline
        text: figure.unit
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 18; weight: Font.DemiBold }
    }
}
