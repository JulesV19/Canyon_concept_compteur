import QtQuick
import QtQuick.Shapes

// Canyon Ultimate de profil, au trait : cadre taille M (cotes en mm, origine au boîtier de pédalier, y vers le haut).
// L'intro le dessine (wheels, frame, parts de 0 à 1), puis l'efface (erase). Pendant ce temps,
// le triangle avant (quadPoints) est repris par l'intro pour devenir le « Ʌ » du logo.
Item {
    id: bike

    property color color: Theme.ash
    property real lineWidth: 2
    property real wheels: 1       // roues dessinées (0 à 1)
    property real frame: 1        // cadre dessiné, une pointe lumineuse en tête
    property real parts: 1        // tube de selle, fourche, cintre, selle, pédalier
    property real erase: 0        // tout s'efface, sauf le triangle avant
    property bool folding: false  // le triangle avant est repris par l'intro

    readonly property color rim: Qt.rgba(color.r, color.g, color.b, 0.4)

    // Le vélo hors tout va de −744 à 929 mm en x et de −270 à 722 mm en y
    readonly property real k: Math.min(width / 1690, height / 1010)
    readonly property real ox: width / 2 - 92.5 * k
    readonly property real oy: height / 2 + 226 * k

    function p(x, y) {
        return Qt.point(ox + x * k, oy - y * k)
    }
    function along(a, b, f) {
        return Qt.point(a.x + (b.x - a.x) * f, a.y + (b.y - a.y) * f)
    }
    // Chemin SVG en mm → chemin SVG en pixels (les nombres vont par paires x, y)
    function svg(commands) {
        let out = ""
        let pending = null
        for (const c of commands) {
            if (typeof c === "string") {
                out += c
            } else if (pending === null) {
                pending = c
            } else {
                const q = p(pending, c)
                out += q.x.toFixed(1) + "," + q.y.toFixed(1) + " "
                pending = null
            }
        }
        return out
    }

    readonly property point rearAxle: p(-404, 70)
    readonly property point frontAxle: p(589, 70)
    readonly property point bottomBracket: p(0, 0)
    readonly property point headTop: p(389, 564)
    readonly property point headBottom: p(433, 421)
    readonly property point seatCluster: p(-139, 470)

    // Cadre d'un seul trait : hauban, tube de selle, tube horizontal, douille, tube diagonal, base
    readonly property var loop: ["M", -404, 70, "L", -125, 422, "L", -139, 470, "L", 389, 564,
                                 "L", 433, 421, "L", 0, 0, "L", -404, 70]

    // Triangle avant en 8 points, dans le sens des aiguilles d'une montre depuis le haut du tube de selle :
    // ils rejoignent un à un les 8 points du « Ʌ »
    readonly property var quadPoints: [seatCluster, headTop, headBottom,
        along(headBottom, bottomBracket, 0.12), along(headBottom, bottomBracket, 0.45),
        along(headBottom, bottomBracket, 0.47), along(headBottom, bottomBracket, 0.85), bottomBracket]

    readonly property real rearDraw: Math.min(1, wheels * 1.15)
    readonly property real frontDraw: Math.max(0, wheels * 1.15 - 0.15)

    // Cercle dessiné depuis le sol ; en s'effaçant, il fait un tour
    component Ring: ShapePath {
        id: ring
        property point center
        property real radius
        property real draw: 1
        property real erase: 0
        property color lineColor
        property real lineWidth: 2
        strokeColor: lineColor
        strokeWidth: lineWidth
        fillColor: "transparent"
        capStyle: ShapePath.RoundCap
        trim.start: erase
        trim.end: draw
        trim.offset: 0.5 * erase
        PathAngleArc {
            centerX: ring.center.x
            centerY: ring.center.y
            radiusX: ring.radius
            radiusY: ring.radius
            startAngle: 90
            sweepAngle: 360
        }
    }

    component Line: ShapePath {
        id: line
        property string svgPath
        property real draw: 1
        property real erase: 0
        property color lineColor
        property real lineWidth: 2
        strokeColor: lineColor
        strokeWidth: lineWidth
        fillColor: "transparent"
        capStyle: ShapePath.RoundCap
        joinStyle: ShapePath.MiterJoin
        trim.start: erase
        trim.end: draw
        PathSvg { path: line.svgPath }
    }

    // Roues (pneu, jante, moyeu) et plateau
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        Ring { center: bike.rearAxle; radius: 336 * bike.k; draw: bike.rearDraw; erase: bike.erase; lineColor: bike.color; lineWidth: bike.lineWidth }
        Ring { center: bike.rearAxle; radius: 298 * bike.k; draw: bike.rearDraw; erase: bike.erase; lineColor: bike.rim; lineWidth: bike.lineWidth * 0.75 }
        Ring { center: bike.rearAxle; radius: 16 * bike.k; draw: bike.rearDraw; erase: bike.erase; lineColor: bike.color; lineWidth: bike.lineWidth }
        Ring { center: bike.frontAxle; radius: 336 * bike.k; draw: bike.frontDraw; erase: bike.erase; lineColor: bike.color; lineWidth: bike.lineWidth }
        Ring { center: bike.frontAxle; radius: 298 * bike.k; draw: bike.frontDraw; erase: bike.erase; lineColor: bike.rim; lineWidth: bike.lineWidth * 0.75 }
        Ring { center: bike.frontAxle; radius: 16 * bike.k; draw: bike.frontDraw; erase: bike.erase; lineColor: bike.color; lineWidth: bike.lineWidth }
        Ring { center: bike.bottomBracket; radius: 92 * bike.k; draw: bike.parts; erase: bike.erase; lineColor: bike.color; lineWidth: bike.lineWidth }
    }

    // Le cadre, tracé d'un seul trait
    Shape {
        anchors.fill: parent
        visible: !bike.folding
        preferredRendererType: Shape.CurveRenderer
        Line { svgPath: bike.svg(bike.loop); draw: bike.frame; lineColor: bike.color; lineWidth: bike.lineWidth }
    }

    // Pendant le repli : hauban et base se rétractent vers le cadre
    Shape {
        anchors.fill: parent
        visible: bike.folding
        preferredRendererType: Shape.CurveRenderer
        Line { svgPath: bike.svg(["M", -404, 70, "L", -125, 422]); erase: bike.erase; lineColor: bike.color; lineWidth: bike.lineWidth }
        Line { svgPath: bike.svg(["M", -404, 70, "L", 0, 0]); erase: bike.erase; lineColor: bike.color; lineWidth: bike.lineWidth }
    }

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        // Bas du tube de selle : repris par le « Ʌ » dès le début du repli
        Line {
            svgPath: bike.svg(["M", 0, 0, "L", -125, 422])
            draw: bike.folding ? 0 : bike.parts
            lineColor: bike.color; lineWidth: bike.lineWidth
        }
        // Tige de selle et selle
        Line {
            svgPath: bike.svg(["M", -139, 470, "L", -206, 695, "M", -305, 705, "C", -270, 722, -210, 720, -160, 716, "L", -85, 708])
            draw: bike.parts; erase: bike.erase
            lineColor: bike.color; lineWidth: bike.lineWidth
        }
        // Fourche
        Line {
            svgPath: bike.svg(["M", 433, 421, "Q", 485, 250, 589, 70])
            draw: bike.parts; erase: bike.erase
            lineColor: bike.color; lineWidth: bike.lineWidth
        }
        // Potence et cintre
        Line {
            svgPath: bike.svg(["M", 389, 564, "L", 396, 588, "L", 495, 574, "L", 535, 578,
                               "C", 572, 578, 584, 548, 578, 515, "C", 572, 478, 552, 460, 515, 458])
            draw: bike.parts; erase: bike.erase
            lineColor: bike.color; lineWidth: bike.lineWidth
        }
        // Manivelle et pédale
        Line {
            svgPath: bike.svg(["M", 0, 0, "L", 60, -160, "M", 36, -160, "L", 84, -160])
            draw: bike.parts; erase: bike.erase
            lineColor: bike.color; lineWidth: bike.lineWidth
        }
    }

    // Pointe lumineuse qui trace le cadre
    PathInterpolator {
        id: pen
        progress: bike.frame
        path: Path {
            PathSvg { path: bike.svg(bike.loop) }
        }
    }
    Shape {
        width: 44
        height: 44
        x: pen.x - 22
        y: pen.y - 22
        visible: bike.frame > 0 && bike.frame < 1
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: 22; centerY: 22; centerRadius: 22
                focalX: 22; focalY: 22
                GradientStop { position: 0; color: Qt.rgba(1, 1, 1, 1) }
                GradientStop { position: 0.12; color: Qt.rgba(1, 1, 1, 0.85) }
                GradientStop { position: 0.35; color: Qt.rgba(0.66, 0.67, 0.67, 0.28) }
                GradientStop { position: 1; color: Qt.rgba(0.66, 0.67, 0.67, 0) }
            }
            PathAngleArc { centerX: 22; centerY: 22; radiusX: 22; radiusY: 22; startAngle: 0; sweepAngle: 360 }
        }
    }
}
