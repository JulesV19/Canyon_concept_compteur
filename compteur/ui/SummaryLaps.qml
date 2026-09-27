import QtQuick
import "Format.js" as Format

// Résumé, troisième page : les tours
Item {
    required property var sheet  // SummaryPage : le résumé, et l'avancée de son apparition

    Panel {
        id: lapsPanel
        x: 16
        width: parent.width - 32
        height: parent.height
        readonly property var columns: [22, 90, 214, 330]  // tour, temps, distance, moyenne

        Repeater {
            model: ["Tour", "Temps", "Distance", "Moyenne"]
            delegate: Text {
                required property int index
                required property string modelData
                x: lapsPanel.columns[index]
                y: 16
                text: modelData
                color: Theme.ash
                font { family: Theme.numbers; pixelSize: 20; weight: Font.DemiBold; letterSpacing: 1.5; capitalization: Font.AllUppercase }
            }
        }
        Rectangle {
            x: 20
            y: 46
            width: parent.width - 40
            height: 1
            color: Theme.hairline
        }
        ListView {
            id: lapList
            y: 47
            width: parent.width
            height: parent.height - y - 10
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: sheet.laps

            delegate: Item {
                id: lapRow
                required property int index
                required property var modelData
                readonly property real entry: sheet.span(0.1 + Math.min(index, 8) * 0.06, 0.5 + Math.min(index, 8) * 0.05)
                width: lapList.width
                height: 52
                opacity: entry
                transform: Translate { x: (1 - lapRow.entry) * 12 * Theme.lean; y: (1 - lapRow.entry) * 12 }

                Text {
                    x: lapsPanel.columns[0]
                    anchors.verticalCenter: parent.verticalCenter
                    text: lapRow.modelData.number
                    color: Theme.ash
                    font { family: Theme.numbers; pixelSize: 28; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                }
                Text {
                    x: lapsPanel.columns[1]
                    anchors.verticalCenter: parent.verticalCenter
                    text: Format.duration(lapRow.modelData.timerS)
                    color: Theme.lacquer
                    font { family: Theme.numbers; pixelSize: 28; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                }
                FigureLine {
                    x: lapsPanel.columns[2]
                    anchors.verticalCenter: parent.verticalCenter
                    value: Format.number(lapRow.modelData.distanceKm, 2)
                    unit: "km"
                }
                FigureLine {
                    x: lapsPanel.columns[3]
                    anchors.verticalCenter: parent.verticalCenter
                    value: Format.number(lapRow.modelData.avgSpeedKmh, 1)
                    unit: "km/h"
                }
                Rectangle {
                    x: 20
                    anchors.bottom: parent.bottom
                    width: parent.width - 40
                    height: 1
                    color: Theme.hairline
                    visible: lapRow.index < lapList.count - 1
                }
            }
        }
        Text {
            anchors {
                left: parent.left; right: parent.right; bottom: parent.bottom
                leftMargin: 22; rightMargin: 22; bottomMargin: 28
            }
            visible: sheet.laps.length <= 1
            text: "Un seul tour : pendant la sortie, le bouton Lap découpe la sortie en tours."
            wrapMode: Text.WordWrap
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold }
        }
    }
}
