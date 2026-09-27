import QtQuick
import "Format.js" as Format

// Réglages : FC max (et les zones cardio qui en découlent), auto-pause, luminosité de l'écran, puis les écrans Batterie
// et GPS. Chaque changement est enregistré aussitôt. Au clavier (plus tard aux boutons) : ↑ ↓ pour choisir, ← → pour
// régler (→ ou Entrée ouvre Batterie ou GPS).
Item {
    id: page
    required property var settings  // SettingsModel
    required property var battery   // BatteryModel : sa charge, sur la case Batterie
    required property var gps       // GpsModel : son état, sur la case GPS
    signal back
    signal batteryRequested
    signal gpsRequested

    readonly property var values: settings.values
    property int focusRow: 0        // ligne choisie au clavier
    property bool keyboard: false   // la ligne choisie n'est soulignée qu'au clavier

    function moveFocus(delta) {
        keyboard = true
        focusRow = (focusRow + delta + 5) % 5
    }
    function open(row) {
        if (row === 3)
            batteryRequested()
        else
            gpsRequested()
    }
    function adjust(delta) {
        keyboard = true
        if (focusRow >= 3) {
            if (delta > 0)
                open(focusRow)
        } else if (focusRow === 0)
            settings.set("maxHr", values.maxHr + delta)
        else if (focusRow === 1)
            settings.set("autoPause", delta > 0)
        else
            settings.set("brightness", values.brightness + 5 * delta)
    }
    function activate() {
        keyboard = true
        if (focusRow === 1)
            settings.set("autoPause", !values.autoPause)
        else if (focusRow >= 3)
            open(focusRow)
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.graphite
    }

    // En-tête : retour au menu
    PageHeader {
        id: header
        title: "Réglages"
        onBack: page.back()
    }

    Panel {
        id: panel
        x: 16
        y: header.height + 4
        width: parent.width - 32
        height: maxHrRow.height + autoPauseRow.height + brightnessRow.height

        Column {
            anchors.fill: parent

            // FC max, avec les zones cardio qui en découlent
            Item {
                id: maxHrRow
                width: panel.width
                height: 156

                FocusMark { visible: page.keyboard && page.focusRow === 0 }
                RowLabel {
                    id: maxHrLabel
                    text: "FC max"
                }
                RowHint {
                    anchors.top: maxHrLabel.bottom
                    text: "Pour les zones cardio"
                }
                Row {
                    anchors { right: parent.right; rightMargin: 24; top: parent.top; topMargin: 16 }
                    spacing: 10

                    StepButton {
                        glyph: "−"
                        onStep: page.settings.preview("maxHr", page.values.maxHr - 1)
                        onDone: page.settings.set("maxHr", page.values.maxHr)
                    }
                    Text {
                        width: 72
                        anchors.verticalCenter: parent.verticalCenter
                        horizontalAlignment: Text.AlignHCenter
                        text: page.values.maxHr
                        color: Theme.lacquer
                        font { family: Theme.numbers; pixelSize: 46; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                    }
                    StepButton {
                        glyph: "+"
                        onStep: page.settings.preview("maxHr", page.values.maxHr + 1)
                        onDone: page.settings.set("maxHr", page.values.maxHr)
                    }
                }

                ZoneBounds {
                    x: 24
                    y: 100
                    width: parent.width - 48
                    height: 40
                    bounds: page.values.zoneBounds
                }
            }

            Hairline {}

            // Auto-pause : tout le rang bascule l'interrupteur
            Item {
                id: autoPauseRow
                width: panel.width
                height: 90

                FocusMark { visible: page.keyboard && page.focusRow === 1 }
                RowLabel {
                    id: autoPauseLabel
                    text: "Auto-pause"
                }
                RowHint {
                    anchors.top: autoPauseLabel.bottom
                    text: "Le chrono s'arrête sous 3 km/h"
                }
                SlantToggle {
                    anchors { right: parent.right; rightMargin: 24; verticalCenter: parent.verticalCenter }
                    checked: page.values.autoPause
                }
                TapHandler {
                    onTapped: {
                        page.keyboard = false
                        page.focusRow = 1
                        page.settings.set("autoPause", !page.values.autoPause)
                    }
                }
            }

            Hairline {}

            // Luminosité : glisser le curseur (enregistrée au lâcher)
            Item {
                id: brightnessRow
                width: panel.width
                height: 120

                FocusMark { visible: page.keyboard && page.focusRow === 2 }
                RowLabel {
                    text: "Luminosité"
                }
                Row {
                    anchors { right: parent.right; rightMargin: 24; top: parent.top; topMargin: 16 }
                    spacing: 4
                    Text {
                        id: brightnessValue
                        text: page.values.brightness
                        color: Theme.lacquer
                        font { family: Theme.numbers; pixelSize: 42; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                    }
                    Text {
                        anchors.baseline: brightnessValue.baseline
                        text: "%"
                        color: Theme.ash
                        font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
                    }
                }
                SlantSlider {
                    x: 24
                    y: 68
                    width: parent.width - 48
                    height: 40
                    value: page.values.brightness
                    onMoved: value => page.settings.preview("brightness", value)
                    onReleased: value => page.settings.set("brightness", value)
                }
            }
        }
    }

    Text {
        anchors { left: panel.left; right: panel.right; top: panel.bottom; topMargin: 14; leftMargin: 8; rightMargin: 8 }
        text: "FC max et auto-pause : au prochain départ."
        color: Theme.ash
        wrapMode: Text.WordWrap
        font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold }
    }

    // Batterie et GPS : chacun ouvre son écran, avec son état du moment en petit
    Panel {
        id: sensors
        x: 16
        y: parent.height - height - 8
        width: parent.width - 32
        height: 88

        Row {
            anchors.fill: parent

            SensorLink {
                readonly property var values: page.battery.values
                view: page
                width: sensors.width / 2
                height: sensors.height
                row: 3
                label: "Batterie"
                hint: values.state === "absente" ? "Jauge absente"
                    : Format.number(values.percent) + " % · "
                      + ({ charge: "en charge", pleine: "pleine", decharge: "en décharge" })[values.state]
            }
            SensorLink {
                readonly property var values: page.gps.values
                view: page
                width: sensors.width / 2
                height: sensors.height
                row: 4
                label: "GPS"
                hint: values.state === "absent" ? "GPS absent" : values.state === "recherche" ? "Recherche"
                    : values.used + " sat. · " + (values.state === "3d" ? "3D" : "2D")
            }
        }
        SlantRule {
            x: sensors.width / 2
            y: 16
            height: sensors.height - 32
        }
    }
}
