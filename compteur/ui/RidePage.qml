import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Page principale : la vitesse en grand, l'avancement sur le parcours, puis quatre mesures sur un panneau carbone.
// La couleur ne sert qu'à informer : zone cardio, hors parcours.
Item {
    id: page
    required property var values

    readonly property bool paused: values.state === "paused" || values.autoPaused
    readonly property bool hasRoute: values.routeKm !== undefined
    readonly property bool offRoute: values.offRoute === true

    // Vitesse, en grands chiffres penchés
    Item {
        id: hero
        width: parent.width
        height: 184

        Text {
            x: 24
            y: 12
            text: "VITESSE"
            color: Theme.ash
            font { family: Theme.numbers; pixelSize: 26; weight: Font.DemiBold; letterSpacing: 1.5 }
        }
        Text {
            id: speed
            x: (hero.width - implicitWidth - 10 - speedUnit.implicitWidth) / 2
            anchors { baseline: parent.top; baselineOffset: 172 }
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
            font { family: Theme.sans; pixelSize: 28; weight: Font.DemiBold }
        }
    }

    // Avancement sur le parcours : des segments penchés qui se remplissent, et les kilomètres restants
    Item {
        id: progress
        x: 24
        y: hero.height
        width: parent.width - 48
        height: page.hasRoute ? 50 : 0
        visible: page.hasRoute

        Text {
            id: progressLabel
            anchors.verticalCenter: parent.verticalCenter
            text: page.offRoute ? "HORS PARCOURS" : "RESTANT"
            color: page.offRoute ? Theme.warning : Theme.ash
            font { family: Theme.numbers; pixelSize: 26; weight: Font.DemiBold; letterSpacing: 1.5 }
        }
        SlantedBar {
            anchors {
                left: progressLabel.right; right: remaining.left; verticalCenter: parent.verticalCenter
                leftMargin: 14; rightMargin: 14
            }
            height: 12
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
                font { family: Theme.numbers; pixelSize: 44; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
            }
            Text {
                anchors.baseline: remainingValue.baseline
                text: "km"
                color: Theme.ash
                font { family: Theme.sans; pixelSize: 24; weight: Font.DemiBold }
            }
        }
    }

    // Quatre mesures sur un seul panneau carbone, séparées par des filets
    Panel {
        id: panel
        x: 16
        y: progress.y + progress.height + 8
        width: parent.width - 32
        height: parent.height - y - 8
        readonly property real rowHeight: (height - 1) / 2
        // Colonne de droite : après le filet penché du milieu
        readonly property real rightX: width / 2 + Theme.lean * (rowHeight - 32) / 2 + 14

        Column {
            anchors.fill: parent

            Item {
                width: panel.width
                height: panel.rowHeight
                Metric {
                    x: 22
                    label: "DISTANCE"
                    value: Format.number(page.values.distanceKm, 1)
                    unit: "km"
                }
                Divider {}
                Metric {
                    id: cardio
                    x: panel.rightX
                    label: "CARDIO"
                    value: Format.number(page.values.heartRate)
                }
                ZoneGauge {
                    x: cardio.x + cardio.labelWidth + 10
                    y: 26
                    segmentWidth: 11
                    segmentHeight: 10
                    spacing: 2
                    zone: page.values.hrZone ?? 0
                }
            }
            Hairline {}
            Item {
                width: panel.width
                height: panel.rowHeight
                Metric {
                    x: 22
                    label: "TEMPS"
                    value: Format.duration(page.values.timerS)
                    splitSeconds: true
                    valueSize: 76
                    dimmed: page.paused && (page.values.tick ?? 0) % 2 === 1  // clignote en pause
                }
                Divider {}
                Metric {
                    x: panel.rightX
                    label: "ASCENSION"
                    value: Format.number(page.values.ascentM)
                    unit: "m"
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
        property bool splitSeconds: false  // chrono : secondes plus petites
        property int valueSize: 88
        // À partir de 4 chiffres (2345 m, 188,8 km), ou de 10 h au chrono, la valeur rapetisse pour rester dans sa colonne
        readonly property int fittedSize: metric.value.replace(/[^0-9]/g, "").length >= (splitSeconds ? 6 : 4)
                                          ? Math.round(valueSize * (splitSeconds ? 0.85 : 0.8)) : valueSize
        readonly property real labelWidth: labelText.implicitWidth
        readonly property real valueEnd: unitText.x + unitText.implicitWidth
        readonly property real valueBaseline: valueText.y + valueText.baselineOffset
        height: parent.height

        Text {
            id: labelText
            y: 18
            text: metric.label
            color: Theme.ash
            font { family: Theme.numbers; pixelSize: 28; weight: Font.DemiBold; letterSpacing: 1.5 }
        }
        Text {
            id: valueText
            anchors { baseline: parent.bottom; baselineOffset: -26 }
            text: metric.splitSeconds && metric.value.length > 3 ? metric.value.slice(0, -3) : metric.value
            color: Theme.lacquer
            opacity: metric.dimmed ? 0.3 : 1
            font { family: Theme.numbers; pixelSize: metric.fittedSize; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            id: unitText
            x: valueText.implicitWidth + (metric.splitSeconds ? 2 : 8)
            anchors.baseline: valueText.baseline
            text: metric.splitSeconds && metric.value.length > 3 ? metric.value.slice(-3) : metric.unit
            color: metric.splitSeconds ? Theme.lacquer : Theme.ash
            opacity: valueText.opacity
            font.family: metric.splitSeconds ? Theme.numbers : Theme.sans
            font.pixelSize: metric.splitSeconds ? metric.fittedSize / 2 : 26
            font.weight: Font.DemiBold
            font.italic: metric.splitSeconds
            font.features: ({ "tnum": 1 })
        }
    }


    // Filet penché comme le logo, entre les deux mesures d'une ligne
    component Divider: Shape {
        id: divider
        x: parent.width / 2
        y: 20
        height: parent.height - 40
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: Theme.hairline
            strokeWidth: 1
            fillColor: "transparent"
            startX: -Theme.lean * divider.height / 2; startY: 0
            PathLine { x: Theme.lean * divider.height / 2; y: divider.height }
        }
    }
}
