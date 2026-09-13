import QtQuick
import QtQuick.Shapes

// Zone cardio : cinq segments penchés, allumés jusqu'à la zone en cours, aux couleurs des zones
Row {
    id: gauge
    property int zone: 0  // 1 à 5 ; 0 : inconnue
    property real segmentWidth: 15
    property real segmentHeight: 9
    spacing: 3

    Repeater {
        model: 5
        delegate: Shape {
            id: segment
            required property int index
            width: gauge.segmentWidth
            height: gauge.segmentHeight
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: segment.index < gauge.zone ? Theme.zones[segment.index]
                                                      : Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.18)
                strokeColor: "transparent"
                startX: 0; startY: 0
                PathLine { x: segment.width - Theme.lean * segment.height; y: 0 }
                PathLine { x: segment.width; y: segment.height }
                PathLine { x: Theme.lean * segment.height; y: segment.height }
                PathLine { x: 0; y: 0 }
            }
        }
    }
}
