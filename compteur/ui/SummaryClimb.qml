import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Résumé, deuxième page : l'altitude et les zones cardio
Item {
    required property var sheet  // SummaryPage : le résumé, et l'avancée de son apparition

    Panel {
        id: altitude
        x: 16
        width: parent.width - 32
        height: 166
        readonly property var points: sheet.summary.profile ?? []
        readonly property var extent: {
            let low = Infinity, high = -Infinity
            for (const p of points) {
                low = Math.min(low, p.y)
                high = Math.max(high, p.y)
            }
            return { low: low, high: high }
        }
        readonly property rect chartBox: Qt.rect(22, 48, width - 44, 80)
        // Profil ramené dans sa zone (au moins 40 m de haut, pour ne pas grossir les faux plats)
        readonly property var line: {
            if (points.length < 2)
                return []
            const box = chartBox
            const range = Math.max(40, extent.high - extent.low)
            const end = points[points.length - 1].x || 1
            return points.map(p => Qt.point(box.x + p.x / end * box.width,
                                            box.y + box.height - (p.y - extent.low) / range * box.height))
        }

        Text {
            x: 22
            y: 14
            text: "Altitude"
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5; capitalization: Font.AllUppercase }
        }
        Row {
            anchors { right: parent.right; top: parent.top; rightMargin: 22 + altitude.cutX; topMargin: 12 }
            spacing: 14
            FigureLine { value: Format.number(sheet.summary.ascentM); unit: "m D+" }
            FigureLine { value: Format.number(sheet.summary.descentM); unit: "m D−" }
        }

        // Le profil se déroule de gauche à droite
        Item {
            width: altitude.chartBox.x + sheet.ease(sheet.span(0.1, 0.8)) * altitude.chartBox.width
            height: altitude.height
            clip: true

            Shape {
                width: altitude.width
                height: altitude.height
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: "transparent"
                    fillColor: Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.14)
                    PathPolyline {
                        path: altitude.line.length ? altitude.line.concat([
                            Qt.point(altitude.chartBox.x + altitude.chartBox.width, altitude.chartBox.y + altitude.chartBox.height),
                            Qt.point(altitude.chartBox.x, altitude.chartBox.y + altitude.chartBox.height)]) : []
                    }
                }
                ShapePath {
                    strokeColor: Theme.lacquer
                    strokeWidth: 2
                    fillColor: "transparent"
                    joinStyle: ShapePath.RoundJoin
                    PathPolyline { path: altitude.line }
                }
            }
        }
        Text {
            x: 22
            y: altitude.chartBox.y + altitude.chartBox.height + 8
            visible: altitude.line.length > 0
            text: "min " + Format.number(altitude.extent.low) + " m"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 17; weight: Font.DemiBold }
        }
        Text {
            anchors { right: parent.right; rightMargin: 22 }
            y: altitude.chartBox.y + altitude.chartBox.height + 8
            visible: altitude.line.length > 0
            text: "max " + Format.number(altitude.extent.high) + " m"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 17; weight: Font.DemiBold }
        }
        Text {
            x: altitude.chartBox.x
            y: altitude.chartBox.y
            width: altitude.chartBox.width
            height: altitude.chartBox.height
            visible: altitude.line.length === 0
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            text: "Pas d'altitude pendant la sortie"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold }
        }
    }

    Panel {
        id: zonesPanel
        x: 16
        y: altitude.height + 10
        width: parent.width - 32
        height: parent.height - y
        readonly property real longest: sheet.zones.reduce((most, s) => Math.max(most, s), 1)
        readonly property real total: sheet.zones.reduce((sum, s) => sum + s, 0)

        Text {
            x: 22
            y: 14
            text: "Zones cardio"
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5; capitalization: Font.AllUppercase }
        }
        Column {
            x: 22
            y: 44
            width: parent.width - 44
            spacing: 3
            visible: zonesPanel.total > 0

            Repeater {
                model: 5
                delegate: ZoneRow {
                    required property int index
                    zone: index
                    seconds: sheet.zones[index] ?? 0
                    longest: zonesPanel.longest
                    total: zonesPanel.total
                    grow: sheet.ease(sheet.span(0.25 + 0.07 * index, 0.75 + 0.05 * index))
                }
            }
        }
        Text {
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 22; topMargin: 56 }
            visible: zonesPanel.total === 0
            text: "Pas de mesure cardio pendant la sortie"
            wrapMode: Text.WordWrap
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold }
        }
    }
}
