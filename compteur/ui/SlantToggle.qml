import QtQuick
import QtQuick.Shapes

// Interrupteur penché comme le logo : laque quand il est activé
Item {
    id: toggle
    property bool checked
    width: 66
    height: 32
    readonly property real slant: Theme.lean * height

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: toggle.checked ? Theme.lacquer : Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.22)
            strokeColor: "transparent"
            startX: 0; startY: 0
            PathLine { x: toggle.width - toggle.slant; y: 0 }
            PathLine { x: toggle.width; y: toggle.height }
            PathLine { x: toggle.slant; y: toggle.height }
            PathLine { x: 0; y: 0 }
        }
    }
    Shape {
        id: knob
        y: 4
        width: 26
        height: toggle.height - 8
        x: toggle.checked ? toggle.width - width - 8 : 8
        Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: toggle.checked ? Theme.graphite : Theme.ash
            strokeColor: "transparent"
            startX: 0; startY: 0
            PathLine { x: knob.width - Theme.lean * knob.height; y: 0 }
            PathLine { x: knob.width; y: knob.height }
            PathLine { x: Theme.lean * knob.height; y: knob.height }
            PathLine { x: 0; y: 0 }
        }
    }
}
