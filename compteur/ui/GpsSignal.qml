import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Signal de chaque satellite, en dB-Hz : au-dessus de 30, il est bon
Panel {
    id: signal
    required property var view  // la page GPS : ses valeurs et son état
    scrolled: true
    height: 132

    Text {
        x: 22
        y: 14
        text: "SIGNAL"
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5 }
    }
    Text {
        anchors { right: parent.right; top: parent.top; rightMargin: 22 + signal.cutX; topMargin: 14 }
        visible: view.values.signalDb !== null && view.values.signalDb !== undefined
        text: "Moyen " + Format.number(view.values.signalDb) + " dB-Hz"
        color: Theme.lacquer
        font { family: Theme.sans; pixelSize: 20; weight: Font.DemiBold; features: ({ "tnum": 1 }) }
    }

    Item {
        id: bars
        x: 22
        y: 52
        width: signal.width - 44
        height: 44
        readonly property real full: 50  // dB-Hz en haut des barres
        readonly property real slot: width / Math.max(view.satellites.length, 12)
        readonly property real barWidth: Math.max(4, slot - 5)
        function bar(index, snr) {
            const h = Math.max(2, Math.min(1, snr / full) * height)
            const x0 = index * slot, s = Math.min(5, barWidth / 3)
            return [Qt.point(x0, height - h), Qt.point(x0 + barWidth - s, height - h),
                    Qt.point(x0 + barWidth, height), Qt.point(x0 + s, height), Qt.point(x0, height - h)]
        }
        readonly property var usedBars: view.satellites.map((sat, i) => sat.used ? bar(i, sat.snr) : null)
                                                       .filter(b => b !== null)
        readonly property var otherBars: view.satellites.map((sat, i) => sat.used ? null : bar(i, sat.snr))
                                                        .filter(b => b !== null)

        // Repère des 30 dB-Hz
        Rectangle {
            y: bars.height * (1 - 30 / bars.full)
            width: bars.width
            height: 1
            color: Theme.hairline
        }
        Text {
            anchors { right: parent.left; rightMargin: 3; verticalCenter: parent.top
                      verticalCenterOffset: bars.height * (1 - 30 / bars.full) }
            text: "30"
            color: Theme.ash
            opacity: 0.7
            font { family: Theme.numbers; pixelSize: 14; weight: Font.DemiBold }
        }
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: Theme.lacquer
                strokeColor: "transparent"
                PathMultiline { paths: bars.usedBars }
            }
            ShapePath {
                fillColor: Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.4)
                strokeColor: "transparent"
                PathMultiline { paths: bars.otherBars }
            }
        }
        Repeater {
            model: bars.slot >= 16 ? view.satellites : []
            delegate: Text {
                required property int index
                required property var modelData
                x: index * bars.slot + bars.barWidth / 2 - implicitWidth / 2
                y: bars.height + 5
                text: modelData.prn
                color: modelData.used ? Theme.lacquer : Theme.ash
                opacity: 0.85
                font { family: Theme.numbers; pixelSize: 14; weight: Font.DemiBold; features: ({ "tnum": 1 }) }
            }
        }
    }
    Text {
        anchors.centerIn: bars
        visible: view.satellites.length === 0
        text: view.present ? "Aucun satellite en vue" : "Pas de GPS sur le bus"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 20; weight: Font.DemiBold }
    }
}
