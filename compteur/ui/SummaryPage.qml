import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Shapes
import "Format.js" as Format

// Résumé d'une sortie, sur trois pages à balayer : le tracé et les chiffres clés, l'altitude et les zones
// cardio, puis les tours. En fin de sortie, en bas : Enregistrer (fichier FIT et historique), ou Supprimer,
// à maintenir pour éviter une fausse manœuvre. Rouverte depuis Mes sorties : Retour, ou Supprimer.
Item {
    id: page
    required property var summary        // résumé de la sortie (SessionModel.summary ou HistoryModel.opened)
    property bool saved: false           // sortie déjà enregistrée, rouverte depuis Mes sorties
    property alias currentIndex: pages.currentIndex
    readonly property int count: pages.count
    property bool saving: false          // enregistrement en cours (SessionModel.saving)
    property string saveError: ""        // dernier enregistrement refusé, en quelques mots (SessionModel.saveError)
    property bool stored: false          // enregistrée : « Enregistrée » s'affiche un instant, puis retour à l'accueil
    readonly property bool busy: saving || stored
    property bool slow: false            // écriture qui dure : « Enregistrement… » (pas de clignotement si elle est brève)
    signal save
    signal discard
    signal back
    signal done                          // enregistrée : l'écran peut partir

    readonly property var laps: summary.laps ?? []
    readonly property var zones: summary.hrZonesS ?? [0, 0, 0, 0, 0]

    // Nouveau résumé : première page, et tout se redessine
    function replay() {
        stored = false
        pages.currentIndex = 0
        reveal.restart()
    }
    function requestSave() {
        if (!busy)
            page.save()
    }
    function showSaved() {
        stored = true
        leave.start()
    }

    onSavingChanged: if (!saving) slow = false
    Timer {
        interval: 250
        running: page.saving
        onTriggered: page.slow = true
    }
    Timer {
        id: leave
        interval: 700
        onTriggered: page.done()
    }

    // 0 → 1 : le tracé se dessine, puis les chiffres arrivent. Rejoué à chaque changement de page.
    property real shown: 1
    NumberAnimation {
        id: reveal
        target: page
        property: "shown"
        from: 0
        to: 1
        duration: 1400
    }
    function span(a, b) {
        return Math.max(0, Math.min(1, (shown - a) / (b - a)))
    }
    function ease(x) {
        return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2
    }

    // Points ramenés dans une zone, centrés, en gardant leurs proportions
    function fit(points, box) {
        if (!points || points.length < 2 || box.width <= 0)
            return []
        let right = 0, bottom = 0
        for (const p of points) {
            right = Math.max(right, p.x)
            bottom = Math.max(bottom, p.y)
        }
        const s = Math.min(box.width / Math.max(right, 1e-6), box.height / Math.max(bottom, 1e-6))
        const dx = box.x + (box.width - right * s) / 2
        const dy = box.y + (box.height - bottom * s) / 2
        return points.map(p => Qt.point(dx + p.x * s, dy + p.y * s))
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.graphite
    }

    Text {
        id: title
        x: 24
        y: 6
        width: parent.width - 48
        text: page.summary.name ?? ""
        elide: Text.ElideRight
        color: Theme.lacquer
        font { family: Theme.sans; pixelSize: 24; weight: Font.DemiBold }
    }
    Text {
        id: date
        anchors { left: title.left; top: title.bottom; topMargin: 1 }
        text: page.summary.dateText ?? ""
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
    }

    SwipeView {
        id: pages
        anchors {
            top: date.bottom; left: parent.left; right: parent.right; bottom: dashes.top
            topMargin: 12; bottomMargin: 10
        }
        onCurrentIndexChanged: reveal.restart()

        // Le tracé et les chiffres clés
        Item {
            Panel {
                id: overview
                x: 16
                width: parent.width - 32
                height: parent.height
                readonly property rect trackBox: Qt.rect(24, 18, width - 48, 128)
                readonly property var track: page.fit(page.summary.outline, trackBox)
                readonly property real drawn: page.ease(page.span(0, 0.6))

                Shape {
                    anchors.fill: parent
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        strokeColor: Theme.lacquer
                        strokeWidth: 3
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.RoundJoin
                        trim.end: overview.drawn
                        PathPolyline { path: overview.track }
                    }
                }
                // Départ (plein), puis arrivée (creux) une fois le tracé dessiné
                Repeater {
                    model: overview.track.length ? [0, overview.track.length - 1] : []
                    delegate: Rectangle {
                        required property int index
                        required property int modelData
                        readonly property var at: overview.track[modelData] ?? Qt.point(0, 0)
                        x: at.x - width / 2
                        y: at.y - height / 2
                        width: 12
                        height: 12
                        radius: 6
                        color: index === 0 ? Theme.lacquer : Theme.carbon
                        border { color: index === 0 ? Theme.carbon : Theme.lacquer; width: 3 }
                        opacity: index === 0 ? (overview.drawn > 0 ? 1 : 0) : page.span(0.55, 0.65)
                    }
                }
                Text {
                    x: overview.trackBox.x
                    y: overview.trackBox.y
                    width: overview.trackBox.width
                    height: overview.trackBox.height
                    visible: overview.track.length === 0
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    text: "Pas de trace GPS"
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
                }

                Rectangle {
                    x: 20
                    y: 160
                    width: parent.width - 40
                    height: 1
                    color: Theme.hairline
                }
                Grid {
                    x: 22
                    y: 174
                    width: parent.width - 44
                    columns: 3
                    opacity: page.span(0.35, 0.8)

                    Stat { label: "Distance"; value: Format.number(page.summary.distanceKm, 1); unit: "km" }
                    Stat { label: "Temps"; value: Format.duration(page.summary.timerS) }
                    Stat { label: "Moyenne"; value: Format.number(page.summary.avgSpeedKmh, 1); unit: "km/h" }
                    Stat { label: "Dénivelé +"; value: Format.number(page.summary.ascentM); unit: "m" }
                    Stat { label: "Vitesse max"; value: Format.number(page.summary.maxSpeedKmh, 1); unit: "km/h" }
                    Stat { label: "Temps total"; value: Format.duration(page.summary.elapsedS) }
                    Stat { label: "Cardio moyen"; value: Format.number(page.summary.avgHeartRate); unit: "bpm" }
                    Stat { label: "FC max"; value: Format.number(page.summary.maxHeartRate); unit: "bpm" }
                    Stat { label: "Dénivelé −"; value: Format.number(page.summary.descentM); unit: "m" }
                }
            }
        }

        // L'altitude et les zones cardio
        Item {
            Panel {
                id: altitude
                x: 16
                width: parent.width - 32
                height: 192
                readonly property var points: page.summary.profile ?? []
                readonly property var extent: {
                    let low = Infinity, high = -Infinity
                    for (const p of points) {
                        low = Math.min(low, p.y)
                        high = Math.max(high, p.y)
                    }
                    return { low: low, high: high }
                }
                readonly property rect chartBox: Qt.rect(22, 50, width - 44, 104)
                // Profil ramené dans sa zone (au moins 40 m de haut, pour ne pas grossir les faux plats)
                readonly property var line: {
                    if (points.length < 2)
                        return []
                    const box = chartBox
                    const range = Math.max(40, extent.high - extent.low)
                    const end = points[points.length - 1].x || 1
                    return points.map(p => Qt.point(box.x + p.x / end * box.width,
                                                    box.y + box.height - (p.y - extent.low) / range * box.height))
                }

                Text {
                    x: 22
                    y: 14
                    text: "Altitude"
                    color: Theme.lacquer
                    font { family: Theme.sans; pixelSize: 18; weight: Font.DemiBold }
                }
                Row {
                    anchors { right: parent.right; top: parent.top; rightMargin: 22 + altitude.cutX; topMargin: 12 }
                    spacing: 14
                    Figure { value: Format.number(page.summary.ascentM); unit: "m D+" }
                    Figure { value: Format.number(page.summary.descentM); unit: "m D−" }
                }

                // Le profil se déroule de gauche à droite
                Item {
                    width: altitude.chartBox.x + page.ease(page.span(0.1, 0.8)) * altitude.chartBox.width
                    height: altitude.height
                    clip: true

                    Shape {
                        width: altitude.width
                        height: altitude.height
                        preferredRendererType: Shape.CurveRenderer
                        ShapePath {
                            strokeColor: "transparent"
                            fillColor: Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.14)
                            PathPolyline {
                                path: altitude.line.length ? altitude.line.concat([
                                    Qt.point(altitude.chartBox.x + altitude.chartBox.width, altitude.chartBox.y + altitude.chartBox.height),
                                    Qt.point(altitude.chartBox.x, altitude.chartBox.y + altitude.chartBox.height)]) : []
                            }
                        }
                        ShapePath {
                            strokeColor: Theme.lacquer
                            strokeWidth: 2
                            fillColor: "transparent"
                            joinStyle: ShapePath.RoundJoin
                            PathPolyline { path: altitude.line }
                        }
                    }
                }
                Text {
                    x: 22
                    y: altitude.chartBox.y + altitude.chartBox.height + 8
                    visible: altitude.line.length > 0
                    text: "min " + Format.number(altitude.extent.low) + " m"
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
                }
                Text {
                    anchors { right: parent.right; rightMargin: 22 }
                    y: altitude.chartBox.y + altitude.chartBox.height + 8
                    visible: altitude.line.length > 0
                    text: "max " + Format.number(altitude.extent.high) + " m"
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
                }
                Text {
                    x: altitude.chartBox.x
                    y: altitude.chartBox.y
                    width: altitude.chartBox.width
                    height: altitude.chartBox.height
                    visible: altitude.line.length === 0
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    text: "Pas d'altitude pendant la sortie"
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
                }
            }

            Panel {
                id: zonesPanel
                x: 16
                y: altitude.height + 12
                width: parent.width - 32
                height: parent.height - y
                readonly property real longest: page.zones.reduce((most, s) => Math.max(most, s), 1)
                readonly property real total: page.zones.reduce((sum, s) => sum + s, 0)

                Text {
                    x: 22
                    y: 14
                    text: "Zones cardio"
                    color: Theme.lacquer
                    font { family: Theme.sans; pixelSize: 18; weight: Font.DemiBold }
                }
                Column {
                    x: 22
                    y: 44
                    width: parent.width - 44
                    spacing: 3
                    visible: zonesPanel.total > 0

                    Repeater {
                        model: 5
                        delegate: ZoneRow {
                            required property int index
                            zone: index
                            seconds: page.zones[index] ?? 0
                            longest: zonesPanel.longest
                            total: zonesPanel.total
                            grow: page.ease(page.span(0.25 + 0.07 * index, 0.75 + 0.05 * index))
                        }
                    }
                }
                Text {
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 22; topMargin: 56 }
                    visible: zonesPanel.total === 0
                    text: "Pas de mesure cardio pendant la sortie"
                    wrapMode: Text.WordWrap
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
                }
            }
        }

        // Les tours
        Item {
            Panel {
                id: lapsPanel
                x: 16
                width: parent.width - 32
                height: parent.height
                readonly property var columns: [22, 86, 206, 326]  // tour, temps, distance, moyenne

                Repeater {
                    model: ["Tour", "Temps", "Distance", "Moyenne"]
                    delegate: Text {
                        required property int index
                        required property string modelData
                        x: lapsPanel.columns[index]
                        y: 16
                        text: modelData
                        color: Theme.ash
                        font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
                    }
                }
                Rectangle {
                    x: 20
                    y: 42
                    width: parent.width - 40
                    height: 1
                    color: Theme.hairline
                }
                ListView {
                    id: lapList
                    y: 43
                    width: parent.width
                    height: parent.height - y - 10
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    model: page.laps

                    delegate: Item {
                        id: lapRow
                        required property int index
                        required property var modelData
                        readonly property real entry: page.span(0.1 + Math.min(index, 8) * 0.06, 0.5 + Math.min(index, 8) * 0.05)
                        width: lapList.width
                        height: 48
                        opacity: entry
                        transform: Translate { x: (1 - lapRow.entry) * 12 * Theme.lean; y: (1 - lapRow.entry) * 12 }

                        Text {
                            x: lapsPanel.columns[0]
                            anchors.verticalCenter: parent.verticalCenter
                            text: lapRow.modelData.number
                            color: Theme.ash
                            font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                        }
                        Text {
                            x: lapsPanel.columns[1]
                            anchors.verticalCenter: parent.verticalCenter
                            text: Format.duration(lapRow.modelData.timerS)
                            color: Theme.lacquer
                            font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                        }
                        Figure {
                            x: lapsPanel.columns[2]
                            anchors.verticalCenter: parent.verticalCenter
                            value: Format.number(lapRow.modelData.distanceKm, 2)
                            unit: "km"
                        }
                        Figure {
                            x: lapsPanel.columns[3]
                            anchors.verticalCenter: parent.verticalCenter
                            value: Format.number(lapRow.modelData.avgSpeedKmh, 1)
                            unit: "km/h"
                        }
                        Rectangle {
                            x: 20
                            anchors.bottom: parent.bottom
                            width: parent.width - 40
                            height: 1
                            color: Theme.hairline
                            visible: lapRow.index < lapList.count - 1
                        }
                    }
                }
                Text {
                    anchors {
                        left: parent.left; right: parent.right; bottom: parent.bottom
                        leftMargin: 22; rightMargin: 22; bottomMargin: 28
                    }
                    visible: page.laps.length <= 1
                    text: "Un seul tour : pendant la sortie, le bouton Lap découpe la sortie en tours."
                    wrapMode: Text.WordWrap
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
                }
            }
        }
    }

    Dashes {
        id: dashes
        anchors.horizontalCenter: parent.horizontalCenter
        y: discardButton.y - 16 - height
        count: pages.count
        currentIndex: pages.currentIndex
        opacity: holdHint.visible || saveFailure.visible ? 0 : 1
    }

    // Enregistrement refusé (carte pleine...) : la raison, à la place des tirets. Enregistrer réessaie ; Supprimer reste
    // possible.
    Text {
        id: saveFailure
        anchors { horizontalCenter: parent.horizontalCenter; verticalCenter: dashes.verticalCenter }
        width: parent.width - 32
        visible: page.saveError !== "" && !page.busy && !holdHint.visible
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: "Pas enregistrée : " + page.saveError
        color: Theme.danger
        font { family: Theme.sans; pixelSize: 15; weight: Font.DemiBold }
    }

    // Un simple appui sur Supprimer rappelle qu'il faut maintenir
    Text {
        id: holdHint
        anchors { horizontalCenter: parent.horizontalCenter; verticalCenter: dashes.verticalCenter }
        opacity: 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 200 } }
        text: "Maintenir pour supprimer"
        color: Theme.danger
        font { family: Theme.sans; pixelSize: 15; weight: Font.DemiBold }

        Timer {
            id: hideHint
            interval: 2000
            onTriggered: holdHint.opacity = 0
        }
    }

    HoldButton {
        id: discardButton
        x: 16
        y: parent.height - height - 18
        width: 150
        height: 68
        text: "Supprimer"
        fillColor: Theme.danger
        enabled: !page.busy
        onActivated: page.discard()
        onInterrupted: {
            holdHint.opacity = 1
            hideHint.restart()
        }
    }

    // Enregistrer, en laque (fin de sortie), ou Retour (sortie rouverte depuis Mes sorties)
    Panel {
        id: mainButton
        readonly property color ink: page.saved && !mainTap.pressed ? Theme.lacquer : Theme.graphite
        x: discardButton.x + discardButton.width + 10
        y: discardButton.y
        width: parent.width - x - 16
        height: 68
        color: page.saved ? (mainTap.pressed ? Theme.ash : Theme.carbonRaised)
                          : (mainTap.pressed ? Qt.darker(Theme.lacquer, 1.15) : Theme.lacquer)
        woven: false
        outline: page.saved ? Theme.hairline : "transparent"
        scale: mainTap.pressed ? 0.97 : 1
        Behavior on scale { NumberAnimation { duration: 120 } }

        Row {
            anchors.centerIn: parent
            spacing: 12

            Item {
                width: 20
                height: 22
                anchors.verticalCenter: parent.verticalCenter

                // Flèche vers le bas (enregistrer), puis coche une fois la sortie enregistrée ; chevron pour Retour
                Shape {
                    anchors.fill: parent
                    visible: !waiting.visible
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        strokeColor: mainButton.ink
                        strokeWidth: 3
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.RoundJoin
                        PathSvg {
                            path: page.saved ? "M 14 2 L 5 11 L 14 20"
                                : page.stored ? "M 2 12 L 8 18 L 19 5" : "M 10 1 L 10 14 M 4 9 L 10 15 L 16 9 M 2 20 L 18 20"
                        }
                    }
                }
                // Anneau qui tourne pendant une écriture qui dure, comme l'attente du GPS sur l'accueil
                Shape {
                    id: waiting
                    anchors.fill: parent
                    visible: page.saving && page.slow
                    preferredRendererType: Shape.CurveRenderer
                    RotationAnimation on rotation {
                        running: waiting.visible
                        from: 0
                        to: 360
                        duration: 900
                        loops: Animation.Infinite
                    }
                    ShapePath {
                        strokeColor: mainButton.ink
                        strokeWidth: 3
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        PathAngleArc { centerX: 10; centerY: 11; radiusX: 8; radiusY: 8; startAngle: 0; sweepAngle: 270 }
                    }
                }
            }
            Text {
                text: page.saved ? "Retour" : page.stored ? "Enregistrée"
                    : page.saving && page.slow ? "Enregistrement…" : "Enregistrer"
                color: mainButton.ink
                font { family: Theme.sans; pixelSize: 24; weight: Font.DemiBold }
            }
        }
        TapHandler {
            id: mainTap
            onTapped: page.saved ? page.back() : page.requestSave()
        }
    }

    // Un chiffre du résumé : libellé, valeur en chiffres penchés, unité
    component Stat: Item {
        id: stat
        property string label
        property string value
        property string unit
        width: parent.width / 3
        height: 74

        Text {
            text: stat.label
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
        }
        Text {
            id: statValue
            anchors { baseline: parent.top; baselineOffset: 50 }
            text: stat.value
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 32; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            x: statValue.implicitWidth + 5
            anchors.baseline: statValue.baseline
            text: stat.unit
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
        }
    }

    // Un chiffre et son unité, sur une ligne
    component Figure: Row {
        id: figure
        property string value
        property string unit
        spacing: 4

        Text {
            id: figureValue
            text: figure.value
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            anchors.baseline: figureValue.baseline
            text: figure.unit
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
        }
    }

}
