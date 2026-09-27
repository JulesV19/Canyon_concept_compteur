import QtQuick
import QtQuick.Controls.Basic
import "Format.js" as Format

// Page segment, ajoutée aux pages de la sortie au départ d'un segment en favori. En très grand, l'écart au record au
// même point du segment (vert et « − » en avance, rouge et « + » en retard), ou le chrono s'il n'y a pas de record ;
// puis ce qui reste, le profil, la vitesse, le cardio et le KOM. À l'arrivée, le résultat, quelques secondes.
Item {
    id: page
    required property var ride     // RideModel : profil du segment
    required property var values
    property var result: null      // segment fini, montré quelques secondes
    property bool inPages: false   // dans les pages de la sortie (Main.qml l'y ajoute et l'en retire)
    objectName: "segmentPage"      // pour les essais

    readonly property bool finished: result !== null
    readonly property var seg: result ?? values.segment ?? ({})
    readonly property bool hasRecord: seg.prS !== null && seg.prS !== undefined
    readonly property int gap: Math.round(seg.gapS ?? 0)
    readonly property color gapColor: gap < 0 ? Theme.ok : gap > 0 ? Theme.taillight : Theme.lacquer
    readonly property real remainingM: (seg.remainingKm ?? 0) * 1000

    // Position sur le profil : mise à jour chaque seconde quand la page est à l'écran, une fois quand elle devient
    // voisine (elle peut arriver sous le doigt), jamais ailleurs
    readonly property bool live: SwipeView.isCurrentItem && visible
    readonly property bool near: SwipeView.isNextItem || SwipeView.isPreviousItem
    property real profileKm: 0
    function updateProfile() {
        profileKm = seg.doneKm ?? 0
    }
    onLiveChanged: if (live) updateProfile()
    onNearChanged: if (near) updateProfile()
    onSegChanged: if (live) updateProfile()

    // Entrée : la page glisse dans l'oblique du logo pendant que les bandes orange passent, et le logo se dessine
    property real entry: 1
    function enter() {
        mark.play()
        entryAnimation.restart()
    }
    // Arrivée : le logo se redessine ; record battu, un reflet de laque traverse le temps
    function celebrate(record) {
        mark.play()
        if (record)
            hero.shine()
    }
    opacity: entry
    transform: Translate { x: (1 - page.entry) * 18 * Theme.lean; y: (1 - page.entry) * 18 }
    NumberAnimation {
        id: entryAnimation
        target: page
        property: "entry"
        from: 0
        to: 1
        duration: 350
        easing.type: Easing.OutCubic
    }

    // En-tête : le logo, le nom du segment, sa longueur et sa pente (ou « Terminé »)
    StravaMark {
        id: mark
        x: 24
        y: 12
        width: 26
    }
    Text {
        id: name
        x: 60
        y: 4
        width: headerInfo.x - x - 12
        elide: Text.ElideRight
        text: page.seg.name ?? ""
        color: Theme.lacquer
        font { family: Theme.sans; pixelSize: 30; weight: Font.DemiBold }
    }
    Text {
        id: headerInfo
        anchors { right: parent.right; rightMargin: 24; baseline: name.baseline }
        text: page.finished ? "Terminé"
            : Format.number(page.seg.lengthKm, 1) + " km · " + Format.number(page.seg.gradePct, 1) + " %"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
    }

    Text {
        x: 24
        y: 58
        text: page.finished ? "TON TEMPS" : page.hasRecord ? "SUR TON RECORD" : "CHRONO DU SEGMENT"
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5 }
    }
    Row {
        anchors { right: parent.right; rightMargin: 24 }
        y: 58
        spacing: 8
        visible: !(page.finished && page.seg.newRecord === true)

        Text {
            id: recordLabel
            text: page.hasRecord ? "RECORD" : "PREMIER PASSAGE"
            color: Theme.ash
            font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5 }
        }
        Text {
            visible: page.hasRecord
            anchors.baseline: recordLabel.baseline
            text: Format.clock(page.seg.prS)
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 27; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
    }
    SegmentRecordTag { view: page }

    SegmentHero {
        id: hero
        view: page
    }

    SegmentRemaining { view: page }

    SegmentOutcome { view: page }

    SegmentPanel { view: page }
}
