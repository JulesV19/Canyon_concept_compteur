import QtQuick
import QtQuick.Controls.Basic
import "carplay"

// Sortie en cours : les pages défilent au doigt (balayage horizontal), avec par-dessus le bouton pour terminer (en
// pause), les bandeaux de tour et de segment, et la page segment le temps d'un segment
Item {
    id: screen
    required property var ride
    required property var phone
    required property int tickMs
    required property bool active         // l'écran de sortie est affiché
    required property bool paused
    required property bool carPlayShown   // la page CarPlay a sa propre barre d'état (voir Main)
    property int segmentResultMs: 15000   // durée du résultat d'un segment à l'écran
    property alias currentIndex: pages.currentIndex
    readonly property alias count: pages.count
    readonly property alias pages: pages
    readonly property alias lapBanner: lapBanner
    readonly property alias carPlay: rideCarPlay
    readonly property bool carPlayCurrent: pages.currentItem === rideCarPlay
    readonly property bool segmentOpen: segmentPage.inPages
    signal finishRequested()

    // La page CarPlay, pour y ouvrir une conversation
    function showCarPlay() {
        pages.currentIndex = indexOfPage(rideCarPlay)
        return rideCarPlay
    }

    // Page segment : toujours la deuxième, juste après la page principale. Ajoutée au départ d'un segment et montrée
    // d'office pendant que les bandes orange passent ; retirée après l'arrivée (ou l'abandon), en revenant à la page
    // d'avant.
    readonly property int segmentPageIndex: 1
    property Item pageBeforeSegment: null
    function indexOfPage(item) {
        for (let i = 0; i < pages.count; i++) {
            if (pages.itemAt(i) === item)
                return i
        }
        return -1
    }
    // Page affichée sans glisser : les bandes orange font la transition
    function showPage(index) {
        const view = pages.contentItem
        const duration = view.highlightMoveDuration
        view.highlightMoveDuration = 0
        pages.currentIndex = index
        view.highlightMoveDuration = duration
    }
    function openSegmentPage(sweeping) {
        if (!active)
            return
        if (!segmentPage.inPages) {
            pageBeforeSegment = pages.currentItem
            pages.insertItem(segmentPageIndex, segmentPage)
            segmentPage.inPages = true
            showPage(indexOfPage(pageBeforeSegment))  // la page affichée reste la même jusqu'aux bandes
        }
        if (pages.currentItem === segmentPage || segmentSwitch.running)
            return
        if (sweeping) {
            sweep.run()
            segmentSwitch.restart()
        } else {
            showPage(indexOfPage(segmentPage))
        }
    }
    function closeSegmentPage() {
        segmentHold.stop()
        segmentSwitch.stop()
        segmentPage.result = null
        if (!segmentPage.inPages)
            return
        const back = pages.currentItem === segmentPage ? pageBeforeSegment : pages.currentItem
        pages.takeItem(indexOfPage(segmentPage))
        segmentPage.inPages = false
        showPage(Math.max(0, indexOfPage(back)))
    }
    // Les bandes sont au milieu de l'écran : la page segment arrive
    Timer {
        id: segmentSwitch
        interval: 350
        onTriggered: {
            screen.showPage(screen.indexOfPage(segmentPage))
            segmentPage.enter()
        }
    }
    // Le résultat reste quelques secondes, puis la page s'en va (sauf si un autre segment est en cours)
    Timer {
        id: segmentHold
        interval: screen.segmentResultMs
        onTriggered: {
            segmentPage.result = null
            if (screen.ride.values.segment === undefined)
                screen.closeSegmentPage()
        }
    }
    Connections {
        target: screen.ride
        function onSegmentStarted(card) {
            screen.openSegmentPage(true)
        }
        function onSegmentFinished(result) {
            segmentPage.result = result
            screen.openSegmentPage(false)
            segmentPage.celebrate(result.newRecord === true)
            if (result.newRecord === true)
                sweep.run()
            segmentHold.restart()
        }
        function onSegmentAbandoned(card) {
            if (segmentPage.result === null && screen.ride.values.segment === undefined)
                screen.closeSegmentPage()
        }
        // Pas de bandeau sur une page qui montre elle-même le tour fini (page tours)
        function onLapCompleted(summary) {
            if (!pages.currentItem || !pages.currentItem.showsLaps)
                lapBanner.show(summary)
        }
    }

    SwipeView {
        id: pages
        anchors { top: parent.top; left: parent.left; right: parent.right; bottom: indicator.top; bottomMargin: 8 }

        RidePage { values: screen.ride.values }
        MapPage {
            ride: screen.ride
            values: screen.ride.values
            animationMs: screen.tickMs
        }
        AltitudePage {
            ride: screen.ride
            values: screen.ride.values
        }
        CardioPage {
            ride: screen.ride
            values: screen.ride.values
        }
        LapsPage {
            ride: screen.ride
            values: screen.ride.values
        }
        CarPlayPage {
            id: rideCarPlay
            objectName: "rideCarPlay"  // pour les essais
            phone: screen.phone
            values: screen.ride.values
            active: SwipeView.isCurrentItem && screen.active
            onExitRequested: pages.currentIndex = 0
        }
    }

    // Sous la page CarPlay, le bas de l'écran continue son fond d'écran
    Item {
        id: carPlayStrip
        anchors { top: pages.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        visible: screen.carPlayShown
        clip: true
        Image {
            y: -carPlayStrip.y
            width: screen.Window.width
            height: screen.Window.height
            source: "carplay/fond.png"
            sourceSize { width: 480; height: 640 }
        }
    }

    Dashes {
        id: indicator
        anchors { bottom: parent.bottom; bottomMargin: 10; horizontalCenter: parent.horizontalCenter }
        count: pages.count
        currentIndex: pages.currentIndex
        dark: screen.carPlayShown
    }

    // En pause : maintenir pour terminer la sortie. Le bas de la page s'efface en fondu derrière le bouton.
    Rectangle {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 150
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.rgba(Theme.graphite.r, Theme.graphite.g, Theme.graphite.b, 0) }
            GradientStop { position: 0.3; color: Theme.graphite }
        }
        opacity: screen.paused ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 200 } }

        HoldButton {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 16; rightMargin: 16; bottomMargin: 20 }
            height: 68
            text: "Maintenir pour terminer"
            onActivated: screen.finishRequested()
        }
    }

    // Fin de tour : le bandeau passe sur la vitesse. Il fait partie de la sortie et s'en va avec elle
    // (il ne recouvre jamais le résumé).
    LapBanner {
        id: lapBanner
        objectName: "lapBanner"  // pour les essais
        x: 16
        y: 4
        width: parent.width - 32
    }

    // Annonce d'un segment en favori, à son approche
    SegmentBanner {
        objectName: "segmentBanner"  // pour les essais
        x: 16
        y: 4
        width: parent.width - 32
        values: screen.ride.values
        profile: screen.ride.segmentProfile
    }

    // Départ d'un segment : les bandes orange passent sur les pages
    StravaSweep {
        id: sweep
        anchors.fill: pages
    }

    // La page segment, hors des pages tant qu'aucun segment n'est en cours : elle ne dessine rien
    Item {
        visible: false

        SegmentPage {
            id: segmentPage
            ride: screen.ride
            values: screen.ride.values
        }
    }
}
