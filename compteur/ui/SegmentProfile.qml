import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Profil d'un segment : ce qui est fait en laque, ce qui reste coloré selon la pente (comme la page altitude), et la
// position. Redessiné tous les 10 m au plus.
Item {
    id: profile
    property var points: []         // (km, m), du départ à l'arrivée
    property real doneKm: 0
    property bool showPosition: true
    property bool axis: true        // repères tous les 500 m et longueur, en dessous
    property real lineWidth: 2
    readonly property real lengthKm: points.length ? points[points.length - 1].x : 0
    readonly property real drawnKm: doneKm >= lengthKm ? lengthKm : Math.floor(doneKm * 100) / 100
    readonly property bool drawable: points.length > 1 && lengthKm > 0
    readonly property real plotHeight: height - (axis ? 30 : 0)
    readonly property color blue: Theme.zones[1]
    // Au moins 40 m de haut : les faux plats restent plats
    readonly property var extent: {
        let low = Infinity, high = -Infinity
        for (const p of points) {
            low = Math.min(low, p.y)
            high = Math.max(high, p.y)
        }
        const middle = (low + high) / 2
        const half = Math.max(20, (high - low) / 2 + 4)
        return { low: middle - half, high: middle + half }
    }
    function toPlot(x, y) {
        return Qt.point(x / lengthKm * width, plotHeight - (y - extent.low) / (extent.high - extent.low) * plotHeight)
    }
    function altitudeAt(km) {
        for (let i = 1; i < points.length; i++) {
            const a = points[i - 1], b = points[i]
            if (b.x >= km)
                return b.x > a.x ? a.y + (b.y - a.y) * (km - a.x) / (b.x - a.x) : b.y
        }
        return points.length ? points[points.length - 1].y : 0
    }
    readonly property var line: drawable ? points.map(p => toPlot(p.x, p.y)) : []
    // Aires sous la courbe, d'un seul tenant par classe : fait, plat, descente, puis montée à 3, 6 et 9 %
    readonly property var areas: {
        const groups = [[], [], [], [], [], []]
        if (!drawable)
            return groups
        const pts = points, n = pts.length, done = drawnKm, base = plotHeight
        const close = run => run.concat([Qt.point(run[run.length - 1].x, base), Qt.point(run[0].x, base), run[0]])
        // Pente lissée sur les voisins, en %
        const gradeClass = i => {
            const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 2)]
            const grade = b.x > a.x ? (b.y - a.y) / ((b.x - a.x) * 10) : 0
            return grade >= 9 ? 5 : grade >= 6 ? 4 : grade >= 3 ? 3 : grade <= -3 ? 2 : 1
        }
        let run = [toPlot(pts[0].x, pts[0].y)], runClass = -1
        for (let i = 0; i + 1 < n; i++) {
            const a = pts[i], b = pts[i + 1]
            const pieces = b.x <= done ? [[b, 0]]
                : a.x >= done ? [[b, gradeClass(i)]]
                : [[Qt.point(done, a.y + (b.y - a.y) * (done - a.x) / (b.x - a.x)), 0], [b, gradeClass(i)]]
            for (const [end, k] of pieces) {
                if (k !== runClass) {
                    if (run.length > 1)
                        groups[runClass].push(close(run))
                    run = [run[run.length - 1]]
                    runClass = k
                }
                run.push(toPlot(end.x, end.y))
            }
        }
        if (run.length > 1)
            groups[runClass].push(close(run))
        return groups
    }

    // Aires en aplats (moteur simple), trait lissé ; les deux se calculent hors du fil de l'interface
    Shape {
        anchors.fill: parent
        visible: profile.drawable
        preferredRendererType: Shape.GeometryRenderer
        asynchronous: true
        ShapePath {
            fillColor: Qt.rgba(Theme.lacquer.r, Theme.lacquer.g, Theme.lacquer.b, 0.22)
            strokeColor: "transparent"
            PathMultiline { paths: profile.areas[0] }
        }
        ShapePath {
            fillColor: Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.16)
            strokeColor: "transparent"
            PathMultiline { paths: profile.areas[1] }
        }
        ShapePath {
            fillColor: Qt.rgba(profile.blue.r, profile.blue.g, profile.blue.b, 0.6)
            strokeColor: "transparent"
            PathMultiline { paths: profile.areas[2] }
        }
        ShapePath {
            fillColor: Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.85)
            strokeColor: "transparent"
            PathMultiline { paths: profile.areas[3] }
        }
        ShapePath {
            fillColor: Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.85)
            strokeColor: "transparent"
            PathMultiline { paths: profile.areas[4] }
        }
        ShapePath {
            fillColor: Qt.rgba(Theme.taillight.r, Theme.taillight.g, Theme.taillight.b, 0.9)
            strokeColor: "transparent"
            PathMultiline { paths: profile.areas[5] }
        }
    }
    Shape {
        anchors.fill: parent
        visible: profile.drawable
        preferredRendererType: Shape.CurveRenderer
        asynchronous: true
        ShapePath {
            strokeColor: Theme.lacquer
            strokeWidth: profile.lineWidth
            fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin
            capStyle: ShapePath.RoundCap
            PathPolyline { path: profile.line }
        }
    }

    // Axe : un repère tous les 500 m, et au bout
    Rectangle {
        visible: profile.axis
        y: profile.plotHeight
        width: parent.width
        height: 1
        color: Theme.hairline
    }
    Repeater {
        model: profile.axis && profile.drawable ? Math.floor(profile.lengthKm * 2) + 1 : 0
        delegate: Rectangle {
            required property int index
            x: index * 0.5 / profile.lengthKm * profile.width - 0.5
            y: profile.plotHeight
            width: 1
            height: 6
            color: Theme.hairline
        }
    }
    Rectangle {
        visible: profile.axis
        x: parent.width - 1
        y: profile.plotHeight
        width: 1
        height: 6
        color: Theme.hairline
    }
    Text {
        visible: profile.axis
        y: profile.plotHeight + 10
        text: "0"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 18; weight: Font.DemiBold }
    }
    Text {
        visible: profile.axis && profile.drawable
        anchors.right: parent.right
        y: profile.plotHeight + 10
        text: Format.number(profile.lengthKm, 1) + " km"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 18; weight: Font.DemiBold }
    }

    // Position
    Rectangle {
        readonly property point at: profile.drawable
            ? profile.toPlot(Math.min(profile.drawnKm, profile.lengthKm), profile.altitudeAt(profile.drawnKm))
            : Qt.point(0, 0)
        visible: profile.showPosition && profile.drawable
        x: at.x - width / 2
        y: at.y - height / 2
        width: 14
        height: 14
        radius: 7
        color: Theme.lacquer
        border { color: Theme.carbon; width: 3 }
    }
}
