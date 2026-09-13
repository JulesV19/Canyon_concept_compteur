import QtQuick
import QtQuick.Shapes

// Intro : le vélo se dessine au trait, son triangle avant se replie en « Ʌ », les autres lettres de CANYON
// se dessinent autour, le logo se remplit et brille, puis se pose en haut de l'accueil pendant que l'accueil apparaît.
// Tout suit une seule horloge `t` (en ms) : l'intro s'enregistre image par image et se passe d'un geste.
Item {
    id: intro
    property Item target  // logo de l'accueil, où l'intro se termine
    property bool autoplay: true
    property real t: 0
    readonly property real duration: 4100
    readonly property bool done: t >= duration

    // Ce que l'intro orchestre autour d'elle : l'entrée de l'accueil et de la barre d'état (0 → 1)
    readonly property real reveal: span(3050, 4100)
    readonly property real chrome: span(3250, 3650)

    function span(a, b) {
        return Math.max(0, Math.min(1, (t - a) / (b - a)))
    }
    function inOut(x) {
        return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2
    }
    function lerp(a, b, x) {
        return a + (b - a) * x
    }
    // Passer l'intro : elle file jusqu'à la fin au lieu de s'arrêter net
    function skip() {
        if (done || fastForward.running)
            return
        clock.stop()
        fastForward.from = t
        fastForward.start()
    }

    NumberAnimation on t {
        id: clock
        running: intro.autoplay
        from: 0
        to: intro.duration
        duration: intro.duration
    }
    NumberAnimation {
        id: fastForward
        target: intro
        property: "t"
        to: intro.duration
        duration: 450
        easing.type: Easing.InOutQuad
    }

    // Position du logo : au centre pendant qu'il se forme, puis à sa place sur l'accueil
    // (l'accueil et l'intro ont le même parent)
    readonly property real startWidth: 400
    readonly property real logoX: (width - startWidth) / 2
    readonly property real logoY: bike.y + bike.height / 2 - startWidth * 144 / 2048
    readonly property rect goal: target && target.parent
        ? Qt.rect(target.parent.x + target.x, target.parent.y + target.y, target.width, target.height)
        : Qt.rect(logoX, logoY, startWidth, 0)

    // Un toucher passe l'intro (et rien ne passe à travers)
    MouseArea {
        anchors.fill: parent
        onClicked: intro.skip()
    }

    // Du noir au graphite ; à la fin, le fond s'efface sur l'accueil
    Rectangle {
        anchors.fill: parent
        color: Theme.graphite
        opacity: 1 - intro.span(3050, 3350)

        Rectangle {
            anchors.fill: parent
            color: "black"
            opacity: 1 - intro.span(0, 250)
        }
    }

    BikeLine {
        id: bike
        x: 24
        width: intro.width - 48
        height: 290
        y: (intro.height - height) / 2 - 20
        visible: intro.t < 1760
        wheels: intro.inOut(intro.span(200, 1050))
        frame: intro.inOut(intro.span(350, 1150))
        parts: intro.inOut(intro.span(850, 1400))
        folding: intro.t >= 1400
        erase: intro.inOut(intro.span(1400, 1750))
    }

    // Repli : les 8 points du triangle avant rejoignent ceux du « Ʌ »
    readonly property real fold: inOut(span(1450, 1950))
    readonly property var foldPoints: {
        const k = startWidth / 1024
        const pts = []
        for (let i = 0; i < 8; i++) {
            const a = bike.quadPoints[i]
            const b = logo.aPoints[i]
            pts.push(Qt.point(lerp(bike.x + a.x, logoX + b.x * k, fold), lerp(bike.y + a.y, logoY + b.y * k, fold)))
        }
        pts.push(pts[0])
        return pts
    }
    Shape {
        anchors.fill: parent
        visible: intro.t >= 1400 && intro.t < 1950
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: Theme.ash
            strokeWidth: intro.lerp(bike.lineWidth, logo.strokePx, intro.fold)
            fillColor: "transparent"
            joinStyle: ShapePath.MiterJoin
            PathPolyline { path: intro.foldPoints }
        }
    }

    Logo {
        id: logo
        readonly property real move: intro.inOut(intro.span(2800, 3350))
        width: intro.lerp(intro.startWidth, intro.goal.width, move)
        x: intro.lerp(intro.logoX, intro.goal.x, move)
        y: intro.lerp(intro.logoY, intro.goal.y, move)
        visible: intro.t >= 1950
        unfold: intro.span(1950, 2500)
        fill: intro.inOut(intro.span(2450, 2800))
        sheen: intro.span(2500, 3000)
    }
}
