import QtQuick
import QtQuick.Shapes

// Le ciel vu d'en haut : l'horizon, 30° et 60° d'élévation, le zénith au centre, le nord en haut
Panel {
    id: sky
    required property var view  // la page GPS : ses valeurs et son état
    scrolled: true
    height: 252

    Text {
        x: 22
        y: 14
        text: "CIEL"
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5 }
    }

    Item {
        id: plot
        x: 22
        y: 36
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
        readonly property var placed: view.satellites
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
            font { family: Theme.sans; pixelSize: 16; weight: Font.Bold }
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
                font { family: Theme.numbers; pixelSize: 14; weight: Font.DemiBold; features: ({ "tnum": 1 }) }
            }
        }
    }

    // Constellations : satellites utilisés sur satellites en vue
    Column {
        x: plot.x + plot.width + 16
        y: 40
        spacing: 6

        Repeater {
            model: view.values.constellations ?? []
            delegate: Item {
                required property var modelData
                width: 200
                height: 32

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.name
                    color: Theme.lacquer
                    font { family: Theme.sans; pixelSize: 20; weight: Font.DemiBold }
                }
                Text {
                    id: constellationUsed
                    x: 100
                    anchors { baseline: parent.top; baselineOffset: 19 }
                    text: modelData.used
                    color: Theme.lacquer
                    font { family: Theme.numbers; pixelSize: 27; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                }
                Text {
                    x: constellationUsed.x + constellationUsed.implicitWidth + 4
                    anchors.baseline: constellationUsed.baseline
                    text: "/ " + modelData.inView
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold; features: ({ "tnum": 1 }) }
                }
            }
        }
        Text {
            visible: view.present && (view.values.constellations ?? []).length === 0
            text: "Aucun satellite en vue"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 20; weight: Font.DemiBold }
        }
    }

    // Légende, sous le ciel
    Row {
        x: 24 + sky.cutX
        y: plot.y + plot.height + 2
        spacing: 18

        GpsSkyLegend { kind: "used"; text: "utilisé" }
        GpsSkyLegend { kind: "tracked"; text: "capté" }
        GpsSkyLegend { kind: "silent"; text: "en vue, sans signal" }
    }
}
