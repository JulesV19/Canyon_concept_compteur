import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Shapes
import "Format.js" as Format

// Page cardio : la fréquence cardiaque et sa zone, la courbe des 10 dernières minutes aux couleurs des zones,
// puis le temps passé dans chaque zone, avec la moyenne et le maximum.
Item {
    id: page
    required property var ride     // RideModel : courbe cardio
    required property var values

    // La courbe suit chaque seconde quand la page est à l'écran ; voisine (elle peut arriver sous le doigt), elle est
    // dessinée une fois, en arrivant à côté ; ailleurs, rien n'est recalculé.
    readonly property bool live: SwipeView.isCurrentItem && visible
    readonly property bool near: SwipeView.isNextItem || SwipeView.isPreviousItem
    property var curve: []  // (âge en s, bpm), du plus ancien au plus récent : une moyenne toutes les 5 s
    function refresh() {
        curve = ride.heartRateCurve
    }
    onLiveChanged: if (live) refresh()
    onNearChanged: if (near) refresh()
    Connections {
        target: page.ride
        enabled: page.live
        function onChanged() { page.refresh() }
    }
    readonly property var bounds: values.hrZoneBounds ?? []           // début des zones 2 à 5, en bpm
    readonly property int zone: values.hrZone ?? 0                    // 1 à 5 ; 0 : inconnue
    readonly property var zoneTimes: values.hrZonesS ?? [0, 0, 0, 0, 0]
    readonly property color zoneColor: zone > 0 ? Theme.zones[zone - 1] : Theme.ash
    readonly property var zoneNames: ["Récupération", "Endurance", "Tempo", "Seuil", "Maximum"]

    // Zone (0 à 4) d'une fréquence cardiaque
    function zoneIndex(bpm) {
        let z = 0
        for (const bound of bounds)
            if (bpm >= bound)
                z++
        return z
    }

    // Fréquence cardiaque et zone, en grand
    Item {
        id: top
        width: parent.width
        height: 120

        HeroFigure {
            id: heartRate
            x: 24
            label: "Cardio"
            value: Format.number(page.values.heartRate)
            unit: "bpm"
        }
        Shape {
            id: divider
            x: top.width / 2 + 6
            y: 14
            height: top.height - 28
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Theme.hairline
                strokeWidth: 1
                fillColor: "transparent"
                startX: -Theme.lean * divider.height / 2; startY: 0
                PathLine { x: Theme.lean * divider.height / 2; y: divider.height }
            }
        }
        Text {
            x: top.width / 2 + 38
            y: 8
            text: page.zone > 0 ? "Zone " + page.zone : "Zone"
            color: page.zoneColor
            font { family: Theme.sans; pixelSize: 15; weight: Font.DemiBold }
        }
        ZoneGauge {
            x: top.width / 2 + 38
            y: 46
            zone: page.zone
            segmentWidth: 30
            segmentHeight: 14
            spacing: 4
        }
        Text {
            x: top.width / 2 + 38
            anchors { baseline: parent.top; baselineOffset: heartRate.valueBaseline }
            text: page.zone > 0 ? page.zoneNames[page.zone - 1] : "--"
            color: Theme.lacquer
            font { family: Theme.sans; pixelSize: 21; weight: Font.DemiBold }
        }
    }

    // Les 10 dernières minutes : la courbe prend la couleur de sa zone ; les seuils des zones en filets
    Panel {
        id: chart
        x: 16
        y: top.height + 4
        width: parent.width - 32
        height: 220
        readonly property rect box: Qt.rect(22, 46, width - 44 - 40, height - 46 - 32)
        // Au moins 40 bpm de haut
        readonly property var extent: {
            let low = Infinity, high = -Infinity
            for (const p of page.curve) {
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
            for (const point of page.curve) {
                const p = toChart(point)
                const z = page.zoneIndex(point.y)
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
            text: "10 dernières minutes"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }

        // Seuils des zones 2 à 5, à leur couleur
        Repeater {
            model: page.bounds
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
                    font { family: Theme.numbers; pixelSize: 13; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
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
            readonly property var at: page.curve.length ? chart.toChart(page.curve[page.curve.length - 1]) : Qt.point(0, 0)
            visible: page.curve.length > 0
            x: at.x - width / 2
            y: at.y - height / 2
            width: 12
            height: 12
            radius: 6
            color: page.zoneColor
            border { color: Theme.carbon; width: 3 }
        }

        Text {
            x: chart.box.x
            y: chart.box.y + chart.box.height + 10
            text: "−10 min"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 12; weight: Font.Medium }
        }
        Text {
            x: chart.box.x + chart.box.width - width
            y: chart.box.y + chart.box.height + 10
            text: "maintenant"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 12; weight: Font.Medium }
        }
        Text {
            x: chart.box.x
            y: chart.box.y
            width: chart.box.width
            height: chart.box.height
            visible: page.curve.length < 2
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            text: "Pas de mesure cardio pour l'instant"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
    }

    // Temps passé dans chaque zone depuis le départ, avec la moyenne et le maximum
    Panel {
        id: zonesPanel
        x: 16
        y: chart.y + chart.height + 10
        width: parent.width - 32
        height: parent.height - y - 8
        readonly property real longest: page.zoneTimes.reduce((most, s) => Math.max(most, s), 1)
        readonly property real total: page.zoneTimes.reduce((sum, s) => sum + s, 0)

        Text {
            x: 22
            y: 14
            text: "Temps par zone"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
        Row {
            anchors { right: parent.right; top: parent.top; rightMargin: 22 + zonesPanel.cutX; topMargin: 10 }
            spacing: 14
            Figure { value: Format.number(page.values.avgHeartRate); unit: "moy." }
            Figure { value: Format.number(page.values.maxHeartRate); unit: "max" }
        }
        Column {
            x: 22
            y: 44
            width: parent.width - 44
            spacing: 2

            Repeater {
                model: 5
                delegate: ZoneRow {
                    required property int index
                    zone: index
                    seconds: page.zoneTimes[index] ?? 0
                    longest: zonesPanel.longest
                    total: zonesPanel.total
                }
            }
        }
    }

    // Un chiffre et son unité, sur une ligne
    component Figure: Row {
        id: figure
        property string value
        property string unit
        spacing: 4

        Text {
            id: figureValue
            text: figure.value
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            anchors.baseline: figureValue.baseline
            text: figure.unit
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
        }
    }
}
