import QtQuick
import QtQuick.Shapes

// En-tête d'un écran du menu : un chevron et le titre. Un toucher ramène à l'écran précédent.
Item {
    id: header
    property string title
    signal back
    width: parent ? parent.width : 0
    height: 64

    Row {
        anchors { left: parent.left; leftMargin: 22; verticalCenter: parent.verticalCenter }
        spacing: 14

        Shape {
            width: 11
            height: 20
            anchors.verticalCenter: parent.verticalCenter
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Theme.lacquer
                strokeWidth: 2.5
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                startX: 10; startY: 1
                PathLine { x: 1; y: 10 }
                PathLine { x: 10; y: 19 }
            }
        }
        Text {
            text: header.title
            color: Theme.lacquer
            font { family: Theme.sans; pixelSize: 26; weight: Font.DemiBold }
        }
    }
    TapHandler { onTapped: header.back() }
}
