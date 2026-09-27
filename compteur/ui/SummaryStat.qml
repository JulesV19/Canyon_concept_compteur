import QtQuick

// Un chiffre du résumé : libellé, valeur en chiffres penchés, unité
Item {
    id: stat
    property string label
    property string value
    property string unit
    width: parent.width / 3
    height: 84

    Text {
        text: stat.label
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 18; weight: Font.DemiBold; letterSpacing: 1.5; capitalization: Font.AllUppercase }
    }
    Text {
        id: statValue
        anchors { baseline: parent.top; baselineOffset: 58 }
        text: stat.value
        color: Theme.lacquer
        font { family: Theme.numbers; pixelSize: 38; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
    }
    Text {
        x: statValue.implicitWidth + 5
        anchors.baseline: statValue.baseline
        text: stat.unit
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 17; weight: Font.DemiBold }
    }
}
