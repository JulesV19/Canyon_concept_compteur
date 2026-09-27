import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Fréquence cardiaque et zone, en grand
Item {
    id: top
    required property var view  // la page cardio : courbe, zones et mesures
    width: parent.width
    height: 140

    HeroFigure {
        id: heartRate
        x: 24
        label: "CARDIO"
        value: Format.number(view.values.heartRate)
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
        text: view.zone > 0 ? "ZONE " + view.zone : "ZONE"
        color: view.zoneColor
        font { family: Theme.numbers; pixelSize: 26; weight: Font.DemiBold; letterSpacing: 1.5 }
    }
    ZoneGauge {
        x: top.width / 2 + 38
        y: 56
        zone: view.zone
        segmentWidth: 28
        segmentHeight: 16
        spacing: 4
    }
    Text {
        x: top.width / 2 + 38
        anchors { baseline: parent.top; baselineOffset: heartRate.valueBaseline }
        text: view.zone > 0 ? view.zoneNames[view.zone - 1] : "--"
        color: Theme.lacquer
        font { family: Theme.sans; pixelSize: 28; weight: Font.DemiBold }
    }
}
