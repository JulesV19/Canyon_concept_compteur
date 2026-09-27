import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Gros plan sur 5 km : l'aire sous la courbe prend la couleur de la pente
Panel {
    id: zoom
    required property var view  // la page altitude : profil, position et mesures
    x: 16
    width: parent.width - 32
    height: 206
    readonly property rect box: Qt.rect(22, 58, width - 44, height - 58 - 40)
    readonly property color blue: Theme.zones[1]
    // Au moins 40 m de haut : les faux plats restent plats
    readonly property var extent: {
        let low = Infinity, high = -Infinity
        for (const p of view.windowPoints) {
            low = Math.min(low, p.y)
            high = Math.max(high, p.y)
        }
        const middle = (low + high) / 2
        const half = Math.max(20, (high - low) / 2 + 4)
        return { low: middle - half, high: middle + half }
    }
    function toBox(p) {
        return Qt.point(box.x + p.x / view.windowKm * box.width,
                        box.y + box.height - (p.y - extent.low) / (extent.high - extent.low) * box.height)
    }
    function closeArea(run, base) {
        return run.concat([Qt.point(run[run.length - 1].x, base), Qt.point(run[0].x, base), run[0]])
    }
    readonly property var line: view.windowPoints.map(p => toBox(p))
    // Aires sous la courbe, d'un seul tenant par classe de pente : plat, descente, puis montée à 3, 6 et 9 %
    readonly property var areas: {
        const groups = [[], [], [], [], []]
        const pts = view.windowPoints
        const n = pts.length
        const base = box.y + box.height
        let run = null, runClass = -1
        for (let i = 0; i + 1 < n; i++) {
            // Pente lissée sur les voisins (≈ 150 m), en %
            const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 2)]
            const grade = b.x > a.x ? (b.y - a.y) / ((b.x - a.x) * 10) : 0
            const k = grade >= 9 ? 4 : grade >= 6 ? 3 : grade >= 3 ? 2 : grade <= -3 ? 1 : 0
            if (k !== runClass) {
                if (run)
                    groups[runClass].push(closeArea(run, base))
                run = [line[i]]
                runClass = k
            }
            run.push(line[i + 1])
        }
        if (run)
            groups[runClass].push(closeArea(run, base))
        return groups
    }

    Text {
        x: 22
        y: 14
        text: view.onRoute ? "5 PROCHAINS KM" : "5 DERNIERS KM"
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 24; weight: Font.DemiBold; letterSpacing: 1.5 }
    }
    Row {
        anchors { right: parent.right; top: parent.top; rightMargin: 22 + zoom.cutX; topMargin: 10 }
        spacing: 4
        visible: zoom.line.length > 1
        Text {
            id: climbValue
            text: Format.number(view.windowAscent)
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 36; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            anchors.baseline: climbValue.baseline
            text: "m D+"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 20; weight: Font.DemiBold }
        }
    }

    // Aires en aplats : le moteur simple suffit (leur bord haut est couvert par le trait), et coûte bien moins
    // au GPU que le moteur de courbes. Le trait, lui, reste lissé. Les deux se calculent hors du fil de
    // l'interface.
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.GeometryRenderer
        asynchronous: true
        ShapePath {
            fillColor: Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.16)
            strokeColor: "transparent"
            PathMultiline { paths: zoom.areas[0] }
        }
        ShapePath {
            fillColor: Qt.rgba(zoom.blue.r, zoom.blue.g, zoom.blue.b, 0.6)
            strokeColor: "transparent"
            PathMultiline { paths: zoom.areas[1] }
        }
        ShapePath {
            fillColor: Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.85)
            strokeColor: "transparent"
            PathMultiline { paths: zoom.areas[2] }
        }
        ShapePath {
            fillColor: Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.85)
            strokeColor: "transparent"
            PathMultiline { paths: zoom.areas[3] }
        }
        ShapePath {
            fillColor: Qt.rgba(Theme.taillight.r, Theme.taillight.g, Theme.taillight.b, 0.9)
            strokeColor: "transparent"
            PathMultiline { paths: zoom.areas[4] }
        }
    }
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        asynchronous: true
        ShapePath {
            strokeColor: Theme.lacquer
            strokeWidth: 2
            fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin
            capStyle: ShapePath.RoundCap
            PathPolyline { path: zoom.line }
        }
    }

    // Axe : un repère par km
    Rectangle {
        x: zoom.box.x
        y: zoom.box.y + zoom.box.height
        width: zoom.box.width
        height: 1
        color: Theme.hairline
    }
    Repeater {
        model: 6
        delegate: Rectangle {
            required property int index
            x: zoom.box.x + index / 5 * zoom.box.width - 0.5
            y: zoom.box.y + zoom.box.height
            width: 1
            height: 6
            color: Theme.hairline
        }
    }
    Text {
        x: zoom.box.x
        y: zoom.box.y + zoom.box.height + 8
        text: view.onRoute ? "0" : "−5 km"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 18; weight: Font.DemiBold }
    }
    Text {
        anchors { right: parent.right; rightMargin: 22 }
        y: zoom.box.y + zoom.box.height + 8
        text: view.onRoute ? "5 km" : "0"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 18; weight: Font.DemiBold }
    }

    // Position : au bord gauche sur un parcours, au bord droit en sortie libre
    Rectangle {
        readonly property var at: zoom.line.length ? zoom.line[view.onRoute ? 0 : zoom.line.length - 1]
                                                  : Qt.point(0, 0)
        visible: zoom.line.length > 1
        x: at.x - width / 2
        y: at.y - height / 2
        width: 14
        height: 14
        radius: 7
        color: Theme.lacquer
        border { color: Theme.carbon; width: 3 }
    }
    Text {
        x: zoom.box.x
        y: zoom.box.y
        width: zoom.box.width
        height: zoom.box.height
        visible: zoom.line.length < 2
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        text: "Pas d'altitude pour l'instant"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
    }
}
