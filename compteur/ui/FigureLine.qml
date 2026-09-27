import QtQuick

// Un chiffre et son unité, sur une ligne
Row {
    id: figure
    property string value
    property string unit
    property int valueSize: 28
    property int unitSize: 17
    spacing: 4

    Text {
        id: figureValue
        text: figure.value
        color: Theme.lacquer
        font { family: Theme.numbers; pixelSize: figure.valueSize; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
    }
    Text {
        anchors.baseline: figureValue.baseline
        text: figure.unit
        color: Theme.ash
        font { family: Theme.sans; pixelSize: figure.unitSize; weight: Font.DemiBold }
    }
}
