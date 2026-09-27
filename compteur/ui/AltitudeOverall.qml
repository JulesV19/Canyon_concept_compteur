import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Tout le parcours (ou toute la sortie) en bande fine : la partie faite en laque
Panel {
    id: overall
    required property var view  // la page altitude : profil, position et mesures
    x: 16
    width: parent.width - 32
    height: parent.height - y - 8
    readonly property rect box: Qt.rect(22, 52, width - 44, 40)
    readonly property real markX: view.onRoute
        ? box.x + Math.max(0, Math.min(1, view.doneKm / Math.max(view.totalKm, 1e-6))) * box.width
        : box.x + box.width
    // Profil ramené dans la bande (au plus 300 points)
    readonly property var line: {
        const pts = view.profile
        const n = pts.length
        if (n < 2)
            return []
        let low = Infinity, high = -Infinity
        for (const p of pts) {
            low = Math.min(low, p.y)
            high = Math.max(high, p.y)
        }
        const range = Math.max(40, high - low)
        const total = view.totalKm || 1
        const toBox = p => Qt.point(box.x + p.x / total * box.width,
                                    box.y + box.height - (p.y - low) / range * box.height)
        const step = Math.ceil(n / 300)
        const out = []
        for (let i = 0; i < n; i += step)
            out.push(toBox(pts[i]))
        if ((n - 1) % step !== 0)
            out.push(toBox(pts[n - 1]))
        return out
    }
    readonly property var area: line.length
        ? line.concat([Qt.point(box.x + box.width, box.y + box.height), Qt.point(box.x, box.y + box.height)])
        : []

    Text {
        x: 22
        y: 14
        text: view.onRoute ? "PARCOURS" : "MA SORTIE"
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 24; weight: Font.DemiBold; letterSpacing: 1.5 }
    }
    Text {
        anchors { right: parent.right; top: parent.top; rightMargin: 22 + overall.cutX; topMargin: 14 }
        visible: view.totalKm > 0
        text: Format.number(view.totalKm, 1) + " km"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
    }

    // À faire, en cendre (aplat au moteur simple, trait lissé)
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.GeometryRenderer
        asynchronous: true
        ShapePath {
            fillColor: Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.12)
            strokeColor: "transparent"
            PathPolyline { path: overall.area }
        }
    }
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        asynchronous: true
        ShapePath {
            strokeColor: Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.6)
            strokeWidth: 1.5
            fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin
            PathPolyline { path: overall.line }
        }
    }
    // Fait, en laque
    Item {
        width: overall.markX
        height: overall.height
        clip: true

        Shape {
            width: overall.width
            height: overall.height
            preferredRendererType: Shape.GeometryRenderer
            asynchronous: true
            ShapePath {
                fillColor: Qt.rgba(Theme.lacquer.r, Theme.lacquer.g, Theme.lacquer.b, 0.22)
                strokeColor: "transparent"
                PathPolyline { path: overall.area }
            }
        }
        Shape {
            width: overall.width
            height: overall.height
            preferredRendererType: Shape.CurveRenderer
            asynchronous: true
            ShapePath {
                strokeColor: Theme.lacquer
                strokeWidth: 2
                fillColor: "transparent"
                joinStyle: ShapePath.RoundJoin
                PathPolyline { path: overall.line }
            }
        }
    }
    Rectangle {
        visible: view.onRoute && overall.line.length > 1
        x: overall.markX - 1
        y: overall.box.y - 6
        width: 2
        height: overall.box.height + 12
        color: Theme.lacquer
    }

    Row {
        x: 22
        y: overall.box.y + overall.box.height + 12
        spacing: 44
        LabeledFigure {
            label: "D+"
            value: Format.number(view.values.ascentM)
            unit: "m"
        }
        LabeledFigure {
            label: view.onRoute ? "RESTE À GRIMPER" : "D−"
            value: Format.number(view.onRoute ? view.values.routeAscentLeftM : view.values.descentM)
            unit: "m"
        }
    }
}
