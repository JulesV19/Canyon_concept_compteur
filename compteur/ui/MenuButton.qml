import QtQuick
import QtQuick.Shapes

// Bouton du menu (Mes sorties, Réglages, Éteindre) : trois traits taillés et étagés dans l'oblique du logo,
// qui se resserrent sous le doigt
Panel {
    id: menuButton
    property real entry: 1  // 0 → 1 : arrivée, dans l'oblique du logo
    signal tapped
    width: 68
    height: 68
    color: menuTap.pressed ? Theme.ash : Theme.carbonRaised
    woven: false
    opacity: entry
    transform: Translate { x: (1 - menuButton.entry) * 14 * Theme.lean; y: (1 - menuButton.entry) * 14 }

    Item {
        id: glyph
        anchors.centerIn: parent
        width: 34
        height: 26
        property real spread: menuTap.pressed ? 6.5 : 9  // écart entre deux traits
        Behavior on spread { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

        Repeater {
            model: 3
            delegate: Shape {
                id: bar
                required property int index
                readonly property real rise: (1 - index) * glyph.spread  // hauteur au-dessus du trait du milieu
                width: 22
                height: 4
                x: (glyph.width - width) / 2 - rise * Theme.lean
                y: (glyph.height - height) / 2 - rise
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    fillColor: menuTap.pressed ? Theme.graphite : Theme.lacquer
                    strokeColor: "transparent"
                    startX: 0; startY: 0
                    PathLine { x: bar.width - Theme.lean * bar.height; y: 0 }
                    PathLine { x: bar.width; y: bar.height }
                    PathLine { x: Theme.lean * bar.height; y: bar.height }
                    PathLine { x: 0; y: 0 }
                }
            }
        }
    }

    TapHandler {
        id: menuTap
        onTapped: menuButton.tapped()
    }
}
