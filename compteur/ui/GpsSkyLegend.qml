import QtQuick
import QtQuick.Shapes

// Une ligne de légende du ciel : la case telle qu'elle est dessinée, et ce qu'elle veut dire
Row {
    id: legend
    property string kind
    property string text
    spacing: 7

    Shape {
        width: 15
        height: 10
        anchors.verticalCenter: parent.verticalCenter
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: legend.kind === "used" ? Theme.lacquer : "transparent"
            strokeColor: legend.kind === "used" ? "transparent" : legend.kind === "tracked" ? Theme.ash
                : Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.35)
            strokeWidth: legend.kind === "tracked" ? 1.5 : 1
            startX: 0; startY: 0
            PathLine { x: 15 - Theme.lean * 10; y: 0 }
            PathLine { x: 15; y: 10 }
            PathLine { x: Theme.lean * 10; y: 10 }
            PathLine { x: 0; y: 0 }
        }
    }
    Text {
        text: legend.text
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 17; weight: Font.DemiBold }
    }
}
