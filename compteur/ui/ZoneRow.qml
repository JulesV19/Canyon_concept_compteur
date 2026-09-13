import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Une zone cardio : son nom, une barre penchée à sa couleur (la zone la plus longue la remplit),
// le temps passé et sa part du total
Item {
    id: row
    property int zone         // 0 à 4
    property real seconds
    property real longest
    property real total
    property real grow: 1     // 0 → 1 : la barre s'allonge
    readonly property real barSpace: width - 36 - 130
    width: parent ? parent.width : 0
    height: 28

    Text {
        anchors.verticalCenter: parent.verticalCenter
        text: "Z" + (row.zone + 1)
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 14; weight: Font.DemiBold }
    }
    Shape {
        id: bar
        x: 36
        anchors.verticalCenter: parent.verticalCenter
        width: Math.max(8, row.barSpace * row.seconds / Math.max(row.longest, 1) * row.grow)
        height: 12
        visible: row.seconds > 0
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: Theme.zones[row.zone]
            strokeColor: "transparent"
            startX: 0; startY: 0
            PathLine { x: bar.width - Theme.lean * bar.height; y: 0 }
            PathLine { x: bar.width; y: bar.height }
            PathLine { x: Theme.lean * bar.height; y: bar.height }
            PathLine { x: 0; y: 0 }
        }
    }
    Text {
        anchors { right: parent.right; rightMargin: 46; verticalCenter: parent.verticalCenter }
        text: Format.duration(row.seconds)
        color: Theme.lacquer
        font { family: Theme.numbers; pixelSize: 20; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
    }
    Text {
        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
        text: row.total > 0 ? Math.round(row.seconds / row.total * 100) + " %" : "--"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
    }
}
