import QtQuick
import QtQuick.Shapes

// Curseur de 10 à 100 %, par pas de 5
Item {
    id: track
    property int value
    readonly property real fraction: (value - 10) / 90
    signal moved(int value)
    signal released(int value)
    function valueAt(x) {
        return Math.round((10 + 90 * Math.max(0, Math.min(1, x / width))) / 5) * 5
    }

    Rectangle {
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width
        height: 6
        color: Theme.carbonRaised
    }
    Rectangle {
        anchors.verticalCenter: parent.verticalCenter
        width: track.fraction * parent.width
        height: 6
        color: Theme.lacquer
    }
    // Poignée penchée
    Shape {
        id: handle
        x: track.fraction * track.width - width / 2
        anchors.verticalCenter: parent.verticalCenter
        width: 18
        height: 30
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: Theme.lacquer
            strokeColor: Theme.carbon
            strokeWidth: 2
            startX: 0; startY: 0
            PathLine { x: handle.width - Theme.lean * handle.height / 2; y: 0 }
            PathLine { x: handle.width; y: handle.height }
            PathLine { x: Theme.lean * handle.height / 2; y: handle.height }
            PathLine { x: 0; y: 0 }
        }
    }
    MouseArea {
        anchors.fill: parent
        preventStealing: true
        onPressed: mouse => track.moved(track.valueAt(mouse.x))
        onPositionChanged: mouse => track.moved(track.valueAt(mouse.x))
        onReleased: mouse => track.released(track.valueAt(mouse.x))
    }
}
