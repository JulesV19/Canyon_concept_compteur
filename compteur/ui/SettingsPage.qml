import QtQuick
import QtQuick.Shapes
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
                Label {
                    id: maxHrLabel
                    text: "FC max"
                }
                Hint {
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
                        font { family: Theme.numbers; pixelSize: 40; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                    }
                    StepButton {
                        glyph: "+"
                        onStep: page.settings.preview("maxHr", page.values.maxHr + 1)
                        onDone: page.settings.set("maxHr", page.values.maxHr)
                    }
                }

                // Zones cardio : cinq segments penchés aux couleurs des zones, et leurs seuils en bpm
                Item {
                    id: zones
                    x: 24
                    y: 100
                    width: parent.width - 48
                    height: 40
                    readonly property real gap: 4
                    readonly property real segment: (width - 4 * gap) / 5

                    Repeater {
                        model: 5
                        delegate: Shape {
                            id: zone
                            required property int index
                            x: index * (zones.segment + zones.gap)
                            width: zones.segment
                            height: 8
                            preferredRendererType: Shape.CurveRenderer
                            ShapePath {
                                fillColor: Theme.zones[zone.index]
                                strokeColor: "transparent"
                                startX: 0; startY: 0
                                PathLine { x: zone.width - 4; y: 0 }
                                PathLine { x: zone.width; y: zone.height }
                                PathLine { x: 4; y: zone.height }
                                PathLine { x: 0; y: 0 }
                            }
                        }
                    }
                    Repeater {
                        model: page.values.zoneBounds
                        delegate: Text {
                            required property int index
                            required property var modelData
                            x: (index + 1) * (zones.segment + zones.gap) - zones.gap / 2 - width / 2
                            y: 16
                            text: modelData
                            color: Theme.ash
                            font { family: Theme.numbers; pixelSize: 17; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                        }
                    }
                }
            }

            Separator {}

            // Auto-pause : tout le rang bascule l'interrupteur
            Item {
                id: autoPauseRow
                width: panel.width
                height: 100

                FocusMark { visible: page.keyboard && page.focusRow === 1 }
                Label {
                    id: autoPauseLabel
                    text: "Auto-pause"
                }
                Hint {
                    anchors.top: autoPauseLabel.bottom
                    text: "Le chrono s'arrête sous 3 km/h"
                }
                Toggle {
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

            Separator {}

            // Luminosité : glisser le curseur (enregistrée au lâcher)
            Item {
                id: brightnessRow
                width: panel.width
                height: 128

                FocusMark { visible: page.keyboard && page.focusRow === 2 }
                Label {
                    text: "Luminosité"
                }
                Row {
                    anchors { right: parent.right; rightMargin: 24; top: parent.top; topMargin: 16 }
                    spacing: 4
                    Text {
                        id: brightnessValue
                        text: page.values.brightness
                        color: Theme.lacquer
                        font { family: Theme.numbers; pixelSize: 34; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                    }
                    Text {
                        anchors.baseline: brightnessValue.baseline
                        text: "%"
                        color: Theme.ash
                        font { family: Theme.sans; pixelSize: 16; weight: Font.Medium }
                    }
                }
                Track {
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
        text: "La FC max et l'auto-pause s'appliquent au prochain départ."
        color: Theme.ash
        wrapMode: Text.WordWrap
        font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
    }

    // Batterie et GPS : chacun ouvre son écran, avec son état du moment en petit
    Panel {
        id: sensors
        x: 16
        y: parent.height - height - 18
        width: parent.width - 32
        height: 84

        Row {
            anchors.fill: parent

            SensorLink {
                readonly property var values: page.battery.values
                row: 3
                label: "Batterie"
                hint: values.state === "absente" ? "Jauge absente"
                    : Format.number(values.percent) + " % · "
                      + ({ charge: "en charge", pleine: "pleine", decharge: "en décharge" })[values.state]
            }
            SensorLink {
                readonly property var values: page.gps.values
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

    // Une case de Batterie et GPS : libellé, état en dessous, chevron à droite
    component SensorLink: Item {
        id: link
        property int row
        property string label
        property string hint
        width: sensors.width / 2
        height: sensors.height

        Rectangle {
            anchors.fill: parent
            color: Theme.carbonRaised
            visible: linkTap.pressed
        }
        FocusMark { visible: page.keyboard && page.focusRow === link.row }
        Label {
            id: linkLabel
            y: 16
            text: link.label
        }
        Hint {
            anchors.top: linkLabel.bottom
            width: link.width - 60
            elide: Text.ElideRight
            text: link.hint
        }
        Shape {
            x: link.width - 22 - width
            anchors.verticalCenter: parent.verticalCenter
            width: 11
            height: 20
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Theme.ash
                strokeWidth: 2.5
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                startX: 1; startY: 1
                PathLine { x: 10; y: 10 }
                PathLine { x: 1; y: 19 }
            }
        }
        TapHandler {
            id: linkTap
            onTapped: {
                page.keyboard = false
                page.focusRow = link.row
                page.open(link.row)
            }
        }
    }

    component Label: Text {
        x: 24
        y: 22
        color: Theme.lacquer
        font { family: Theme.sans; pixelSize: 21; weight: Font.DemiBold }
    }

    component Hint: Text {
        x: 24
        anchors.topMargin: 2
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
    }

    component Separator: Rectangle {
        x: 20
        width: parent.width - 40
        height: 1
        color: Theme.hairline
    }

    // Ligne choisie au clavier : un trait laque sur le bord gauche
    component FocusMark: Rectangle {
        x: 0
        y: 14
        width: 3
        height: parent.height - 28
        color: Theme.lacquer
    }

    // Bouton − ou + : un appui change d'un cran ; maintenu, il défile (enregistré au lâcher)
    component StepButton: Panel {
        id: stepButton
        property string glyph
        signal step
        signal done
        width: 52
        height: 52
        cut: 12
        woven: false
        ground: Theme.carbon
        color: press.pressed ? Theme.ash : Theme.carbonRaised

        Text {
            anchors.centerIn: parent
            text: stepButton.glyph
            color: press.pressed ? Theme.graphite : Theme.lacquer
            font { family: Theme.sans; pixelSize: 30; weight: Font.DemiBold }
        }
        TapHandler {
            id: press
            onPressedChanged: {
                if (pressed) {
                    stepButton.step()
                    repeat.interval = 450
                    repeat.start()
                } else {
                    repeat.stop()
                    stepButton.done()
                }
            }
        }
        Timer {
            id: repeat
            repeat: true
            onTriggered: {
                stepButton.step()
                interval = 70
            }
        }
    }

    // Interrupteur penché comme le logo : laque quand il est activé
    component Toggle: Item {
        id: toggle
        property bool checked
        width: 66
        height: 32
        readonly property real slant: Theme.lean * height

        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: toggle.checked ? Theme.lacquer : Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.22)
                strokeColor: "transparent"
                startX: 0; startY: 0
                PathLine { x: toggle.width - toggle.slant; y: 0 }
                PathLine { x: toggle.width; y: toggle.height }
                PathLine { x: toggle.slant; y: toggle.height }
                PathLine { x: 0; y: 0 }
            }
        }
        Shape {
            id: knob
            y: 4
            width: 26
            height: toggle.height - 8
            x: toggle.checked ? toggle.width - width - 8 : 8
            Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: toggle.checked ? Theme.graphite : Theme.ash
                strokeColor: "transparent"
                startX: 0; startY: 0
                PathLine { x: knob.width - Theme.lean * knob.height; y: 0 }
                PathLine { x: knob.width; y: knob.height }
                PathLine { x: Theme.lean * knob.height; y: knob.height }
                PathLine { x: 0; y: 0 }
            }
        }
    }

    // Curseur de 10 à 100 %, par pas de 5
    component Track: Item {
        id: track
        property int value
        readonly property real fraction: (value - 10) / 90
        signal moved(int value)
        signal released(int value)
        function valueAt(x) {
            return Math.round((10 + 90 * Math.max(0, Math.min(1, x / width))) / 5) * 5
        }

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width
            height: 6
            color: Theme.carbonRaised
        }
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: track.fraction * parent.width
            height: 6
            color: Theme.lacquer
        }
        // Poignée penchée
        Shape {
            id: handle
            x: track.fraction * track.width - width / 2
            anchors.verticalCenter: parent.verticalCenter
            width: 18
            height: 30
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: Theme.lacquer
                strokeColor: Theme.carbon
                strokeWidth: 2
                startX: 0; startY: 0
                PathLine { x: handle.width - Theme.lean * handle.height / 2; y: 0 }
                PathLine { x: handle.width; y: handle.height }
                PathLine { x: Theme.lean * handle.height / 2; y: handle.height }
                PathLine { x: 0; y: 0 }
            }
        }
        MouseArea {
            anchors.fill: parent
            preventStealing: true
            onPressed: mouse => track.moved(track.valueAt(mouse.x))
            onPositionChanged: mouse => track.moved(track.valueAt(mouse.x))
            onReleased: mouse => track.released(track.valueAt(mouse.x))
        }
    }
}
