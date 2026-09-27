import QtQuick
import "Format.js" as Format

// Détail des mesures, trois par ligne
Panel {
    id: details
    required property var view  // la page GPS : ses valeurs et son état
    scrolled: true
    height: 5 * cellHeight + 8
    readonly property real cellWidth: (width - 16) / 3
    readonly property real cellHeight: 66

    Repeater {
        model: 4
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
            label: "Latitude"
            value: Format.number(view.values.lat === undefined || view.values.lat === null ? null
                                 : Math.abs(view.values.lat), 5)
            unit: view.values.lat < 0 ? "° S" : "° N"
        }
        Tile {
            label: "Longitude"
            value: Format.number(view.values.lon === undefined || view.values.lon === null ? null
                                 : Math.abs(view.values.lon), 5)
            unit: view.values.lon < 0 ? "° O" : "° E"
        }
        Tile {
            label: "Altitude"
            value: Format.number(view.values.altitudeM)
            unit: "m"
            edge: false
        }
        Tile {
            label: "Vitesse"
            value: Format.number(view.values.speedKmh, 1)
            unit: "km/h"
        }
        Tile {
            label: "Cap"
            value: Format.number(view.values.headingDeg)
            unit: "°"
        }
        Tile {
            label: "Correction"
            value: !view.located ? "--" : view.values.sbas ? "SBAS" : "Aucune"
            numeric: false
            edge: false
        }
        Tile {
            label: "HDOP"
            value: Format.number(view.values.hdop, 1)
        }
        Tile {
            label: "PDOP"
            value: Format.number(view.values.pdop, 1)
        }
        Tile {
            label: "VDOP"
            value: Format.number(view.values.vdop, 1)
            edge: false
        }
        Tile {
            label: "Heure UTC"
            value: view.values.utcTime || "--"
        }
        Tile {
            label: "Horloge Pi"
            value: Format.signed(view.values.clockOffsetS)
            unit: "s"
        }
        Tile {
            readonly property var seconds: view.values.firstFixS
            label: "1re pos."
            value: seconds === null || seconds === undefined ? "--"
                   : seconds < 60 ? Format.number(seconds) : Format.span(seconds)
            unit: seconds < 60 ? "s" : ""
            edge: false
        }
        Tile {
            label: "Âge pos."
            value: Format.number(view.values.fixAgeS)
            unit: "s"
        }
        Tile {
            label: "Date UTC"
            value: view.values.utcDate ? Format.dayMonth(view.values.utcDate) : "--"
            numeric: false
        }
        Tile {
            label: "Erreurs"
            value: Format.number(view.values.errors)
            edge: false
        }
    }

    component Tile: MeasureTile {
        width: details.cellWidth
        height: details.cellHeight
        valueSize: 28
        wordSize: 20
    }
}
