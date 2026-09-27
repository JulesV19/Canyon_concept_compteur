import QtQuick
import QtQuick.Shapes

// Zones cardio : cinq segments penchés aux couleurs des zones, et leurs seuils en bpm
Item {
    id: zones
    property var bounds: []  // début des zones 2 à 5, en bpm
    readonly property real gap: 4
    readonly property real segment: (width - 4 * gap) / 5

    Repeater {
        model: 5
        delegate: Shape {
            id: zone
            required property int index
            x: index * (zones.segment + zones.gap)
            width: zones.segment
            height: 8
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: Theme.zones[zone.index]
                strokeColor: "transparent"
                startX: 0; startY: 0
                PathLine { x: zone.width - 4; y: 0 }
                PathLine { x: zone.width; y: zone.height }
                PathLine { x: 4; y: zone.height }
                PathLine { x: 0; y: 0 }
            }
        }
    }
    Repeater {
        model: zones.bounds
        delegate: Text {
            required property int index
            required property var modelData
            x: (index + 1) * (zones.segment + zones.gap) - zones.gap / 2 - width / 2
            y: 16
            text: modelData
            color: Theme.ash
            font { family: Theme.numbers; pixelSize: 21; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
    }
}
