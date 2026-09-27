import QtQuick
import "Format.js" as Format

// Détail des mesures, trois par ligne
Panel {
    id: details
    required property var view  // la page Batterie : ses valeurs et son état
    x: 16
    width: parent.width - 32
    height: parent.height - y - 8
    readonly property real cellWidth: (width - 16) / 3
    readonly property real cellHeight: (height - 8) / 3
    readonly property string supplyText: view.values.undervoltage === true ? "Trop basse"
        : view.values.undervoltageSeen === true ? "Baisse vue"
        : view.values.undervoltage === false ? "Correcte" : "--"
    readonly property color supplyColor: view.values.undervoltage === true ? Theme.danger
        : view.values.undervoltageSeen === true ? Theme.warning : Theme.lacquer

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
            value: Format.number(view.values.voltage, 3)
            unit: "V"
        }
        Tile {
            label: "Variation"
            value: Format.signed(view.values.ratePctH, 1)
            unit: "%/h"
        }
        Tile {
            label: view.state === "charge" ? "Recharge" : "Courant"
            value: Format.number(view.values.currentMa)
            unit: "mA"
            edge: false
        }
        Tile {
            label: "Reste"
            value: Format.number(view.values.remainingMah)
            unit: "mAh"
        }
        Tile {
            label: view.values.sinceS !== null && view.values.sinceS !== undefined
                   ? "Depuis " + Format.span(view.values.sinceS) : "Depuis le début"
            value: Format.signed(view.values.changePct, 1)
            unit: "%"
        }
        Tile {
            label: "Capacité"
            value: Format.number(view.values.capacityMah)
            unit: "mAh"
            edge: false
        }
        Tile {
            label: "Alim. 5 V"
            value: details.supplyText
            valueColor: details.supplyColor
            numeric: false
        }
        Tile {
            label: "Processeur"
            value: Format.number(view.values.cpuTempC)
            unit: "°C"
        }
        Tile {
            label: "Jauge"
            value: view.values.hibernating === true ? "En veille" : view.values.hibernating === false ? "Active" : "--"
            numeric: false
            edge: false
        }
    }

    component Tile: MeasureTile {
        width: details.cellWidth
        height: details.cellHeight
    }
}
