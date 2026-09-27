import QtQuick
import "Format.js" as Format

// Encadré du bas de la page segment : en cours, le profil et les mesures ; à l'arrivée, le résultat
Panel {
    id: panel
    required property var view  // la page segment : le segment et les mesures
    x: 16
    y: 286
    width: parent.width - 32
    height: parent.height - y - 8

    // En cours : profil et pente, chrono (ou moyenne sans record), vitesse, cardio, KOM
    Item {
        anchors.fill: parent
        visible: !view.finished

        Text {
            x: 22
            y: 14
            text: "PROFIL"
            color: Theme.ash
            font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5 }
        }
        Row {
            anchors { right: parent.right; top: parent.top; rightMargin: 22 + panel.cutX; topMargin: 12 }
            spacing: 5

            Text {
                id: gradeLabel
                rightPadding: 3
                text: "PENTE"
                color: Theme.ash
                font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5 }
            }
            Text {
                anchors.baseline: gradeLabel.baseline
                text: Format.number(view.values.gradePct)
                color: Theme.lacquer
                font { family: Theme.numbers; pixelSize: 32; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
            }
            Text {
                anchors.baseline: gradeLabel.baseline
                rightPadding: 5
                text: "%"
                color: Theme.ash
                font { family: Theme.sans; pixelSize: 20; weight: Font.DemiBold }
            }
            GradeWedge {
                anchors.bottom: gradeLabel.baseline
                visible: view.values.gradePct !== null && view.values.gradePct !== undefined
                         && Math.round(view.values.gradePct) !== 0
                grade: view.values.gradePct ?? 0
            }
        }
        SegmentProfile {
            x: 22
            y: 52
            width: parent.width - 44
            height: 62
            points: view.ride.segmentProfile
            doneKm: view.profileKm
        }
        Hairline { y: 120 }
        SegmentFigure {
            x: 22
            y: 121
            label: view.hasRecord ? "CHRONO" : "MOYENNE"
            value: view.hasRecord ? Format.clock(view.seg.elapsedS) : Format.number(view.seg.avgSpeedKmh, 1)
            unit: view.hasRecord ? "" : "km/h"
        }
        SegmentFigure {
            x: 162
            y: 121
            label: "VITESSE"
            value: Format.number(view.values.speedKmh, 1)
            unit: "km/h"
        }
        SegmentFigure {
            id: cardio
            x: 306
            y: 121
            label: "CARDIO"
            value: Format.number(view.values.heartRate)
            unit: "bpm"
        }
        ZoneGauge {
            x: cardio.x + cardio.labelWidth + 10
            y: 121 + 20
            segmentWidth: 10
            segmentHeight: 10
            spacing: 2
            zone: view.values.hrZone ?? 0
        }
        Hairline { y: 214 }
        SegmentKomRow {
            y: 215
            seg: view.seg
        }
    }

    // Arrivée : moyenne et cardio, KOM, profil du segment fait
    Item {
        anchors.fill: parent
        visible: view.finished

        SegmentFigure {
            x: 22
            label: "MOYENNE"
            value: Format.number(view.seg.avgSpeedKmh, 1)
            unit: "km/h"
        }
        SegmentFigure {
            x: 162
            label: "CARDIO MOY."
            value: Format.number(view.seg.avgHeartRate)
            unit: "bpm"
        }
        SegmentFigure {
            x: 306
            label: "CARDIO MAX"
            value: Format.number(view.seg.maxHeartRate)
            unit: "bpm"
        }
        Hairline { y: 94 }
        SegmentKomRow {
            y: 95
            seg: view.seg
        }
        Hairline { y: 157 }
        Text {
            x: 22
            y: 172
            text: "PROFIL"
            color: Theme.ash
            font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5 }
        }
        SegmentProfile {
            x: 22
            y: 206
            width: parent.width - 44
            height: 64
            points: view.ride.segmentProfile
            doneKm: view.seg.lengthKm ?? 0
        }
    }
}
