import QtQuick
import QtQuick.Shapes

// Où l'on est : des traits penchés comme le logo, plus long et en laque pour l'élément affiché.
Row {
    id: dashes
    property int count
    property int currentIndex
    property bool dark: false  // sur fond clair (page CarPlay)
    spacing: 6

    Repeater {
        model: dashes.count
        delegate: Shape {
            id: dash
            required property int index
            readonly property bool active: index === dashes.currentIndex
            width: active ? 24 : 10
            height: 4
            Behavior on width { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: dashes.dark ? (dash.active ? "#CC000000" : "#40000000")
                    : dash.active ? Theme.lacquer : Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.45)
                strokeColor: "transparent"
                startX: 0; startY: 0
                PathLine { x: dash.width - 2; y: 0 }
                PathLine { x: dash.width; y: dash.height }
                PathLine { x: 2; y: dash.height }
                PathLine { x: 0; y: 0 }
            }
        }
    }
}
