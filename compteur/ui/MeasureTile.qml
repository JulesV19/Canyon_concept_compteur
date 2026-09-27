import QtQuick

// Une mesure d'un tableau : libellé, valeur (chiffres penchés, ou un mot), unité ; un filet penché à droite
Item {
    id: tile
    property string label
    property string value
    property string unit
    property bool numeric: true
    property color valueColor: Theme.lacquer
    property bool edge: true  // filet à droite (pas sur la dernière colonne)
    property int valueSize: 34  // chiffres ; un mot est un peu plus petit
    property int wordSize: 24

    Text {
        x: 16
        y: 9
        width: tile.width - 22
        text: tile.label
        elide: Text.ElideRight
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 18; weight: Font.DemiBold; letterSpacing: 1.5; capitalization: Font.AllUppercase }
    }
    Text {
        id: tileValue
        x: 16
        anchors { baseline: parent.top; baselineOffset: 54 }
        text: tile.value
        color: tile.valueColor
        font.family: tile.numeric ? Theme.numbers : Theme.sans
        font.pixelSize: tile.numeric ? tile.valueSize : tile.wordSize
        font.weight: Font.DemiBold
        font.italic: tile.numeric
        font.features: ({ "tnum": 1 })
    }
    Text {
        x: tileValue.x + tileValue.implicitWidth + 4
        anchors.baseline: tileValue.baseline
        visible: tile.value !== "--"
        text: tile.unit
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 18; weight: Font.DemiBold }
    }
    SlantRule {
        visible: tile.edge
        x: tile.width
        y: 12
        height: tile.height - 24
    }
}
