import QtQuick
import QtQuick.Controls.Basic

Window {
    id: root
    required property var ride            // sortie en cours (RideModel)
    required property var session         // parcours de l'accueil, départ et fin (SessionModel)
    required property var history         // sorties enregistrées (HistoryModel)
    required property var settings        // réglages (SettingsModel)
    required property var strava          // segments Strava en favori et leur synchro (StravaModel)
    required property var battery         // charge, autonomie et mesures de la batterie (BatteryModel)
    required property var gps             // état de la réception GPS (GpsModel)
    required property int tickMs          // durée d'un pas de simulation, pour animer la carte
    required property bool introEnabled
    required property bool introAutoplay  // faux : l'intro est pilotée image par image (enregistrement)
    property alias page: pages.currentIndex
    property alias homeIndex: home.currentIndex
    property alias introTime: intro.t
    readonly property real introDuration: intro.duration
    // "home" : accueil ; "ride" : sortie en cours ; "summary" : résumé de la sortie terminée ;
    // menu (bouton ≡ de l'accueil) : "menu", puis "settings" (réglages), "battery" et "gps" (Batterie et GPS, depuis
    // les réglages), "rides" (Mes sorties), "saved" (une sortie rouverte), "segments" (Segments Strava)
    property string screen: "home"
    property string resumedAt: ""  // sortie reprise au démarrage après une coupure : heure de sa dernière écriture
    property int segmentResultMs: 15000  // durée du résultat d'un segment à l'écran
    readonly property int pageCount: pages.count
    readonly property bool segmentOpen: segmentPage.inPages
    readonly property bool introRunning: intro.visible
    readonly property bool paused: ride.values.state === "paused"

    // Écran 2,8" en portrait. Sur le Pi, la fenêtre occupe tout l'écran.
    width: 480
    height: 640
    minimumWidth: width
    maximumWidth: width
    minimumHeight: height
    maximumHeight: height
    visible: true
    color: Theme.graphite
    title: "Canyon compteur"

    // Écrans du menu ouverts, du premier au dernier : chacun reste en place sous celui qui glisse par-dessus
    readonly property var menuTrail: ({
        menu: ["menu"],
        settings: ["menu", "settings"],
        battery: ["menu", "settings", "battery"],
        gps: ["menu", "settings", "gps"],
        rides: ["menu", "rides"],
        saved: ["menu", "rides", "saved"],
        segments: ["menu", "segments"]
    })[screen] ?? []
    function inMenu(name) {
        return menuTrail.indexOf(name) >= 0
    }
    // Retour à l'écran précédent du menu (à l'accueil depuis le menu)
    function back() {
        if (menuTrail.length)
            screen = menuTrail.length > 1 ? menuTrail[menuTrail.length - 2] : "home"
    }
    function openRides() {
        ridesPage.replay()
        screen = "rides"
    }
    function openSegments() {
        strava.check()  // relié depuis le démarrage ?
        segmentsPage.replay()
        screen = "segments"
    }
    function openRide(index) {
        history.open(index)
        savedPage.replay()
        screen = "saved"
    }
    function deleteRide() {
        if (screen !== "saved")
            return
        history.removeOpened()
        screen = "rides"
    }

    // Départ : la carte choisie s'agrandit jusqu'à la page de sortie
    function start(index) {
        if (screen !== "home")
            return
        resumedAt = ""  // une sortie neuve n'est pas une sortie reprise
        closeSegmentPage()
        launch.run(home.cardRect())
        session.start(index)
        pages.currentIndex = 0
        screen = "ride"
    }
    // Fin de la sortie : son résumé, puis Enregistrer ou Supprimer
    function finish() {
        if (screen !== "ride")
            return
        closeSegmentPage()
        session.finish()
        summaryPage.replay()
        screen = "summary"
    }
    // Enregistrer : la sortie s'écrit sans figer l'écran ; l'accueil revient une fois qu'elle est à l'abri (voir
    // onSaved), et si la carte refuse, le résumé reste, avec la raison. Rien ne se supprime pendant l'écriture.
    function closeSummary(save) {
        if (screen !== "summary" || session.saving)
            return
        if (save) {
            session.save()
            return
        }
        session.discard()
        leaveSummary()
    }
    function leaveSummary() {
        if (screen !== "summary")
            return
        screen = "home"
        home.replay()
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
        if (screen !== "ride")
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
            root.showPage(root.indexOfPage(segmentPage))
            segmentPage.enter()
        }
    }
    // Le résultat reste quelques secondes, puis la page s'en va (sauf si un autre segment est en cours)
    Timer {
        id: segmentHold
        interval: root.segmentResultMs
        onTriggered: {
            segmentPage.result = null
            if (root.ride.values.segment === undefined)
                root.closeSegmentPage()
        }
    }
    Connections {
        target: root.ride
        function onSegmentStarted(card) {
            root.openSegmentPage(true)
        }
        function onSegmentFinished(result) {
            segmentPage.result = result
            root.openSegmentPage(false)
            segmentPage.celebrate(result.newRecord === true)
            if (result.newRecord === true)
                sweep.run()
            segmentHold.restart()
        }
        function onSegmentAbandoned(card) {
            if (segmentPage.result === null && root.ride.values.segment === undefined)
                root.closeSegmentPage()
        }
    }
    Connections {
        target: root.session
        function onSaved() {
            summaryPage.showSaved()  // « Enregistrée » un instant, puis l'accueil
        }
        function onPowerOffFailed(message) {
            menuPage.powerError = message
        }
    }

    // Sur le Mac, le clavier remplace les boutons physiques.
    // Espace ou Entrée : l'action principale de l'écran (pendant l'intro : la passer)
    function confirm() {
        if (screen === "home")
            home.requestStart()
        else if (screen === "menu")
            menuPage.activate()
        else if (screen === "settings")
            settingsPage.activate()
        else if (screen === "rides")
            ridesPage.activate()
        else if (screen === "segments")
            segmentsPage.activate()
        else if (screen === "saved")
            back()
        else if (screen === "summary")
            summaryPage.requestSave()
    }
    // Page suivante (1) ou précédente (−1), en boucle
    function turn(view, delta) {
        view.currentIndex = (view.currentIndex + view.count + delta) % view.count
    }

    Shortcut {
        sequence: "Space"
        context: Qt.ApplicationShortcut
        onActivated: {
            if (root.introRunning)
                intro.skip()
            else if (root.screen === "ride")
                root.ride.startPause()
            else
                root.confirm()
        }
    }
    Shortcut {
        sequences: ["Return", "Enter"]
        context: Qt.ApplicationShortcut
        onActivated: {
            if (root.introRunning)
                intro.skip()
            else if (root.screen !== "ride")
                root.confirm()
        }
    }
    Shortcut {
        sequence: "L"
        context: Qt.ApplicationShortcut
        enabled: root.screen === "ride"
        onActivated: root.ride.lap()
    }
    Shortcut {
        sequences: ["P", "Right"]
        context: Qt.ApplicationShortcut
        onActivated: {
            if (root.screen === "home")
                home.next()
            else if (root.screen === "settings")
                settingsPage.adjust(1)
            else if (root.screen === "menu" || root.screen === "rides")
                root.confirm()
            else if (root.screen === "summary")
                root.turn(summaryPage, 1)
            else if (root.screen === "saved")
                root.turn(savedPage, 1)
            else if (root.screen === "ride")
                root.turn(pages, 1)
        }
    }
    Shortcut {
        sequence: "Left"
        context: Qt.ApplicationShortcut
        onActivated: {
            if (root.screen === "home")
                home.previous()
            else if (root.screen === "settings")
                settingsPage.adjust(-1)
            else if (["menu", "rides", "segments", "battery", "gps"].indexOf(root.screen) >= 0)
                root.back()
            else if (root.screen === "summary")
                root.turn(summaryPage, -1)
            else if (root.screen === "saved")
                root.turn(savedPage, -1)
            else if (root.screen === "ride")
                root.turn(pages, -1)
        }
    }
    Shortcut {
        sequences: ["Up", "Down"]
        context: Qt.ApplicationShortcut
        enabled: ["menu", "settings", "rides", "segments", "gps"].indexOf(root.screen) >= 0
        onActivated: {
            const list = root.screen === "menu" ? menuPage : root.screen === "settings" ? settingsPage
                : root.screen === "segments" ? segmentsPage : root.screen === "gps" ? gpsPage : ridesPage
            list.moveFocus(sequence === "Up" ? -1 : 1)
        }
    }
    Shortcut {
        sequence: "M"
        context: Qt.ApplicationShortcut
        enabled: root.screen === "home" && !root.introRunning
        onActivated: root.screen = "menu"
    }
    Shortcut {
        sequence: "R"
        context: Qt.ApplicationShortcut
        enabled: root.screen === "home" && !root.introRunning
        onActivated: root.screen = "settings"
    }
    Shortcut {
        sequence: "E"
        context: Qt.ApplicationShortcut
        enabled: root.screen === "ride" && root.paused
        onActivated: root.finish()
    }
    // Échap : écran précédent dans le menu ; quitter depuis l'accueil seulement. Jamais pendant une sortie ni sur son
    // résumé : elle n'est pas encore enregistrée (et un futur bouton « retour » pourrait être relié à Échap).
    Shortcut {
        sequence: "Esc"
        context: Qt.ApplicationShortcut
        onActivated: {
            if (root.menuTrail.length)
                root.back()
            else if (root.screen === "home")
                Qt.quit()
        }
    }
    Shortcut {
        sequences: ["Backspace", "Delete"]
        context: Qt.ApplicationShortcut
        enabled: root.screen === "summary" || root.screen === "saved"
        onActivated: {
            if (root.screen === "summary")
                root.closeSummary(false)
            else
                root.deleteRide()
        }
    }
    // Q : quitter, depuis l'accueil seulement
    Shortcut {
        sequence: "Q"
        context: Qt.ApplicationShortcut
        enabled: root.screen === "home"
        onActivated: Qt.quit()
    }

    StatusBar {
        id: statusBar
        anchors { top: parent.top; left: parent.left; right: parent.right }
        values: root.ride.values
        showRideState: root.screen === "ride"
        opacity: root.introRunning ? intro.chrome : 1
    }

    HomePage {
        id: home
        anchors { top: statusBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        session: root.session
        values: root.ride.values
        reveal: root.introRunning ? intro.reveal : 1
        logoShown: !root.introRunning
        opacity: root.screen === "home" ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 300 } }
        onStartRequested: index => root.start(index)
        onMenuRequested: root.screen = "menu"
    }

    // Menu : chaque écran glisse depuis la droite, par-dessus le précédent. Seul l'écran affiché répond au doigt :
    // un toucher ne traverse jamais jusqu'à l'écran recouvert.
    MenuPage {
        id: menuPage
        anchors { top: statusBar.bottom; bottom: parent.bottom }
        width: parent.width
        x: root.inMenu("menu") ? 0 : width
        enabled: root.screen === "menu"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        history: root.history
        strava: root.strava
        onBack: root.back()
        onRidesRequested: root.openRides()
        onSegmentsRequested: root.openSegments()
        onSettingsRequested: root.screen = "settings"
        onPowerOffRequested: root.session.powerOff()
    }

    SettingsPage {
        id: settingsPage
        anchors { top: statusBar.bottom; bottom: parent.bottom }
        width: parent.width
        x: root.inMenu("settings") ? 0 : width
        enabled: root.screen === "settings"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        settings: root.settings
        battery: root.battery
        gps: root.gps
        onBack: root.back()
        onBatteryRequested: root.screen = "battery"
        onGpsRequested: {
            gpsPage.replay()
            root.screen = "gps"
        }
    }

    GpsPage {
        id: gpsPage
        objectName: "gpsPage"  // pour les essais
        anchors { top: statusBar.bottom; bottom: parent.bottom }
        width: parent.width
        x: root.inMenu("gps") ? 0 : width
        enabled: root.screen === "gps"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        gps: root.gps
        onBack: root.back()
    }

    BatteryPage {
        id: batteryPage
        anchors { top: statusBar.bottom; bottom: parent.bottom }
        width: parent.width
        x: root.inMenu("battery") ? 0 : width
        enabled: root.screen === "battery"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        battery: root.battery
        onBack: root.back()
    }

    RidesPage {
        id: ridesPage
        anchors { top: statusBar.bottom; bottom: parent.bottom }
        width: parent.width
        x: root.inMenu("rides") ? 0 : width
        enabled: root.screen === "rides"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        history: root.history
        onBack: root.back()
        onOpenRequested: index => root.openRide(index)
    }

    SegmentsPage {
        id: segmentsPage
        objectName: "segmentsPage"  // pour les essais
        anchors { top: statusBar.bottom; bottom: parent.bottom }
        width: parent.width
        x: root.inMenu("segments") ? 0 : width
        enabled: root.screen === "segments"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        strava: root.strava
        onBack: root.back()
    }

    // Une sortie rouverte depuis Mes sorties : le même résumé, avec Retour et Supprimer
    SummaryPage {
        id: savedPage
        anchors { top: statusBar.bottom; bottom: parent.bottom }
        width: parent.width
        x: root.inMenu("saved") ? 0 : width
        enabled: root.screen === "saved"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        summary: root.history.opened
        saved: true
        onBack: root.back()
        onDiscard: root.deleteRide()
    }

    // Sortie en cours : les pages défilent au doigt (balayage horizontal)
    Item {
        anchors { top: statusBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        // Pendant le départ, la page n'apparaît qu'une fois la carte agrandie
        opacity: root.screen === "ride" && !launch.growing ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 250 } }

        SwipeView {
            id: pages
            anchors { top: parent.top; left: parent.left; right: parent.right; bottom: indicator.top; bottomMargin: 8 }

            RidePage { values: root.ride.values }
            MapPage {
                ride: root.ride
                values: root.ride.values
                animationMs: root.tickMs
            }
            AltitudePage {
                ride: root.ride
                values: root.ride.values
            }
            CardioPage {
                ride: root.ride
                values: root.ride.values
            }
            LapsPage {
                ride: root.ride
                values: root.ride.values
            }
        }

        Dashes {
            id: indicator
            anchors { bottom: parent.bottom; bottomMargin: 10; horizontalCenter: parent.horizontalCenter }
            count: pages.count
            currentIndex: pages.currentIndex
        }

        // En pause : maintenir pour terminer la sortie. Le bas de la page s'efface en fondu derrière le bouton.
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 150
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.rgba(Theme.graphite.r, Theme.graphite.g, Theme.graphite.b, 0) }
                GradientStop { position: 0.3; color: Theme.graphite }
            }
            opacity: root.paused ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 200 } }

            HoldButton {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 16; rightMargin: 16; bottomMargin: 20 }
                height: 68
                text: "Maintenir pour terminer"
                onActivated: root.finish()
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
            values: root.ride.values
            profile: root.ride.segmentProfile
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
                ride: root.ride
                values: root.ride.values
            }
        }
    }

    // Sortie reprise au démarrage, en pause : le bandeau le dit dès la première image, avec ses chiffres
    Connections {
        id: resumeNotice
        target: root
        enabled: root.resumedAt !== "" && root.screen === "ride"
        function onFrameSwapped() {
            resumeNotice.enabled = false
            const values = root.ride.values
            lapBanner.show({ timerS: values.timerS, distanceKm: values.distanceKm, avgSpeedKmh: values.avgSpeedKmh,
                             avgHeartRate: values.avgHeartRate }, "Sortie reprise · coupée à " + root.resumedAt, 6000)
        }
    }

    // Résumé de fin de sortie : il arrive en glissant dans l'oblique du logo
    SummaryPage {
        id: summaryPage
        property real entry: root.screen === "summary" ? 1 : 0
        anchors { top: statusBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        summary: root.session.summary
        saving: root.session.saving
        saveError: root.session.saveError
        opacity: entry
        visible: entry > 0
        transform: Translate { x: (1 - summaryPage.entry) * 18 * Theme.lean; y: (1 - summaryPage.entry) * 18 }
        Behavior on entry { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }
        onSave: root.closeSummary(true)
        onDiscard: root.closeSummary(false)
        onDone: root.leaveSummary()
    }

    Connections {
        target: root.ride
        // Pas de bandeau sur une page qui montre elle-même le tour fini (page tours)
        function onLapCompleted(summary) {
            if (!pages.currentItem || !pages.currentItem.showsLaps)
                lapBanner.show(summary)
        }
    }

    // Départ : un panneau carbone part de la carte choisie, s'agrandit jusqu'à la page de sortie,
    // puis s'efface sur elle
    Panel {
        id: launch
        property bool growing: false
        visible: false

        function run(from) {
            x = from.x
            y = from.y
            width = from.width
            height = from.height
            cut = 22
            opacity = 1
            visible = true
            growing = true
            takeOff.restart()
        }

        SequentialAnimation {
            id: takeOff
            ParallelAnimation {
                NumberAnimation { target: launch; property: "x"; to: 0; duration: 450; easing.type: Easing.OutCubic }
                NumberAnimation { target: launch; property: "y"; to: statusBar.height; duration: 450; easing.type: Easing.OutCubic }
                NumberAnimation { target: launch; property: "width"; to: root.width; duration: 450; easing.type: Easing.OutCubic }
                NumberAnimation { target: launch; property: "height"; to: root.height - statusBar.height; duration: 450; easing.type: Easing.OutCubic }
                NumberAnimation { target: launch; property: "cut"; to: 0; duration: 450; easing.type: Easing.OutCubic }
            }
            ScriptAction { script: launch.growing = false }
            NumberAnimation { target: launch; property: "opacity"; to: 0; duration: 250 }
            ScriptAction { script: launch.visible = false }
        }
    }

    Intro {
        id: intro
        anchors.fill: parent
        target: home.logo
        autoplay: root.introEnabled && root.introAutoplay
        visible: root.introEnabled && !done
    }
}
