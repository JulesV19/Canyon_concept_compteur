import QtQuick
import QtQuick.Shapes

// En-tête d'un écran du menu : un chevron et le titre. Un toucher ramène à l'écran précédent.
Item {
    id: header
    property string title
    signal back
    width: parent ? parent.width : 0
    height: 68

    Row {
        anchors { left: parent.left; leftMargin: 22; verticalCenter: parent.verticalCenter }
        spacing: 14

        Shape {
            width: 13
            height: 24
            anchors.verticalCenter: parent.verticalCenter
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Theme.lacquer
                strokeWidth: 3
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                startX: 12; startY: 1.5
                PathLine { x: 1.5; y: 12 }
                PathLine { x: 12; y: 22.5 }
            }
        }
        Text {
            text: header.title
            color: Theme.lacquer
            font { family: Theme.sans; pixelSize: 32; weight: Font.DemiBold }
        }
    }
    TapHandler { onTapped: header.back() }
}
