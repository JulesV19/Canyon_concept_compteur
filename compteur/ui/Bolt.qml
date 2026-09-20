import QtQuick
import QtQuick.Shapes

// Éclair de la batterie en charge, penché comme le logo
Shape {
    id: bolt
    property color color: Theme.ok
    width: 9
    height: 14
    preferredRendererType: Shape.CurveRenderer

    ShapePath {
        fillColor: bolt.color
        strokeColor: "transparent"
        scale: Qt.size(bolt.width / 9, bolt.height / 14)
        startX: 6.2; startY: 0
        PathLine { x: 0.4; y: 8.2 }
        PathLine { x: 4.1; y: 8.2 }
        PathLine { x: 2.6; y: 14 }
        PathLine { x: 8.6; y: 5.6 }
        PathLine { x: 4.9; y: 5.6 }
        PathLine { x: 6.2; y: 0 }
    }
}
