import QtQuick
import QtQuick.Shapes

// Symbole à la manière des SF Symbols, dessiné dans une boîte de 24 × 24 : `path` en syntaxe SVG, plein ou en trait.
Shape {
    id: glyph
    property string path
    property color color: CarTheme.label
    property real size: CarTheme.pt(24)
    property real stroke: 0  // épaisseur du trait (unités de la boîte) ; 0 : symbole plein
    readonly property real k: size / 24
    width: size
    height: size
    preferredRendererType: Shape.CurveRenderer

    ShapePath {
        fillColor: glyph.stroke > 0 ? "transparent" : glyph.color
        strokeColor: glyph.stroke > 0 ? glyph.color : "transparent"
        strokeWidth: glyph.stroke * glyph.k
        capStyle: ShapePath.RoundCap
        joinStyle: ShapePath.RoundJoin
        scale: Qt.size(glyph.k, glyph.k)
        PathSvg { path: glyph.path }
    }
}
