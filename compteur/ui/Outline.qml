import QtQuick
import QtQuick.Shapes

// Un tracé ramené entre 0 et 1 (nord en haut), agrandi et centré dans l'élément en gardant ses proportions.
Shape {
    id: outline
    property var points: []
    property color color: Theme.lacquer
    property real thickness: 2

    readonly property var fitted: {
        const pts = points
        const w = width - thickness
        const h = height - thickness
        if (!pts || pts.length < 2 || w <= 0 || h <= 0)
            return []
        let right = 0, bottom = 0
        for (const p of pts) {
            right = Math.max(right, p.x)
            bottom = Math.max(bottom, p.y)
        }
        const s = Math.min(w / Math.max(right, 1e-6), h / Math.max(bottom, 1e-6))
        const dx = (width - right * s) / 2
        const dy = (height - bottom * s) / 2
        return pts.map(p => Qt.point(dx + p.x * s, dy + p.y * s))
    }

    preferredRendererType: Shape.CurveRenderer
    ShapePath {
        strokeColor: outline.color
        strokeWidth: outline.thickness
        fillColor: "transparent"
        capStyle: ShapePath.RoundCap
        joinStyle: ShapePath.RoundJoin
        PathPolyline { path: outline.fitted }
    }
}
