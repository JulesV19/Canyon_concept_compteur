import QtQuick
import QtQuick.Shapes

// Un trait : tronçon du parcours ou de la trace
Shape {
    id: line
    property var points: []
    property color stroke
    property real thickness
    preferredRendererType: Shape.CurveRenderer
    ShapePath {
        strokeColor: line.stroke
        strokeWidth: line.thickness
        fillColor: "transparent"
        capStyle: ShapePath.RoundCap
        joinStyle: ShapePath.RoundJoin
        PathPolyline { path: line.points }
    }
}
