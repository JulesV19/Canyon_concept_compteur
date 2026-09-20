import QtQuick
import QtQuick.Shapes

// Barre d'avancement : des segments penchés comme le logo, remplis à mesure qu'on avance
Shape {
    id: bar
    property real progress
    property color color: Theme.lacquer
    property int count: 20
    readonly property real gap: 3
    readonly property real slant: Theme.lean * height
    readonly property real segment: (width - (count - 1) * gap) / count
    readonly property int filled: Math.round(Math.max(0, Math.min(1, progress)) * count)

    // Contours des segments first à last (exclu)
    function outlines(first, last) {
        const list = []
        for (let i = first; i < last; i++) {
            const x = i * (segment + gap)
            list.push([Qt.point(x, 0), Qt.point(x + segment - slant, 0), Qt.point(x + segment, height),
                       Qt.point(x + slant, height), Qt.point(x, 0)])
        }
        return list
    }

    preferredRendererType: Shape.CurveRenderer
    ShapePath {
        fillColor: bar.color
        strokeColor: "transparent"
        PathMultiline { paths: bar.outlines(0, bar.filled) }
    }
    ShapePath {
        fillColor: Theme.carbonRaised
        strokeColor: "transparent"
        PathMultiline { paths: bar.outlines(bar.filled, bar.count) }
    }
}
