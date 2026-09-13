import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Page principale : la vitesse en grand, l'avancement sur le parcours, puis six mesures sur un panneau carbone.
// La couleur ne sert qu'à informer : pente, zone cardio, hors parcours.
Item {
    id: page
    required property var values

    readonly property bool paused: values.state === "paused" || values.autoPaused
    readonly property bool hasRoute: values.routeKm !== undefined
    readonly property bool offRoute: values.offRoute === true
    readonly property bool hasGrade: values.gradePct !== null && values.gradePct !== undefined

    // Vitesse, en grands chiffres penchés
    Item {
        id: hero
        width: parent.width
        height: 190

        Text {
            x: 24
            y: 10
            text: "Vitesse"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
        Text {
            id: speed
            x: (hero.width - implicitWidth - 10 - speedUnit.implicitWidth) / 2
            anchors { baseline: parent.top; baselineOffset: 166 }
            text: Format.number(page.values.speedKmh, 1)
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 172; weight: Font.Bold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            id: speedUnit
            x: speed.x + speed.implicitWidth + 10
            anchors.baseline: speed.baseline
            text: "km/h"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 20; weight: Font.DemiBold }
        }
    }

    // Avancement sur le parcours : des segments penchés qui se remplissent, et les kilomètres restants
    Item {
        id: progress
        x: 24
        y: hero.height
        width: parent.width - 48
        height: page.hasRoute ? 40 : 0
        visible: page.hasRoute

        Text {
            id: progressLabel
            anchors.verticalCenter: parent.verticalCenter
            text: page.offRoute ? "Hors parcours" : "Restant"
            color: page.offRoute ? Theme.warning : Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
        Segments {
            anchors {
                left: progressLabel.right; right: remaining.left; verticalCenter: parent.verticalCenter
                leftMargin: 14; rightMargin: 14
            }
            height: 10
            progress: page.values.routeProgress ?? 0
            color: page.offRoute ? Theme.warning : Theme.lacquer
        }
        Row {
            id: remaining
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            spacing: 5
            Text {
                id: remainingValue
                text: Format.number(page.values.routeRemainingKm, 1)
                color: Theme.lacquer
                font { family: Theme.numbers; pixelSize: 28; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
            }
            Text {
                anchors.baseline: remainingValue.baseline
                text: "km"
                color: Theme.ash
                font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
            }
        }
    }

    // Six mesures sur un seul panneau carbone, séparées par des filets
    Panel {
        id: panel
        x: 16
        y: progress.y + progress.height + 8
        width: parent.width - 32
        height: parent.height - y - 8
        readonly property real rowHeight: (height - 2) / 3
        // Colonne de droite : après le filet penché du milieu
        readonly property real rightX: width / 2 + Theme.lean * (rowHeight - 32) / 2 + 14

        Column {
            anchors.fill: parent

            Item {
                width: panel.width
                height: panel.rowHeight
                Metric {
                    x: 22
                    label: "Distance"
                    value: Format.number(page.values.distanceKm, 1)
                    unit: "km"
                }
                Divider {}
                Metric {
                    x: panel.rightX
                    label: "Moyenne"
                    value: Format.number(page.values.avgSpeedKmh, 1)
                    unit: "km/h"
                }
            }
            Separator {}
            Item {
                width: panel.width
                height: panel.rowHeight
                Metric {
                    x: 22
                    label: "Temps"
                    value: Format.duration(page.values.timerS)
                    dimmed: page.paused && (page.values.tick ?? 0) % 2 === 1  // clignote en pause
                }
                Divider {}
                Metric {
                    id: cardio
                    x: panel.rightX
                    label: "Cardio"
                    value: Format.number(page.values.heartRate)
                    unit: "bpm"
                }
                ZoneGauge {
                    x: cardio.x + cardio.labelWidth + 12
                    y: 21
                    zone: page.values.hrZone ?? 0
                }
            }
            Separator {}
            Item {
                width: panel.width
                height: panel.rowHeight
                Metric {
                    x: 22
                    label: "Dénivelé +"
                    value: Format.number(page.values.ascentM)
                    unit: "m"
                }
                Divider {}
                Metric {
                    id: grade
                    x: panel.rightX
                    label: "Pente"
                    value: Format.number(page.values.gradePct)
                    unit: "%"
                }
                GradeWedge {
                    x: grade.x + grade.valueEnd + 12
                    y: grade.valueBaseline - height
                    visible: page.hasGrade && Math.round(page.values.gradePct) !== 0
                    grade: page.values.gradePct ?? 0
                }
            }
        }
    }

    // Une mesure : libellé en cendre, valeur en chiffres penchés, unité
    component Metric: Item {
        id: metric
        property string label
        property string value
        property string unit
        property bool dimmed: false  // valeur estompée (chrono en pause, une seconde sur deux)
        readonly property real labelWidth: labelText.implicitWidth
        readonly property real valueEnd: unitText.x + unitText.implicitWidth
        readonly property real valueBaseline: valueText.y + valueText.baselineOffset
        height: parent.height

        Text {
            id: labelText
            y: 16
            text: metric.label
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
        Text {
            id: valueText
            anchors { baseline: parent.bottom; baselineOffset: -20 }
            text: metric.value
            color: Theme.lacquer
            opacity: metric.dimmed ? 0.3 : 1
            font { family: Theme.numbers; pixelSize: 50; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            id: unitText
            x: valueText.implicitWidth + 7
            anchors.baseline: valueText.baseline
            text: metric.unit
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 16; weight: Font.Medium }
        }
    }

    // Filet entre deux lignes de mesures
    component Separator: Rectangle {
        x: 20
        width: parent.width - 40
        height: 1
        color: Theme.hairline
    }

    // Filet penché comme le logo, entre les deux mesures d'une ligne
    component Divider: Shape {
        id: divider
        x: parent.width / 2
        y: 16
        height: parent.height - 32
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: Theme.hairline
            strokeWidth: 1
            fillColor: "transparent"
            startX: -Theme.lean * divider.height / 2; startY: 0
            PathLine { x: Theme.lean * divider.height / 2; y: divider.height }
        }
    }

    // Barre d'avancement : des segments penchés comme le logo, remplis à mesure qu'on avance
    component Segments: Shape {
        id: bar
        property real progress
        property color color
        readonly property int count: 20
        readonly property real gap: 3
        readonly property real slant: Theme.lean * height
        readonly property real segment: (width - (count - 1) * gap) / count
        readonly property int filled: Math.round(Math.max(0, Math.min(1, progress)) * count)

        // Contours des segments first à last (exclu)
        function outlines(first, last) {
            const list = []
            for (let i = first; i < last; i++) {
                const x = i * (segment + gap)
                list.push([Qt.point(x, 0), Qt.point(x + segment - slant, 0), Qt.point(x + segment, height),
                           Qt.point(x + slant, height), Qt.point(x, 0)])
            }
            return list
        }

        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: bar.color
            strokeColor: "transparent"
            PathMultiline { paths: bar.outlines(0, bar.filled) }
        }
        ShapePath {
            fillColor: Theme.carbonRaised
            strokeColor: "transparent"
            PathMultiline { paths: bar.outlines(bar.filled, bar.count) }
        }
    }
}
