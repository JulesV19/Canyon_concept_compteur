import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Résumé, première page : le tracé et les chiffres clés
Item {
    required property var sheet  // SummaryPage : le résumé, et l'avancée de son apparition

    Panel {
        id: overview
        x: 16
        width: parent.width - 32
        height: parent.height
        readonly property rect trackBox: Qt.rect(24, 16, width - 48, 96)
        readonly property var track: sheet.fit(sheet.summary.outline, trackBox)
        readonly property real drawn: sheet.ease(sheet.span(0, 0.6))

        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Theme.lacquer
                strokeWidth: 3
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                trim.end: overview.drawn
                PathPolyline { path: overview.track }
            }
        }
        // Départ (plein), puis arrivée (creux) une fois le tracé dessiné
        Repeater {
            model: overview.track.length ? [0, overview.track.length - 1] : []
            delegate: Rectangle {
                required property int index
                required property int modelData
                readonly property var at: overview.track[modelData] ?? Qt.point(0, 0)
                x: at.x - width / 2
                y: at.y - height / 2
                width: 12
                height: 12
                radius: 6
                color: index === 0 ? Theme.lacquer : Theme.carbon
                border { color: index === 0 ? Theme.carbon : Theme.lacquer; width: 3 }
                opacity: index === 0 ? (overview.drawn > 0 ? 1 : 0) : sheet.span(0.55, 0.65)
            }
        }
        Text {
            x: overview.trackBox.x
            y: overview.trackBox.y
            width: overview.trackBox.width
            height: overview.trackBox.height
            visible: overview.track.length === 0
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            text: "Pas de trace GPS"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold }
        }

        Rectangle {
            x: 20
            y: 124
            width: parent.width - 40
            height: 1
            color: Theme.hairline
        }
        Grid {
            x: 22
            y: 134
            width: parent.width - 44
            columns: 3
            opacity: sheet.span(0.35, 0.8)

            SummaryStat { label: "Distance"; value: Format.number(sheet.summary.distanceKm, 1); unit: "km" }
            SummaryStat { label: "Temps"; value: Format.duration(sheet.summary.timerS) }
            SummaryStat { label: "Moyenne"; value: Format.number(sheet.summary.avgSpeedKmh, 1); unit: "km/h" }
            SummaryStat { label: "Dénivelé +"; value: Format.number(sheet.summary.ascentM); unit: "m" }
            SummaryStat { label: "Vitesse max"; value: Format.number(sheet.summary.maxSpeedKmh, 1); unit: "km/h" }
            SummaryStat { label: "Temps total"; value: Format.duration(sheet.summary.elapsedS) }
            SummaryStat { label: "Cardio moy."; value: Format.number(sheet.summary.avgHeartRate); unit: "bpm" }
            SummaryStat { label: "FC max"; value: Format.number(sheet.summary.maxHeartRate); unit: "bpm" }
            SummaryStat { label: "Dénivelé −"; value: Format.number(sheet.summary.descentM); unit: "m" }
        }
    }
}
