import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Les 10 dernières minutes : la courbe prend la couleur de sa zone ; les seuils des zones en filets
Panel {
    id: chart
    required property var view  // la page cardio : courbe, zones et mesures
    x: 16
    width: parent.width - 32
    height: 184
    readonly property rect box: Qt.rect(22, 54, width - 44 - 52, height - 54 - 40)
    // Au moins 40 bpm de haut
    readonly property var extent: {
        let low = Infinity, high = -Infinity
        for (const p of view.curve) {
            low = Math.min(low, p.y)
            high = Math.max(high, p.y)
        }
        if (low === Infinity)
            return { low: 60, high: 180 }
        const middle = (low + high) / 2
        const half = Math.max(20, (high - low) / 2 + 6)
        return { low: middle - half, high: middle + half }
    }
    function yOf(bpm) {
        return box.y + box.height - (bpm - extent.low) / (extent.high - extent.low) * box.height
    }
    // Point de la courbe (âge en s, bpm) : maintenant au bord droit, 10 minutes sur toute la largeur
    function toChart(p) {
        return Qt.point(box.x + box.width - p.x * box.width / 599, yOf(p.y))
    }
    // La courbe en morceaux d'une même zone, rangés par zone
    readonly property var runs: {
        const groups = [[], [], [], [], []]
        let run = null, runZone = -1, previous = null
        for (const point of view.curve) {
            const p = toChart(point)
            const z = view.zoneIndex(point.y)
            if (z !== runZone) {
                if (run && run.length > 1)
                    groups[runZone].push(run)
                run = previous ? [previous, p] : [p]
                runZone = z
            } else {
                run.push(p)
            }
            previous = p
        }
        if (run && run.length > 1)
            groups[runZone].push(run)
        return groups
    }

    Text {
        x: 22
        y: 14
        text: "10 DERNIÈRES MINUTES"
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 24; weight: Font.DemiBold; letterSpacing: 1.5 }
    }

    // Seuils des zones 2 à 5, à leur couleur
    Repeater {
        model: view.bounds
        delegate: Item {
            id: threshold
            required property int index
            required property var modelData
            readonly property color tint: Theme.zones[index + 1]
            readonly property real at: chart.yOf(modelData)
            visible: modelData > chart.extent.low && modelData < chart.extent.high

            Rectangle {
                x: chart.box.x
                y: threshold.at
                width: chart.box.width
                height: 1
                color: Qt.rgba(threshold.tint.r, threshold.tint.g, threshold.tint.b, 0.4)
            }
            Text {
                x: chart.box.x + chart.box.width + 8
                y: threshold.at - height / 2
                text: Format.number(threshold.modelData)
                color: threshold.tint
                font { family: Theme.numbers; pixelSize: 20; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
            }
        }
    }

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        asynchronous: true  // tracé calculé hors du fil de l'interface
        ShapePath {
            strokeColor: Theme.zones[0]
            strokeWidth: 3
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathMultiline { paths: chart.runs[0] }
        }
        ShapePath {
            strokeColor: Theme.zones[1]
            strokeWidth: 3
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathMultiline { paths: chart.runs[1] }
        }
        ShapePath {
            strokeColor: Theme.zones[2]
            strokeWidth: 3
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathMultiline { paths: chart.runs[2] }
        }
        ShapePath {
            strokeColor: Theme.zones[3]
            strokeWidth: 3
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathMultiline { paths: chart.runs[3] }
        }
        ShapePath {
            strokeColor: Theme.zones[4]
            strokeWidth: 3
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathMultiline { paths: chart.runs[4] }
        }
    }
    // Maintenant : un point à la couleur de la zone
    Rectangle {
        readonly property var at: view.curve.length ? chart.toChart(view.curve[view.curve.length - 1]) : Qt.point(0, 0)
        visible: view.curve.length > 0
        x: at.x - width / 2
        y: at.y - height / 2
        width: 12
        height: 12
        radius: 6
        color: view.zoneColor
        border { color: Theme.carbon; width: 3 }
    }

    Text {
        x: chart.box.x
        y: chart.box.y + chart.box.height + 8
        text: "−10 min"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 18; weight: Font.DemiBold }
    }
    Text {
        x: chart.box.x + chart.box.width - width
        y: chart.box.y + chart.box.height + 8
        text: "maintenant"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 18; weight: Font.DemiBold }
    }
    Text {
        x: chart.box.x
        y: chart.box.y
        width: chart.box.width
        height: chart.box.height
        visible: view.curve.length < 2
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        text: "Pas de mesure cardio pour l'instant"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
    }
}
