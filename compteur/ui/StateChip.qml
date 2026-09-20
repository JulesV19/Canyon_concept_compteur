import QtQuick
import QtQuick.Shapes

// État sur une étiquette penchée : un point de couleur (un éclair en charge) et le mot
Item {
    id: chip
    property string text
    property color dot
    property bool charging
    readonly property real slant: Theme.lean * height
    width: chipRow.implicitWidth + 2 * slant + 12
    height: 26

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: Theme.carbonRaised
            strokeColor: "transparent"
            startX: 0; startY: 0
            PathLine { x: chip.width - chip.slant; y: 0 }
            PathLine { x: chip.width; y: chip.height }
            PathLine { x: chip.slant; y: chip.height }
            PathLine { x: 0; y: 0 }
        }
    }
    Row {
        id: chipRow
        anchors.centerIn: parent
        spacing: 7

        Rectangle {
            visible: !chip.charging
            width: 8
            height: 8
            radius: 4
            color: chip.dot
            anchors.verticalCenter: parent.verticalCenter
        }
        Bolt {
            visible: chip.charging
            color: chip.dot
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text: chip.text
            color: Theme.lacquer
            font { family: Theme.sans; pixelSize: 15; weight: Font.DemiBold }
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
