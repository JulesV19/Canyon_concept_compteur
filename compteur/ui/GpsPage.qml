import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// GPS, en direct : l'état de la réception et la précision, le ciel (où sont les satellites, et lesquels servent), le
// signal de chacun, puis le détail : position, précision, heure, liaison. Ouverte depuis les Réglages ; elle sert surtout
// pendant les essais (placement de l'antenne, temps jusqu'à la première position). Plus haute que l'écran : elle défile
// au doigt, ou avec ↑ ↓. Tout suit la mise à jour de chaque seconde ; le ciel, celle du GPS (toutes les 5 s).
Item {
    id: page
    required property var gps  // GpsModel
    signal back

    readonly property var values: gps.values
    readonly property string state: values.state ?? "absent"
    readonly property bool present: state !== "absent"
    readonly property bool located: state === "2d" || state === "3d"
    // La couleur informe : verte en 3D, ambre en recherche ou en 2D (sans altitude), rouge sans GPS
    readonly property color stateColor: state === "3d" ? Theme.ok : state === "absent" ? Theme.danger : Theme.warning
    readonly property string stateText: ({ absent: "GPS absent", recherche: "Recherche", "2d": "Position 2D",
                                           "3d": "Position 3D" })[state] ?? ""

    // Le ciel ne se relit que page à l'écran
    property var satellites: []
    onVisibleChanged: if (visible) satellites = gps.satellites
    Connections {
        target: page.gps
        enabled: page.visible
        function onSatellitesChanged() { page.satellites = page.gps.satellites }
    }

    // À l'ouverture : en haut de la page
    function replay() {
        flick.contentY = 0
    }
    // ↑ ↓ : fait défiler la page
    function moveFocus(delta) {
        flick.contentY = Math.max(0, Math.min(flick.contentHeight - flick.height, flick.contentY + delta * 160))
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.graphite
    }

    PageHeader {
        id: header
        title: "GPS"
        onBack: page.back()
    }
    // D'où viennent les mesures : le GPS, ou le GPS simulé
    Text {
        anchors { right: parent.right; rightMargin: 26; verticalCenter: header.verticalCenter }
        text: page.values.source ?? ""
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 14; weight: Font.DemiBold; letterSpacing: 0.6 }
    }

    Flickable {
        id: flick
        objectName: "gpsScroll"  // pour les essais
        anchors { top: header.bottom; topMargin: 4; left: parent.left; right: parent.right; bottom: parent.bottom }
        contentHeight: column.height + 16
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Column {
            id: column
            x: 16
            width: flick.width - 32
            spacing: 10

            // Satellites utilisés en grand, état et précision
            Panel {
                id: hero
                width: column.width
                height: 120

                Text {
                    x: 22
                    y: 14
                    text: "Satellites utilisés"
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
                }
                Text {
                    id: used
                    x: 18
                    anchors { baseline: parent.top; baselineOffset: 102 }
                    text: page.present ? page.values.used : "--"
                    color: Theme.lacquer
                    font { family: Theme.numbers; pixelSize: 84; weight: Font.Bold; italic: true; features: ({ "tnum": 1 }) }
                }
                Text {
                    x: used.x + used.implicitWidth + 10
                    anchors.baseline: used.baseline
                    visible: page.present
                    text: "sur " + page.values.inView + " en vue"
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 17; weight: Font.DemiBold }
                }

                SlantRule {
                    x: hero.width * 0.5
                    y: 20
                    height: 84
                }

                // État, puis précision estimée
                Item {
                    x: hero.width * 0.5 + 34
                    y: 16
                    width: hero.width - x - 18
                    height: 96

                    StateChip {
                        text: page.stateText
                        dot: page.stateColor
                    }
                    Text {
                        y: 42
                        text: "Précision estimée"
                        color: Theme.ash
                        font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
                    }
                    Text {
                        id: accuracy
                        anchors { baseline: parent.top; baselineOffset: 88 }
                        text: page.located ? "≈ " + Format.number(page.values.accuracyM) : "--"
                        color: Theme.lacquer
                        font { family: Theme.numbers; pixelSize: 34; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                    }
                    Text {
                        x: accuracy.implicitWidth + 5
                        anchors.baseline: accuracy.baseline
                        visible: page.located
                        text: "m"
                        color: Theme.ash
                        font { family: Theme.sans; pixelSize: 15; weight: Font.DemiBold }
                    }
                }
            }

            // Le ciel vu d'en haut : l'horizon, 30° et 60° d'élévation, le zénith au centre, le nord en haut
            Panel {
                id: sky
                width: column.width
                height: 236

                Text {
                    x: 22
                    y: 14
                    text: "Ciel"
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
                }

                Item {
                    id: plot
                    x: 22
                    y: 26
                    width: 180
                    height: 180
                    readonly property real radius: 76
                    readonly property real cx: width / 2
                    readonly property real cy: height / 2 + 2
                    function place(sat) {
                        const r = radius * (90 - Math.max(0, Math.min(90, sat.elevation))) / 90
                        const a = sat.azimuth * Math.PI / 180
                        return Qt.point(cx + r * Math.sin(a), cy - r * Math.cos(a))
                    }
                    // Un satellite : une petite case penchée comme le logo
                    function mark(p) {
                        const w = 12, h = 8, s = Theme.lean * h, x0 = p.x - w / 2, y0 = p.y - h / 2
                        return [Qt.point(x0, y0), Qt.point(x0 + w - s, y0), Qt.point(x0 + w, y0 + h),
                                Qt.point(x0 + s, y0 + h), Qt.point(x0, y0)]
                    }
                    readonly property var placed: page.satellites
                        .filter(sat => sat.elevation !== undefined && sat.elevation !== null
                                       && sat.azimuth !== undefined && sat.azimuth !== null)
                        .map(sat => ({ sat: sat, at: place(sat) }))

                    Repeater {
                        model: [1, 2 / 3, 1 / 3]
                        delegate: Rectangle {
                            required property var modelData
                            x: plot.cx - width / 2
                            y: plot.cy - height / 2
                            width: 2 * plot.radius * modelData
                            height: width
                            radius: width / 2
                            color: "transparent"
                            border { color: Theme.hairline; width: 1 }
                        }
                    }
                    Rectangle {
                        x: plot.cx
                        y: plot.cy - plot.radius
                        width: 1
                        height: 2 * plot.radius
                        color: Theme.hairline
                    }
                    Rectangle {
                        x: plot.cx - plot.radius
                        y: plot.cy
                        width: 2 * plot.radius
                        height: 1
                        color: Theme.hairline
                    }
                    Text {
                        x: plot.cx - implicitWidth / 2
                        y: plot.cy - plot.radius - implicitHeight - 1
                        text: "N"
                        color: Theme.taillight
                        font { family: Theme.sans; pixelSize: 12; weight: Font.Bold }
                    }

                    // Utilisés en laque ; captés mais pas utilisés, en cendre ; en vue sans signal, à peine marqués
                    Shape {
                        anchors.fill: parent
                        preferredRendererType: Shape.CurveRenderer
                        ShapePath {
                            fillColor: Theme.lacquer
                            strokeColor: "transparent"
                            PathMultiline { paths: plot.placed.filter(p => p.sat.used).map(p => plot.mark(p.at)) }
                        }
                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: Theme.ash
                            strokeWidth: 1.5
                            PathMultiline { paths: plot.placed.filter(p => !p.sat.used && p.sat.snr > 0).map(p => plot.mark(p.at)) }
                        }
                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.35)
                            strokeWidth: 1
                            PathMultiline { paths: plot.placed.filter(p => !p.sat.snr).map(p => plot.mark(p.at)) }
                        }
                    }
                    Repeater {
                        model: plot.placed
                        delegate: Text {
                            required property var modelData
                            x: modelData.at.x + 8
                            y: modelData.at.y - 13
                            text: modelData.sat.prn
                            color: modelData.sat.used ? Theme.lacquer : Theme.ash
                            opacity: modelData.sat.snr > 0 ? 0.85 : 0.4
                            font { family: Theme.numbers; pixelSize: 11; weight: Font.DemiBold; features: ({ "tnum": 1 }) }
                        }
                    }
                }

                // Constellations : satellites utilisés sur satellites en vue
                Column {
                    x: plot.x + plot.width + 16
                    y: 40
                    spacing: 6

                    Repeater {
                        model: page.values.constellations ?? []
                        delegate: Item {
                            required property var modelData
                            width: 190
                            height: 24

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.name
                                color: Theme.lacquer
                                font { family: Theme.sans; pixelSize: 15; weight: Font.DemiBold }
                            }
                            Text {
                                id: constellationUsed
                                x: 88
                                anchors { baseline: parent.top; baselineOffset: 19 }
                                text: modelData.used
                                color: Theme.lacquer
                                font { family: Theme.numbers; pixelSize: 21; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                            }
                            Text {
                                x: constellationUsed.x + constellationUsed.implicitWidth + 4
                                anchors.baseline: constellationUsed.baseline
                                text: "/ " + modelData.inView
                                color: Theme.ash
                                font { family: Theme.sans; pixelSize: 14; weight: Font.Medium; features: ({ "tnum": 1 }) }
                            }
                        }
                    }
                    Text {
                        visible: page.present && (page.values.constellations ?? []).length === 0
                        text: "Aucun satellite en vue"
                        color: Theme.ash
                        font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
                    }
                }

                // Légende, sous le ciel
                Row {
                    x: 24 + sky.cutX
                    y: plot.y + plot.height + 2
                    spacing: 18

                    Legend { kind: "used"; text: "utilisé" }
                    Legend { kind: "tracked"; text: "capté" }
                    Legend { kind: "silent"; text: "en vue, sans signal" }
                }
            }

            // Signal de chaque satellite, en dB-Hz : au-dessus de 30, il est bon
            Panel {
                id: signal
                width: column.width
                height: 118

                Text {
                    x: 22
                    y: 14
                    text: "Signal"
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
                }
                Text {
                    anchors { right: parent.right; top: parent.top; rightMargin: 22 + signal.cutX; topMargin: 14 }
                    visible: page.values.signalDb !== null && page.values.signalDb !== undefined
                    text: "Moyen " + Format.number(page.values.signalDb) + " dB-Hz"
                    color: Theme.lacquer
                    font { family: Theme.sans; pixelSize: 15; weight: Font.DemiBold; features: ({ "tnum": 1 }) }
                }

                Item {
                    id: bars
                    x: 22
                    y: 44
                    width: signal.width - 44
                    height: 44
                    readonly property real full: 50  // dB-Hz en haut des barres
                    readonly property real slot: width / Math.max(page.satellites.length, 12)
                    readonly property real barWidth: Math.max(4, slot - 5)
                    function bar(index, snr) {
                        const h = Math.max(2, Math.min(1, snr / full) * height)
                        const x0 = index * slot, s = Math.min(5, barWidth / 3)
                        return [Qt.point(x0, height - h), Qt.point(x0 + barWidth - s, height - h),
                                Qt.point(x0 + barWidth, height), Qt.point(x0 + s, height), Qt.point(x0, height - h)]
                    }
                    readonly property var usedBars: page.satellites.map((sat, i) => sat.used ? bar(i, sat.snr) : null)
                                                                   .filter(b => b !== null)
                    readonly property var otherBars: page.satellites.map((sat, i) => sat.used ? null : bar(i, sat.snr))
                                                                    .filter(b => b !== null)

                    // Repère des 30 dB-Hz
                    Rectangle {
                        y: bars.height * (1 - 30 / bars.full)
                        width: bars.width
                        height: 1
                        color: Theme.hairline
                    }
                    Text {
                        anchors { right: parent.left; rightMargin: 3; verticalCenter: parent.top
                                  verticalCenterOffset: bars.height * (1 - 30 / bars.full) }
                        text: "30"
                        color: Theme.ash
                        opacity: 0.7
                        font { family: Theme.numbers; pixelSize: 10; weight: Font.DemiBold }
                    }
                    Shape {
                        anchors.fill: parent
                        preferredRendererType: Shape.CurveRenderer
                        ShapePath {
                            fillColor: Theme.lacquer
                            strokeColor: "transparent"
                            PathMultiline { paths: bars.usedBars }
                        }
                        ShapePath {
                            fillColor: Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.4)
                            strokeColor: "transparent"
                            PathMultiline { paths: bars.otherBars }
                        }
                    }
                    Repeater {
                        model: bars.slot >= 16 ? page.satellites : []
                        delegate: Text {
                            required property int index
                            required property var modelData
                            x: index * bars.slot + bars.barWidth / 2 - implicitWidth / 2
                            y: bars.height + 5
                            text: modelData.prn
                            color: modelData.used ? Theme.lacquer : Theme.ash
                            opacity: 0.85
                            font { family: Theme.numbers; pixelSize: 11; weight: Font.DemiBold; features: ({ "tnum": 1 }) }
                        }
                    }
                }
                Text {
                    anchors.centerIn: bars
                    visible: page.satellites.length === 0
                    text: page.present ? "Aucun satellite en vue" : "Pas de GPS sur le bus"
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
                }
            }

            // Détail des mesures, trois par ligne
            Panel {
                id: details
                width: column.width
                height: 5 * cellHeight + 8
                readonly property real cellWidth: (width - 16) / 3
                readonly property real cellHeight: 56

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
                        value: Format.number(page.values.lat === undefined || page.values.lat === null ? null
                                             : Math.abs(page.values.lat), 5)
                        unit: page.values.lat < 0 ? "° S" : "° N"
                    }
                    Tile {
                        label: "Longitude"
                        value: Format.number(page.values.lon === undefined || page.values.lon === null ? null
                                             : Math.abs(page.values.lon), 5)
                        unit: page.values.lon < 0 ? "° O" : "° E"
                    }
                    Tile {
                        label: "Altitude"
                        value: Format.number(page.values.altitudeM)
                        unit: "m"
                        edge: false
                    }
                    Tile {
                        label: "Vitesse"
                        value: Format.number(page.values.speedKmh, 1)
                        unit: "km/h"
                    }
                    Tile {
                        label: "Cap"
                        value: Format.number(page.values.headingDeg)
                        unit: "°"
                    }
                    Tile {
                        label: "Correction"
                        value: !page.located ? "--" : page.values.sbas ? "SBAS" : "Aucune"
                        numeric: false
                        edge: false
                    }
                    Tile {
                        label: "HDOP"
                        value: Format.number(page.values.hdop, 1)
                    }
                    Tile {
                        label: "PDOP"
                        value: Format.number(page.values.pdop, 1)
                    }
                    Tile {
                        label: "VDOP"
                        value: Format.number(page.values.vdop, 1)
                        edge: false
                    }
                    Tile {
                        label: "Heure UTC"
                        value: page.values.utcTime || "--"
                    }
                    Tile {
                        label: "Horloge du Pi"
                        value: Format.signed(page.values.clockOffsetS)
                        unit: "s"
                    }
                    Tile {
                        readonly property var seconds: page.values.firstFixS
                        label: "1re position en"
                        value: seconds === null || seconds === undefined ? "--"
                               : seconds < 60 ? Format.number(seconds) : Format.span(seconds)
                        unit: seconds < 60 ? "s" : ""
                        edge: false
                    }
                    Tile {
                        label: "Position reçue il y a"
                        value: Format.number(page.values.fixAgeS)
                        unit: "s"
                    }
                    Tile {
                        label: "Date UTC"
                        value: page.values.utcDate ? Format.dayMonth(page.values.utcDate) : "--"
                        numeric: false
                    }
                    Tile {
                        label: "Erreurs du bus"
                        value: Format.number(page.values.errors)
                        edge: false
                    }
                }
            }

            Text {
                x: 8
                visible: (page.values.firmware ?? "") !== ""
                text: "Micrologiciel " + page.values.firmware
                color: Theme.ash
                font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
            }
        }
    }

    component Tile: MeasureTile {
        width: details.cellWidth
        height: details.cellHeight
    }

    // Une ligne de légende du ciel : la case telle qu'elle est dessinée, et ce qu'elle veut dire
    component Legend: Row {
        id: legend
        property string kind
        property string text
        spacing: 7

        Shape {
            width: 12
            height: 8
            anchors.verticalCenter: parent.verticalCenter
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: legend.kind === "used" ? Theme.lacquer : "transparent"
                strokeColor: legend.kind === "used" ? "transparent" : legend.kind === "tracked" ? Theme.ash
                    : Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.35)
                strokeWidth: legend.kind === "tracked" ? 1.5 : 1
                startX: 0; startY: 0
                PathLine { x: 12 - Theme.lean * 8; y: 0 }
                PathLine { x: 12; y: 8 }
                PathLine { x: Theme.lean * 8; y: 8 }
                PathLine { x: 0; y: 0 }
            }
        }
        Text {
            text: legend.text
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
        }
    }
}
