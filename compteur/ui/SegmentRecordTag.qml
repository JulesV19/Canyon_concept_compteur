import QtQuick
import QtQuick.Shapes

// Record battu (ou premier temps) : une étiquette penchée comme le logo
Item {
    id: recordTag
    required property var view  // la page segment : le segment et les mesures
    readonly property real slant: Theme.lean * height
    visible: view.finished && view.seg.newRecord === true
    anchors { right: parent.right; rightMargin: 24 }
    y: 52
    width: tagRow.implicitWidth + 2 * slant + 10
    height: 36

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: Theme.carbonRaised
            strokeColor: "transparent"
            startX: 0; startY: 0
            PathLine { x: recordTag.width - recordTag.slant; y: 0 }
            PathLine { x: recordTag.width; y: recordTag.height }
            PathLine { x: recordTag.slant; y: recordTag.height }
            PathLine { x: 0; y: 0 }
        }
    }
    Row {
        id: tagRow
        anchors.centerIn: parent
        spacing: 7

        Rectangle {
            width: 10
            height: 10
            radius: 5
            color: Theme.ok
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text: view.hasRecord ? "Nouveau record" : "Premier temps"
            color: Theme.lacquer
            font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
