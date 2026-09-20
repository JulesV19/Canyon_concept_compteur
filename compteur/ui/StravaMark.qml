import QtQuick
import QtQuick.Shapes

// Logo Strava, redessiné d'après le tracé de Simple Icons (CC0) et coupé en ses deux chevrons. Leurs flancs penchent de
// 0,51 : presque la pente du logo Canyon (0,52). play() : le trait se dessine, le logo se remplit, puis un reflet le
// traverse (0,9 s). Au repos, rien ne bouge.
Item {
    id: mark
    property real draw: 1    // 0 → 1 : trait dessiné
    property real fill: 1    // 0 → 1 : remplissage
    property real sheen: -1  // position du reflet, de 0 (à gauche) à 1 (à droite)
    property real strokePx: 1.5
    readonly property real k: width / 24  // pixels par unité du dessin
    width: 20
    height: width

    function play() {
        drawing.restart()
    }

    readonly property color base: Qt.rgba(Theme.strava.r, Theme.strava.g, Theme.strava.b, fill)
    readonly property color glint: Qt.rgba(1, 0.8, 0.68, fill)
    readonly property real sheenX: -8 + sheen * 40

    Item {
        width: 24
        height: 24
        scale: mark.k
        transformOrigin: Item.TopLeft

        Repeater {
            model: ["M10.463 0L17.471 13.828H13.299L10.463 8.229L7.632 13.828H3.463Z",
                    "M10.233 13.828H13.298L15.387 17.944L17.471 13.828H20.537L15.387 24Z"]
            delegate: Shape {
                id: chevron
                required property string modelData
                required property int index
                width: 24
                height: 24
                preferredRendererType: Shape.CurveRenderer

                ShapePath {
                    strokeColor: Qt.rgba(Theme.strava.r, Theme.strava.g, Theme.strava.b, 1 - mark.fill)
                    strokeWidth: mark.fill < 1 && mark.k > 0 ? mark.strokePx / mark.k : -1
                    joinStyle: ShapePath.MiterJoin
                    // Le petit chevron se dessine un peu après le grand
                    trim.end: Math.max(0, Math.min(1, mark.draw * 1.25 - chevron.index * 0.25))
                    // Reflet : une bande claire, penchée comme le logo Canyon, qui traverse les chevrons
                    fillGradient: LinearGradient {
                        x1: mark.sheenX - 3
                        y1: 13.6
                        x2: mark.sheenX + 3
                        y2: 10.4
                        GradientStop { position: 0.3; color: mark.base }
                        GradientStop { position: 0.5; color: mark.glint }
                        GradientStop { position: 0.7; color: mark.base }
                    }
                    PathSvg { path: chevron.modelData }
                }
            }
        }
    }

    SequentialAnimation {
        id: drawing
        PropertyAction { target: mark; property: "fill"; value: 0 }
        PropertyAction { target: mark; property: "draw"; value: 0 }
        NumberAnimation { target: mark; property: "draw"; to: 1; duration: 350; easing.type: Easing.OutCubic }
        NumberAnimation { target: mark; property: "fill"; to: 1; duration: 150 }
        NumberAnimation { target: mark; property: "sheen"; from: 0; to: 1; duration: 400; easing.type: Easing.InOutCubic }
        PropertyAction { target: mark; property: "sheen"; value: -1 }
    }
}
