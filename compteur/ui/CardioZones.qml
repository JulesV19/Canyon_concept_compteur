import QtQuick
import "Format.js" as Format

// Temps passé dans chaque zone depuis le départ, avec la moyenne et le maximum
Panel {
    id: zonesPanel
    required property var view  // la page cardio : courbe, zones et mesures
    x: 16
    width: parent.width - 32
    height: parent.height - y - 8
    readonly property real longest: view.zoneTimes.reduce((most, s) => Math.max(most, s), 1)
    readonly property real total: view.zoneTimes.reduce((sum, s) => sum + s, 0)

    Text {
        x: 22
        y: 14
        text: "PAR ZONE"
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 24; weight: Font.DemiBold; letterSpacing: 1.5 }
    }
    Row {
        anchors { right: parent.right; top: parent.top; rightMargin: 22 + zonesPanel.cutX; topMargin: 10 }
        spacing: 14
        FigureLine { valueSize: 32; unitSize: 20; value: Format.number(view.values.avgHeartRate); unit: "moy." }
        FigureLine { valueSize: 32; unitSize: 20; value: Format.number(view.values.maxHeartRate); unit: "max" }
    }
    Column {
        x: 22
        y: 52
        width: parent.width - 44
        spacing: 1

        Repeater {
            model: 5
            delegate: ZoneRow {
                required property int index
                zone: index
                seconds: view.zoneTimes[index] ?? 0
                longest: zonesPanel.longest
                total: zonesPanel.total
            }
        }
    }
}
