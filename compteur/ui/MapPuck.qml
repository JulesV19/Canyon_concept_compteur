import QtQuick
import QtQuick.Shapes

// Position : le « Ʌ » du logo, redressé, pointé dans le sens de la marche. Son disque graphite
// le détache du parcours en laque ; en roulant, un halo respire autour.
Item {
    id: puck
    required property Item view  // la carte (MapView)
    width: 48
    height: 48
    x: puck.view.anchorX - width / 2
    y: puck.view.anchorY - height / 2
    rotation: puck.view.shownHeading - puck.view.shownBearing

    Rectangle {
        anchors.centerIn: parent
        width: 48
        height: 48
        radius: 24
        color: Theme.lacquer
        opacity: 0.16
        // Par pas d'un pixel sur le rayon : entre deux, rien à redessiner
        scale: puck.view.live && puck.view.animated ? Math.round((0.9 - 0.2 * Math.cos(2 * Math.PI * puck.view.breath)) * 24) / 24 : 1
    }
    Rectangle {
        anchors.centerIn: parent
        width: 34
        height: 34
        radius: 17
        color: Theme.graphite
        border { color: Theme.lacquer; width: 2 }
    }
    Shape {
        anchors.centerIn: parent
        width: 20
        height: 19
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: Theme.lacquer
            strokeColor: "transparent"
            startX: 8.5; startY: 0
            PathLine { x: 11.5; y: 0 }
            PathLine { x: 20; y: 19 }
            PathLine { x: 15; y: 19 }
            PathLine { x: 10; y: 7.5 }
            PathLine { x: 5; y: 19 }
            PathLine { x: 0; y: 19 }
            PathLine { x: 8.5; y: 0 }
        }
    }
}
