import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Carte d'un parcours sur l'accueil : nom, tracé qui se dessine, profil d'altitude, distance et dénivelé.
Panel {
    id: card
    property string name
    property var distanceKm
    property var ascentM
    property var outline: []  // tracé ramené entre 0 et 1, nord en haut
    property var profile: []  // profil : points (distance en km, altitude en m)
    property real draw: 1     // 0 → 1 : le tracé se dessine, puis le profil

    function ease(x) {
        return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2
    }
    readonly property real lineDraw: ease(Math.min(1, draw / 0.75))
    readonly property real profileDraw: ease(Math.max(0, Math.min(1, (draw - 0.35) / 0.65)))

    readonly property rect mapBox: Qt.rect(24, 60, width - 48, height - 60 - 112)
    readonly property rect profileBox: Qt.rect(20, height - 102, width - 40, 40)

    // Le tracé agrandi et centré dans sa zone, en gardant ses proportions
    readonly property var fitted: {
        const pts = outline
        const box = mapBox
        if (!pts || pts.length < 2 || box.width <= 0)
            return []
        let right = 0, bottom = 0
        for (const p of pts) {
            right = Math.max(right, p.x)
            bottom = Math.max(bottom, p.y)
        }
        const s = Math.min(box.width / Math.max(right, 1e-6), box.height / Math.max(bottom, 1e-6))
        const dx = box.x + (box.width - right * s) / 2
        const dy = box.y + (box.height - bottom * s) / 2
        return pts.map(p => Qt.point(dx + p.x * s, dy + p.y * s))
    }

    // Profil d'altitude ramené dans sa bande (au moins 40 m de haut, pour ne pas grossir les faux plats)
    readonly property var profileLine: {
        const pts = profile
        const box = profileBox
        if (!pts || pts.length < 2)
            return []
        let lo = Infinity, hi = -Infinity
        for (const p of pts) {
            lo = Math.min(lo, p.y)
            hi = Math.max(hi, p.y)
        }
        const range = Math.max(40, hi - lo)
        const end = pts[pts.length - 1].x
        return pts.map(p => Qt.point(box.x + p.x / end * box.width, box.y + box.height - (p.y - lo) / range * box.height))
    }

    Text {
        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 24; rightMargin: 24 + card.cutX; topMargin: 18 }
        text: card.name
        elide: Text.ElideRight
        color: Theme.lacquer
        font { family: Theme.sans; pixelSize: 28; weight: Font.DemiBold }
    }

    // Le tracé se dessine depuis le départ
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: Theme.lacquer
            strokeWidth: 3
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            trim.end: card.lineDraw
            PathPolyline { path: card.fitted }
        }
    }
    Rectangle {
        visible: card.fitted.length > 0 && card.lineDraw > 0
        x: visible ? card.fitted[0].x - width / 2 : 0
        y: visible ? card.fitted[0].y - height / 2 : 0
        width: 12
        height: 12
        radius: 6
        color: Theme.lacquer
        border { color: Theme.carbon; width: 3 }
    }

    // Profil d'altitude, qui se déroule de gauche à droite
    Item {
        width: card.profileBox.x + card.profileDraw * card.profileBox.width
        height: card.height
        clip: true

        Shape {
            width: card.width
            height: card.height
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: "transparent"
                fillColor: Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.14)
                PathPolyline {
                    path: card.profileLine.length ? card.profileLine.concat([
                        Qt.point(card.profileBox.x + card.profileBox.width, card.profileBox.y + card.profileBox.height),
                        Qt.point(card.profileBox.x, card.profileBox.y + card.profileBox.height)]) : []
                }
            }
            ShapePath {
                strokeColor: Theme.ash
                strokeWidth: 1.5
                fillColor: "transparent"
                joinStyle: ShapePath.RoundJoin
                PathPolyline { path: card.profileLine }
            }
        }
    }

    // Distance à gauche, dénivelé à droite
    Row {
        anchors { left: parent.left; bottom: parent.bottom; leftMargin: 24; bottomMargin: 12 }
        spacing: 5
        Text {
            id: distance
            text: Format.number(card.distanceKm, 1)
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 46; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            anchors.baseline: distance.baseline
            text: "km"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
        }
    }
    Row {
        anchors { right: parent.right; bottom: parent.bottom; rightMargin: 24; bottomMargin: 12 }
        spacing: 5
        Text {
            id: ascent
            text: Format.number(card.ascentM)
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 46; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            anchors.baseline: ascent.baseline
            text: "m D+"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
        }
    }
}
