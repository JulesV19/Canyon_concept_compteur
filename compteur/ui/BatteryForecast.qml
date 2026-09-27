import QtQuick
import QtQuick.Shapes

// Prévision : la charge mesurée depuis la mise en route, puis en tirets jusqu'à vide (ou pleine)
Panel {
    id: forecast
    required property var view  // la page Batterie : ses valeurs et son état
    x: 16
    width: parent.width - 32
    height: 124
    readonly property rect box: Qt.rect(22, 48, width - 44, 38)
    readonly property real nowS: view.values.nowS ?? 0
    readonly property bool forecasting: view.values.forecastS !== null && view.values.forecastS !== undefined
    readonly property real spanS: Math.max(nowS + (forecasting ? view.values.forecastS : 0), 600)
    function toBox(s, pct) {
        return Qt.point(box.x + s / spanS * box.width, box.y + box.height * (1 - Math.max(0, Math.min(100, pct)) / 100))
    }
    readonly property point nowPoint: toBox(nowS, view.percent)
    readonly property point endPoint: toBox(nowS + (view.values.forecastS ?? 0), view.state === "charge" ? 100 : 0)
    // Mesuré : les points de la courbe (au plus 240), puis la lecture du moment
    readonly property var line: {
        if (!view.visible || !view.present)
            return []
        const points = view.curve
        const n = points.length
        const step = Math.max(1, Math.ceil(n / 240))
        const out = []
        for (let i = 0; i < n; i += step)
            out.push(toBox(points[i].x, points[i].y))
        out.push(nowPoint)
        return out
    }
    readonly property var area: line.length > 1
        ? line.concat([Qt.point(nowPoint.x, box.y + box.height), Qt.point(line[0].x, box.y + box.height)])
        : []
    readonly property string headline: !view.present ? ""
        : view.state === "pleine" ? "Batterie pleine"
        : forecasting ? (view.state === "charge" ? "Pleine vers " : "Vide vers ") + view.values.endClock
        : "Stable"

    Text {
        x: 22
        y: 14
        text: "PRÉVISION"
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5 }
    }
    Text {
        anchors { right: parent.right; top: parent.top; rightMargin: 22 + forecast.cutX; topMargin: 12 }
        text: forecast.headline
        color: Theme.lacquer
        font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold; features: ({ "tnum": 1 }) }
    }

    // Repères à 0, 50 et 100 %
    Repeater {
        model: 3
        delegate: Rectangle {
            required property int index
            x: forecast.box.x
            y: forecast.box.y + index * forecast.box.height / 2
            width: forecast.box.width
            height: 1
            color: Theme.hairline
        }
    }

    // Mesuré : aplat (moteur simple) et trait lissé, en laque
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.GeometryRenderer
        ShapePath {
            fillColor: Qt.rgba(Theme.lacquer.r, Theme.lacquer.g, Theme.lacquer.b, 0.16)
            strokeColor: "transparent"
            PathPolyline { path: forecast.area }
        }
    }
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: Theme.lacquer
            strokeWidth: 2
            fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin
            PathPolyline { path: forecast.line }
        }
    }
    // Prévu : en tirets, jusqu'au bout de la courbe
    Shape {
        anchors.fill: parent
        visible: view.present && forecast.forecasting
        ShapePath {
            strokeColor: view.state === "charge" ? Theme.ok : Theme.ash
            strokeWidth: 2
            strokeStyle: ShapePath.DashLine
            dashPattern: [2.5, 2]
            fillColor: "transparent"
            startX: forecast.nowPoint.x; startY: forecast.nowPoint.y
            PathLine { x: forecast.endPoint.x; y: forecast.endPoint.y }
        }
    }
    // Maintenant : un repère penché et la position sur la courbe
    SlantRule {
        visible: view.present
        x: forecast.nowPoint.x
        y: forecast.box.y - 6
        height: forecast.box.height + 12
        color: Qt.rgba(Theme.lacquer.r, Theme.lacquer.g, Theme.lacquer.b, 0.35)
    }
    Rectangle {
        visible: view.present
        x: forecast.nowPoint.x - width / 2
        y: forecast.nowPoint.y - height / 2
        width: 10
        height: 10
        radius: 5
        color: Theme.lacquer
        border { color: Theme.carbon; width: 2 }
    }

    // Heures : mise en route, et fin de la prévision (sinon, maintenant)
    Text {
        x: forecast.box.x
        y: forecast.box.y + forecast.box.height + 6
        text: view.present ? view.values.startClock : ""
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 18; weight: Font.DemiBold; features: ({ "tnum": 1 }) }
    }
    Text {
        anchors.right: parent.right
        anchors.rightMargin: parent.width - forecast.box.x - forecast.box.width
        y: forecast.box.y + forecast.box.height + 6
        text: !view.present ? "" : forecast.forecasting ? view.values.endClock : view.values.nowClock
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 18; weight: Font.DemiBold; features: ({ "tnum": 1 }) }
    }
}
