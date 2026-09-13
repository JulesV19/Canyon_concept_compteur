import QtQuick
import QtQuick.Shapes

// Panneau à coins coupés dans l'oblique du logo (en haut à droite et en bas à gauche),
// en carbone tissé par défaut.
Item {
    id: panel
    property color color: Theme.carbon
    property color ground: Theme.graphite  // fond sous le panneau, visible dans les coins coupés
    property color outline: Theme.hairline
    property bool woven: true              // trame carbone
    property real cut: 22                  // hauteur de la coupe ; sa largeur suit la pente du logo
    readonly property real cutX: cut * Theme.lean

    Rectangle {
        anchors.fill: parent
        color: panel.color
    }
    Image {
        anchors.fill: parent
        visible: panel.woven
        source: "textures/carbone.png"
        fillMode: Image.Tile
        smooth: false
    }

    // Coins et contour par-dessus le contenu du panneau
    Shape {
        anchors.fill: parent
        z: 10
        preferredRendererType: Shape.CurveRenderer

        // Coin haut droit
        ShapePath {
            fillColor: panel.ground
            strokeColor: "transparent"
            startX: panel.width - panel.cutX; startY: 0
            PathLine { x: panel.width; y: 0 }
            PathLine { x: panel.width; y: panel.cut }
            PathLine { x: panel.width - panel.cutX; y: 0 }
        }
        // Coin bas gauche
        ShapePath {
            fillColor: panel.ground
            strokeColor: "transparent"
            startX: 0; startY: panel.height - panel.cut
            PathLine { x: panel.cutX; y: panel.height }
            PathLine { x: 0; y: panel.height }
            PathLine { x: 0; y: panel.height - panel.cut }
        }
        // Contour
        ShapePath {
            fillColor: "transparent"
            strokeColor: panel.outline
            strokeWidth: 1
            joinStyle: ShapePath.MiterJoin
            startX: 0.5; startY: 0.5
            PathLine { x: panel.width - panel.cutX; y: 0.5 }
            PathLine { x: panel.width - 0.5; y: panel.cut }
            PathLine { x: panel.width - 0.5; y: panel.height - 0.5 }
            PathLine { x: panel.cutX; y: panel.height - 0.5 }
            PathLine { x: 0.5; y: panel.height - panel.cut }
            PathLine { x: 0.5; y: 0.5 }
        }
    }
}
