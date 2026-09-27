import QtQuick
import QtQuick.Shapes

// Démarrer : en laque ; en attente du signal GPS, un anneau tourne
Panel {
    id: startButton
    property real entry: 1  // 0 → 1 : arrivée, dans l'oblique du logo
    property bool armed: false  // départ demandé, en attente du signal GPS
    signal tapped
    height: 68
    color: tap.pressed ? Qt.darker(Theme.lacquer, 1.15) : Theme.lacquer
    woven: false
    outline: "transparent"
    opacity: entry
    scale: tap.pressed ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: 120 } }
    transform: Translate { x: (1 - startButton.entry) * 14 * Theme.lean; y: (1 - startButton.entry) * 14 }

    Row {
        anchors.centerIn: parent
        spacing: 14

        Item {
            width: 20
            height: 20
            anchors.verticalCenter: parent.verticalCenter

            // Triangle « lecture »
            Shape {
                x: 2
                width: 17
                height: 20
                visible: !startButton.armed
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    fillColor: Theme.graphite
                    strokeColor: "transparent"
                    startX: 0; startY: 0
                    PathLine { x: 17; y: 10 }
                    PathLine { x: 0; y: 20 }
                    PathLine { x: 0; y: 0 }
                }
            }
            // Anneau d'attente du signal GPS
            Shape {
                anchors.fill: parent
                visible: startButton.armed
                preferredRendererType: Shape.CurveRenderer
                RotationAnimation on rotation {
                    running: startButton.armed
                    from: 0
                    to: 360
                    duration: 900
                    loops: Animation.Infinite
                }
                ShapePath {
                    strokeColor: Theme.graphite
                    strokeWidth: 3
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    PathAngleArc { centerX: 10; centerY: 10; radiusX: 8; radiusY: 8; startAngle: 0; sweepAngle: 270 }
                }
            }
        }
        Text {
            text: startButton.armed ? "Départ au signal GPS" : "Démarrer"
            color: Theme.graphite
            font { family: Theme.sans; pixelSize: 30; weight: Font.DemiBold }
        }
    }

    TapHandler {
        id: tap
        onTapped: startButton.tapped()
    }
}
