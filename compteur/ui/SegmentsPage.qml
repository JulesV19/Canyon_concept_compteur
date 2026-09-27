import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Segments Strava : les segments vélo en favori, gardés pour rouler sans réseau, avec ton record et le KOM (ou QOM).
// Synchronisés au démarrage et par le bouton du bas. Au clavier : ↑ ↓ pour parcourir, Entrée pour synchroniser.
Item {
    id: page
    required property var strava  // StravaModel
    signal back

    readonly property var segments: strava.segments
    readonly property bool connected: strava.connected
    readonly property bool syncing: strava.syncing
    property int focusRow: 0        // segment choisi au clavier
    property bool keyboard: false   // le segment choisi n'est souligné qu'au clavier
    onSegmentsChanged: focusRow = Math.min(focusRow, Math.max(0, segments.length - 1))

    function moveFocus(delta) {
        if (segments.length === 0)
            return
        keyboard = true
        focusRow = Math.max(0, Math.min(segments.length - 1, focusRow + delta))
        list.positionViewAtIndex(focusRow, ListView.Contain)
        snapRows()
    }
    // Le défilement se cale sur les lignes (snapMode), mais positionViewAtIndex, lui, ne s'en occupe pas : au clavier,
    // on recale sur la ligne, sans jamais dépasser la fin de la liste.
    function snapRows() {
        const last = list.contentHeight + list.bottomMargin - list.height
        list.contentY = Math.max(0, Math.min(Math.ceil(list.contentY / list.rowHeight) * list.rowHeight, last))
    }
    function activate() {
        strava.sync()
    }
    // À l'ouverture : le logo se dessine, et les segments arrivent en glissant dans l'oblique du logo Canyon
    function replay() {
        keyboard = false
        focusRow = 0
        list.positionViewAtBeginning()
        reveal.restart()
        mark.play()
    }

    property real shown: 1
    NumberAnimation {
        id: reveal
        target: page
        property: "shown"
        from: 0
        to: 1
        duration: 900
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.graphite
    }

    PageHeader {
        id: header
        title: "Segments Strava"
        onBack: page.back()
    }
    StravaMark {
        id: mark
        anchors { right: parent.right; rightMargin: 26; verticalCenter: header.verticalCenter }
        width: 26
    }

    Panel {
        id: panel
        x: 16
        y: header.height + 4
        width: parent.width - 32
        height: (page.connected ? status.y - 14 : parent.height - 18) - y

        ListView {
            id: list
            readonly property real rowHeight: 96
            anchors { fill: parent; topMargin: 2; bottomMargin: 2 }
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            // Le cadre ne fait pas un nombre entier de lignes : sans rien, une ligne reste à cheval sur un bord et le
            // rognage tranche le nom en plein milieu. La liste se cale donc sur les lignes, et ce qui dépasse devient
            // une marge sous la dernière : arrivé au bas de la liste, le haut tombe encore juste. Reste, voulue, la
            // lisière de la ligne suivante en bas du cadre : elle dit qu'il y en a d'autres.
            snapMode: ListView.SnapToItem
            bottomMargin: height % rowHeight  // marge du contenu, pas celle des ancres ci-dessus
            model: page.segments

            delegate: Item {
                id: row
                required property int index
                required property var modelData
                readonly property bool hasRecord: typeof modelData.prS === "number"
                readonly property bool hasCrown: typeof modelData.komS === "number"
                // Arrivée en glissant, l'un après l'autre
                readonly property real entry: {
                    const x = Math.max(0, Math.min(1, (page.shown - 0.07 * Math.min(index, 6)) / 0.5))
                    return 1 - Math.pow(1 - x, 3)
                }
                width: list.width
                height: list.rowHeight
                opacity: entry
                // Chaque ligne dans son propre calque : sinon, arrivée en haut du cadre, son dessin déborde
                // sur le titre et y reste (voir Panel.scrolled).
                layer.enabled: true
                transform: Translate { x: (1 - row.entry) * 12 * Theme.lean; y: (1 - row.entry) * 12 }

                Rectangle {
                    y: 14
                    width: 3
                    height: parent.height - 28
                    color: Theme.lacquer
                    visible: page.keyboard && page.focusRow === row.index
                }

                // Profil en vignette, coloré selon la pente
                SegmentProfile {
                    x: 20
                    y: 24
                    width: 60
                    height: 48
                    points: row.modelData.profile
                    axis: false
                    showPosition: false
                    lineWidth: 1.5
                }
                Text {
                    id: segmentName
                    x: 96
                    y: 16
                    width: (row.hasRecord ? record.x : noRecord.x) - x - 12
                    text: row.modelData.name
                    elide: Text.ElideRight
                    color: Theme.lacquer
                    font { family: Theme.sans; pixelSize: 25; weight: Font.DemiBold }
                }
                Text {
                    id: details
                    x: 96
                    anchors { top: segmentName.bottom; topMargin: 2 }
                    width: (row.hasCrown ? crownLabel.x : row.width - 22) - x - 12
                    text: Format.number(row.modelData.lengthKm, 1) + " km"
                          + (typeof row.modelData.gradePct === "number"
                             ? " · " + Format.number(row.modelData.gradePct, 1) + " %" : "")
                    elide: Text.ElideRight
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold }
                }

                // Record à droite, le KOM (ou QOM) dessous
                Text {
                    id: record
                    anchors { right: parent.right; rightMargin: 22; baseline: segmentName.baseline }
                    visible: row.hasRecord
                    text: row.hasRecord ? Format.clock(row.modelData.prS) : ""
                    color: Theme.lacquer
                    font { family: Theme.numbers; pixelSize: 32; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                }
                Text {
                    id: noRecord
                    anchors { right: parent.right; rightMargin: 22; baseline: segmentName.baseline }
                    visible: !row.hasRecord
                    text: "Pas de temps"
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold }
                }
                Text {
                    id: crownTime
                    anchors { right: parent.right; rightMargin: 22; baseline: details.baseline }
                    visible: row.hasCrown
                    text: row.hasCrown ? Format.clock(row.modelData.komS) : ""
                    color: Theme.ash
                    font { family: Theme.numbers; pixelSize: 23; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                }
                Text {
                    id: crownLabel
                    anchors { right: crownTime.left; rightMargin: 6; baseline: details.baseline }
                    visible: row.hasCrown
                    text: row.modelData.komLabel
                    color: Theme.ash
                    font { family: Theme.numbers; pixelSize: 18; weight: Font.DemiBold; letterSpacing: 1.5 }
                }

                Rectangle {
                    x: 20
                    anchors.bottom: parent.bottom
                    width: parent.width - 40
                    height: 1
                    color: Theme.hairline
                    visible: row.index < list.count - 1
                }
            }
        }

        Text {
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 32 }
            visible: page.segments.length === 0
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: !page.connected ? "Pas encore relié à Strava.\nSur le Mac : tools/strava/connecter.py\n"
                                    + "(voir le README, section Strava)"
                : page.syncing ? "Première synchro en cours…"
                : page.strava.error !== "" ? "Pas encore de segments."
                : "Aucun segment vélo en favori.\nMets une étoile à un segment sur Strava, puis synchronise."
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 21; weight: Font.DemiBold }
        }
    }

    // Dernière synchro, ou pourquoi elle n'a pas abouti
    Text {
        id: status
        readonly property int count: page.segments.length
        anchors { left: parent.left; right: parent.right; leftMargin: 20; rightMargin: 20 }
        y: syncButton.y - 14 - height
        visible: page.connected
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        maximumLineCount: 2
        elide: Text.ElideRight
        text: page.strava.error !== "" ? "Synchro inachevée : " + page.strava.error
            : page.strava.syncedText === "" ? "Jamais synchronisé"
            : (count === 0 ? "Aucun segment" : count + (count > 1 ? " segments" : " segment"))
              + " · synchro " + page.strava.syncedText
        color: page.strava.error !== "" ? Theme.danger : Theme.ash
        font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold }
    }

    // Synchroniser, grisé pendant la synchro
    Panel {
        id: syncButton
        readonly property bool pressed: syncTap.pressed
        readonly property color ink: pressed ? Theme.graphite : Theme.lacquer
        x: 16
        y: parent.height - height - 8
        width: parent.width - 32
        height: 68
        visible: page.connected
        color: pressed ? Theme.ash : Theme.carbonRaised
        woven: false
        opacity: page.syncing ? 0.55 : 1
        scale: pressed ? 0.97 : 1
        Behavior on scale { NumberAnimation { duration: 120 } }

        Row {
            anchors.centerIn: parent
            spacing: 12

            // Flèche qui tourne sur elle-même
            Shape {
                width: 24
                height: 24
                anchors.verticalCenter: parent.verticalCenter
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: syncButton.ink
                    strokeWidth: 2.5
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    joinStyle: ShapePath.RoundJoin
                    PathSvg { path: "M 23 4 L 23 10 L 17 10 M 20.49 15 A 9 9 0 1 1 18.37 5.64 L 23 10" }
                }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: page.syncing ? "Synchro en cours…" : "Synchroniser"
                color: syncButton.ink
                font { family: Theme.sans; pixelSize: 26; weight: Font.DemiBold }
            }
        }
        TapHandler {
            id: syncTap
            enabled: !page.syncing
            onTapped: page.strava.sync()
        }
    }
}
