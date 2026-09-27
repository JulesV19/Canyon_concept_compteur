import QtQuick
import "Format.js" as Format

// Mes sorties : les sorties enregistrées, de la plus récente à la plus ancienne. Un toucher rouvre leur résumé.
// Au clavier : ↑ ↓ pour choisir, Entrée ou → pour ouvrir.
Item {
    id: page
    required property var history  // HistoryModel : sorties enregistrées
    signal back
    signal openRequested(int index)

    readonly property var rides: history.rides
    readonly property real totalKm: rides.reduce((sum, ride) => sum + (ride.distanceKm ?? 0), 0)
    property int focusRow: 0        // sortie choisie au clavier
    property bool keyboard: false   // la sortie choisie n'est soulignée qu'au clavier
    onRidesChanged: focusRow = Math.min(focusRow, Math.max(0, rides.length - 1))

    function moveFocus(delta) {
        if (rides.length === 0)
            return
        keyboard = true
        focusRow = Math.max(0, Math.min(rides.length - 1, focusRow + delta))
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
        if (rides.length > 0)
            openRequested(focusRow)
    }
    // À l'ouverture : haut de la liste, et les sorties arrivent en glissant dans l'oblique du logo
    function replay() {
        keyboard = false
        focusRow = 0
        list.positionViewAtBeginning()
        reveal.restart()
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
        title: "Mes sorties"
        onBack: page.back()
    }
    Text {
        anchors { right: parent.right; rightMargin: 24; verticalCenter: header.verticalCenter }
        visible: page.rides.length > 0
        text: Format.number(page.totalKm) + " km"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
    }

    Panel {
        id: panel
        x: 16
        y: header.height + 4
        width: parent.width - 32
        height: parent.height - y - 18

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
            model: page.rides

            delegate: Item {
                id: row
                required property int index
                required property var modelData
                // Arrivée en glissant, l'une après l'autre
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
                    anchors.fill: parent
                    color: Theme.carbonRaised
                    visible: tap.pressed
                }
                Rectangle {
                    y: 14
                    width: 3
                    height: parent.height - 28
                    color: Theme.lacquer
                    visible: page.keyboard && page.focusRow === row.index
                }

                Outline {
                    x: 20
                    y: 20
                    width: 56
                    height: 56
                    points: row.modelData.outline
                }
                Text {
                    id: rideName
                    x: 92
                    y: 16
                    width: rideKm.x - x - 12
                    text: row.modelData.name
                    elide: Text.ElideRight
                    color: Theme.lacquer
                    font { family: Theme.sans; pixelSize: 25; weight: Font.DemiBold }
                }
                Text {
                    id: rideDate
                    x: 92
                    anchors { top: rideName.bottom; topMargin: 2 }
                    width: rideTime.x - x - 12
                    text: row.modelData.dateText
                    elide: Text.ElideRight
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold }
                }

                // Distance et temps, à droite
                Text {
                    id: rideKm
                    anchors { right: kmUnit.left; rightMargin: 4; baseline: rideName.baseline }
                    text: Format.number(row.modelData.distanceKm, 1)
                    color: Theme.lacquer
                    font { family: Theme.numbers; pixelSize: 32; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                }
                Text {
                    id: kmUnit
                    anchors { right: parent.right; rightMargin: 22; baseline: rideName.baseline }
                    text: "km"
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold }
                }
                Text {
                    id: rideTime
                    anchors { right: parent.right; rightMargin: 22; baseline: rideDate.baseline }
                    text: Format.duration(row.modelData.timerS)
                    color: Theme.ash
                    font { family: Theme.numbers; pixelSize: 23; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                }

                Rectangle {
                    x: 20
                    anchors.bottom: parent.bottom
                    width: parent.width - 40
                    height: 1
                    color: Theme.hairline
                    visible: row.index < list.count - 1
                }
                TapHandler {
                    id: tap
                    onTapped: page.openRequested(row.index)
                }
            }
        }

        Text {
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 32 }
            visible: page.rides.length === 0
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: "Aucune sortie enregistrée.\nÀ la fin d'une sortie, Enregistrer la range ici."
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
        }
    }
}
