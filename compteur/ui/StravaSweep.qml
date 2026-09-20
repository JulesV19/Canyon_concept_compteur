import QtQuick
import QtQuick.Shapes

// Départ d'un segment (et record battu) : deux bandes orange, penchées comme le flanc du chevron Strava et le logo
// Canyon, balaient la page de gauche à droite en 0,7 s. Hors de ces instants, rien n'est dessiné.
Item {
    id: sweep
    property real travel: 0  // 0 → 1
    readonly property real slant: Theme.lean * height
    readonly property bool running: animation.running
    visible: running
    clip: true

    function run() {
        animation.restart()
    }

    // Une bande de 34 px, 18 px d'écart, puis une de 70 px devant : les deux chevrons du logo
    Shape {
        width: 122 + sweep.slant
        height: sweep.height
        x: -width + sweep.travel * (sweep.width + width)
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            fillColor: Theme.strava
            strokeColor: "transparent"
            startX: 0; startY: 0
            PathLine { x: 34; y: 0 }
            PathLine { x: 34 + sweep.slant; y: sweep.height }
            PathLine { x: sweep.slant; y: sweep.height }
            PathLine { x: 0; y: 0 }
        }
        ShapePath {
            fillColor: Theme.strava
            strokeColor: "transparent"
            startX: 52; startY: 0
            PathLine { x: 122; y: 0 }
            PathLine { x: 122 + sweep.slant; y: sweep.height }
            PathLine { x: 52 + sweep.slant; y: sweep.height }
            PathLine { x: 52; y: 0 }
        }
    }

    NumberAnimation {
        id: animation
        target: sweep
        property: "travel"
        from: 0
        to: 1
        duration: 700
        easing.type: Easing.InOutCubic
    }
}
