import QtQuick

// Une mesure : libellé en cendre, valeur en chiffres penchés, unité
Item {
    id: figure
    property string label
    property string value
    property string unit
    readonly property real labelWidth: figureLabel.implicitWidth
    height: 94

    Text {
        id: figureLabel
        y: 12
        text: figure.label
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5 }
    }
    Text {
        id: figureValue
        anchors { baseline: parent.top; baselineOffset: 80 }
        text: figure.value
        color: Theme.lacquer
        font { family: Theme.numbers; pixelSize: 44; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
    }
    Text {
        x: figureValue.implicitWidth + 6
        anchors.baseline: figureValue.baseline
        text: figure.unit
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
    }
}
