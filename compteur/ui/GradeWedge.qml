import QtQuick
import QtQuick.Shapes

// Pente dessinée : un triangle qui monte ou descend comme la route (exagéré), à la couleur de la pente
Shape {
    id: wedge
    property real grade
    property color color: Theme.gradeColor(grade)
    width: 34
    height: 22
    readonly property real rise: Math.max(2, Math.min(1, Math.abs(grade) / 12) * height)
    preferredRendererType: Shape.CurveRenderer
    ShapePath {
        fillColor: wedge.color
        strokeColor: "transparent"
        startX: 0; startY: wedge.height
        PathLine { x: wedge.width; y: wedge.height }
        PathLine { x: wedge.grade >= 0 ? wedge.width : 0; y: wedge.height - wedge.rise }
        PathLine { x: 0; y: wedge.height }
    }
}
