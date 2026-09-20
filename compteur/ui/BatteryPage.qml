import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Batterie, en direct : la charge et l'autonomie, la prévision (la charge depuis la mise en route, prolongée jusqu'à
// vide), puis le détail des mesures de la jauge et de l'alimentation du Pi. Ouverte depuis les Réglages ; elle sert
// surtout pendant les essais d'autonomie. Tout suit la mise à jour de chaque seconde, sans animation.
Item {
    id: page
    required property var battery  // BatteryModel
    signal back

    readonly property var values: battery.values
    readonly property string state: values.state ?? "absente"
    readonly property bool present: state !== "absente"
    readonly property real percent: values.percent ?? 0
    readonly property int tenths: Math.round(percent * 10)  // au dixième, en entier : pas d'erreur d'arrondi (60,3 × 10)
    readonly property bool low: values.low === true
    // La couleur informe : verte en charge ou pleine, rouge quand la batterie est faible, ambre sans jauge
    readonly property color stateColor: state === "charge" || state === "pleine" ? Theme.ok
        : state === "absente" ? Theme.warning : low ? Theme.danger : Theme.ash
    readonly property color fillColor: state === "charge" ? Theme.ok : low ? Theme.danger : Theme.lacquer
    readonly property string stateText: ({ charge: "En charge", pleine: "Pleine", decharge: "En décharge",
                                           absente: "Jauge absente" })[state] ?? ""

    // La courbe ne se relit que page à l'écran
    property var curve: []
    onVisibleChanged: if (visible) curve = battery.curve
    Connections {
        target: page.battery
        enabled: page.visible
        function onCurveChanged() { page.curve = page.battery.curve }
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.graphite
    }

    PageHeader {
        id: header
        title: "Batterie"
        onBack: page.back()
    }
    // D'où viennent les mesures : la jauge, ou la batterie simulée
    Text {
        anchors { right: parent.right; rightMargin: 26; verticalCenter: header.verticalCenter }
        text: page.values.source ?? ""
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 14; weight: Font.DemiBold; letterSpacing: 0.6 }
    }

    // Charge en grand, état et autonomie, puis la batterie en segments penchés
    Panel {
        id: hero
        x: 16
        y: header.height + 4
        width: parent.width - 32
        height: 172

        Text {
            x: 22
            y: 14
            text: "Charge"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
        Text {
            id: whole
            x: 18
            anchors { baseline: parent.top; baselineOffset: 114 }
            text: page.present ? Math.floor(page.tenths / 10) : "--"
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 100; weight: Font.Bold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            id: tenth
            x: whole.x + whole.implicitWidth + 2
            anchors.baseline: whole.baseline
            visible: page.present
            text: "," + page.tenths % 10
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 38; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            x: (page.present ? tenth.x + tenth.implicitWidth : whole.x + whole.implicitWidth) + 6
            anchors.baseline: whole.baseline
            text: "%"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 20; weight: Font.DemiBold }
        }

        SlantRule {
            x: hero.width * 0.56
            y: 20
            height: 96
        }

        // État, puis autonomie (en décharge) ou temps avant la charge complète
        Item {
            x: hero.width * 0.56 + 34
            y: 16
            width: hero.width - x - 18
            height: 110

            StateChip {
                text: page.stateText
                dot: page.stateColor
                charging: page.state === "charge"
            }
            Text {
                y: 44
                text: page.state === "charge" ? "Pleine dans" : "Autonomie estimée"
                color: Theme.ash
                font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
            }
            Text {
                anchors { baseline: parent.top; baselineOffset: 98 }
                text: Format.span(page.state === "charge" ? page.values.fullInS : page.values.autonomyS)
                color: Theme.lacquer
                font { family: Theme.numbers; pixelSize: 36; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
            }
        }

        // Dix cases de 10 %
        SlantedBar {
            x: 22
            y: 132
            width: hero.width - 44
            height: 18
            count: 10
            progress: page.percent / 100
            color: page.fillColor
        }
    }

    // Prévision : la charge mesurée depuis la mise en route, puis en tirets jusqu'à vide (ou pleine)
    Panel {
        id: forecast
        x: 16
        y: hero.y + hero.height + 10
        width: parent.width - 32
        height: 148
        readonly property rect box: Qt.rect(22, 48, width - 44, 58)
        readonly property real nowS: page.values.nowS ?? 0
        readonly property bool forecasting: page.values.forecastS !== null && page.values.forecastS !== undefined
        readonly property real spanS: Math.max(nowS + (forecasting ? page.values.forecastS : 0), 600)
        function toBox(s, pct) {
            return Qt.point(box.x + s / spanS * box.width, box.y + box.height * (1 - Math.max(0, Math.min(100, pct)) / 100))
        }
        readonly property point nowPoint: toBox(nowS, page.percent)
        readonly property point endPoint: toBox(nowS + (page.values.forecastS ?? 0), page.state === "charge" ? 100 : 0)
        // Mesuré : les points de la courbe (au plus 240), puis la lecture du moment
        readonly property var line: {
            if (!page.visible || !page.present)
                return []
            const points = page.curve
            const n = points.length
            const step = Math.max(1, Math.ceil(n / 240))
            const out = []
            for (let i = 0; i < n; i += step)
                out.push(toBox(points[i].x, points[i].y))
            out.push(nowPoint)
            return out
        }
        readonly property var area: line.length > 1
            ? line.concat([Qt.point(nowPoint.x, box.y + box.height), Qt.point(line[0].x, box.y + box.height)])
            : []
        readonly property string headline: !page.present ? ""
            : page.state === "pleine" ? "Batterie pleine"
            : forecasting ? (page.state === "charge" ? "Pleine vers " : "Vide vers ") + page.values.endClock
            : "Stable"

        Text {
            x: 22
            y: 14
            text: "Prévision"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
        Text {
            anchors { right: parent.right; top: parent.top; rightMargin: 22 + forecast.cutX; topMargin: 14 }
            text: forecast.headline
            color: Theme.lacquer
            font { family: Theme.sans; pixelSize: 15; weight: Font.DemiBold; features: ({ "tnum": 1 }) }
        }

        // Repères à 0, 50 et 100 %
        Repeater {
            model: 3
            delegate: Rectangle {
                required property int index
                x: forecast.box.x
                y: forecast.box.y + index * forecast.box.height / 2
                width: forecast.box.width
                height: 1
                color: Theme.hairline
            }
        }

        // Mesuré : aplat (moteur simple) et trait lissé, en laque
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.GeometryRenderer
            ShapePath {
                fillColor: Qt.rgba(Theme.lacquer.r, Theme.lacquer.g, Theme.lacquer.b, 0.16)
                strokeColor: "transparent"
                PathPolyline { path: forecast.area }
            }
        }
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Theme.lacquer
                strokeWidth: 2
                fillColor: "transparent"
                joinStyle: ShapePath.RoundJoin
                PathPolyline { path: forecast.line }
            }
        }
        // Prévu : en tirets, jusqu'au bout de la courbe
        Shape {
            anchors.fill: parent
            visible: page.present && forecast.forecasting
            ShapePath {
                strokeColor: page.state === "charge" ? Theme.ok : Theme.ash
                strokeWidth: 2
                strokeStyle: ShapePath.DashLine
                dashPattern: [2.5, 2]
                fillColor: "transparent"
                startX: forecast.nowPoint.x; startY: forecast.nowPoint.y
                PathLine { x: forecast.endPoint.x; y: forecast.endPoint.y }
            }
        }
        // Maintenant : un repère penché et la position sur la courbe
        SlantRule {
            visible: page.present
            x: forecast.nowPoint.x
            y: forecast.box.y - 6
            height: forecast.box.height + 12
            color: Qt.rgba(Theme.lacquer.r, Theme.lacquer.g, Theme.lacquer.b, 0.35)
        }
        Rectangle {
            visible: page.present
            x: forecast.nowPoint.x - width / 2
            y: forecast.nowPoint.y - height / 2
            width: 10
            height: 10
            radius: 5
            color: Theme.lacquer
            border { color: Theme.carbon; width: 2 }
        }

        // Heures : mise en route, et fin de la prévision (sinon, maintenant)
        Text {
            x: forecast.box.x
            y: forecast.box.y + forecast.box.height + 10
            text: page.present ? page.values.startClock : ""
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 13; weight: Font.Medium; features: ({ "tnum": 1 }) }
        }
        Text {
            anchors.right: parent.right
            anchors.rightMargin: parent.width - forecast.box.x - forecast.box.width
            y: forecast.box.y + forecast.box.height + 10
            text: !page.present ? "" : forecast.forecasting ? page.values.endClock : page.values.nowClock
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 13; weight: Font.Medium; features: ({ "tnum": 1 }) }
        }
    }

    // Détail des mesures, trois par ligne
    Panel {
        id: details
        x: 16
        y: forecast.y + forecast.height + 10
        width: parent.width - 32
        height: parent.height - y - 14
        readonly property real cellWidth: (width - 16) / 3
        readonly property real cellHeight: (height - 8) / 3
        readonly property string supplyText: page.values.undervoltage === true ? "Trop basse"
            : page.values.undervoltageSeen === true ? "Baisse vue"
            : page.values.undervoltage === false ? "Correcte" : "--"
        readonly property color supplyColor: page.values.undervoltage === true ? Theme.danger
            : page.values.undervoltageSeen === true ? Theme.warning : Theme.lacquer

        Repeater {
            model: 2
            delegate: Rectangle {
                required property int index
                x: 20
                y: 4 + (index + 1) * details.cellHeight
                width: details.width - 40
                height: 1
                color: Theme.hairline
            }
        }

        Grid {
            x: 8
            y: 4
            columns: 3

            Tile {
                label: "Tension"
                value: Format.number(page.values.voltage, 3)
                unit: "V"
            }
            Tile {
                label: "Variation"
                value: Format.signed(page.values.ratePctH, 1)
                unit: "%/h"
            }
            Tile {
                label: page.state === "charge" ? "Recharge" : "Consommation"
                value: Format.number(page.values.currentMa)
                unit: "mA"
                edge: false
            }
            Tile {
                label: "Reste"
                value: Format.number(page.values.remainingMah)
                unit: "mAh"
            }
            Tile {
                label: page.values.sinceS !== null && page.values.sinceS !== undefined
                       ? "Depuis " + Format.span(page.values.sinceS) : "Depuis le début"
                value: Format.signed(page.values.changePct, 1)
                unit: "%"
            }
            Tile {
                label: "Capacité"
                value: Format.number(page.values.capacityMah)
                unit: "mAh"
                edge: false
            }
            Tile {
                label: "Alimentation 5 V"
                value: details.supplyText
                valueColor: details.supplyColor
                numeric: false
            }
            Tile {
                label: "Processeur"
                value: Format.number(page.values.cpuTempC)
                unit: "°C"
            }
            Tile {
                label: "Jauge"
                value: page.values.hibernating === true ? "En veille" : page.values.hibernating === false ? "Active" : "--"
                numeric: false
                edge: false
            }
        }
    }

    component Tile: MeasureTile {
        width: details.cellWidth
        height: details.cellHeight
    }
}
