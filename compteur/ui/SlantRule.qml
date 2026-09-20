import QtQuick
import QtQuick.Shapes

// Filet penché comme le logo, centré sur x
Shape {
    id: rule
    property color color: Theme.hairline
    preferredRendererType: Shape.CurveRenderer
    ShapePath {
        strokeColor: rule.color
        strokeWidth: 1
        fillColor: "transparent"
        startX: -Theme.lean * rule.height / 2; startY: 0
        PathLine { x: Theme.lean * rule.height / 2; y: rule.height }
    }
}
