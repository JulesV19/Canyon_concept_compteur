import QtQuick
import QtQuick.Controls.Basic
import "carplay"

Window {
    id: root
    required property var ride            // sortie en cours (RideModel)
    required property var session         // parcours de l'accueil, départ et fin (SessionModel)
    required property var history         // sorties enregistrées (HistoryModel)
    required property var settings        // réglages (SettingsModel)
    required property var strava          // segments Strava en favori et leur synchro (StravaModel)
    required property var battery         // charge, autonomie et mesures de la batterie (BatteryModel)
    required property var gps             // état de la réception GPS (GpsModel)
    required property var phone           // l'iPhone, pour la page CarPlay (PhoneModel)
    required property int tickMs          // durée d'un pas de simulation, pour animer la carte
    required property bool introEnabled
    required property bool introAutoplay  // faux : l'intro est pilotée image par image (enregistrement)
    property alias page: rideScreen.currentIndex
    property alias homeIndex: home.currentIndex
    property alias introTime: intro.t
    readonly property real introDuration: intro.duration
    // "home" : accueil ; "ride" : sortie en cours ; "summary" : résumé de la sortie terminée ;
    // menu (bouton ≡ de l'accueil) : "menu", puis "settings" (réglages), "battery" et "gps" (Batterie et GPS, depuis
    // les réglages), "rides" (Mes sorties), "saved" (une sortie rouverte), "segments" (Segments Strava), "carplay"
    property string screen: "home"
    property string resumedAt: ""  // sortie reprise au démarrage après une coupure : heure de sa dernière écriture
    property alias segmentResultMs: rideScreen.segmentResultMs  // durée du résultat d'un segment à l'écran
    readonly property int pageCount: rideScreen.count
    readonly property bool segmentOpen: rideScreen.segmentOpen
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

    // La page CarPlay a sa propre barre d'état : celle du compteur s'efface tant qu'elle est à l'écran
    readonly property bool carPlayShown: screen === "carplay" || (screen === "ride" && rideScreen.carPlayCurrent)
    readonly property alias menuTrail: menus.trail
    // Retour à l'écran précédent du menu (à l'accueil depuis le menu)
    function back() {
        menus.back()
    }
    function deleteRide() {
        menus.deleteRide()
    }

    // Départ : la carte choisie s'agrandit jusqu'à la page de sortie
    function start(index) {
        if (screen !== "home")
            return
        resumedAt = ""  // une sortie neuve n'est pas une sortie reprise
        rideScreen.closeSegmentPage()
        launch.run(home.cardRect())
        session.start(index)
        rideScreen.currentIndex = 0
        screen = "ride"
    }
    // Fin de la sortie : son résumé, puis Enregistrer ou Supprimer
    function finish() {
        if (screen !== "ride")
            return
        rideScreen.closeSegmentPage()
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


    Connections {
        target: root.session
        function onSaved() {
            summaryPage.showSaved()  // « Enregistrée » un instant, puis l'accueil
        }
        function onPowerOffFailed(message) {
            menus.menu.powerError = message
        }
    }


    Shortcuts {
        app: root
        intro: intro
        home: home
        menu: menus.menu
        settings: menus.settingsScreen
        gps: menus.gpsScreen
        rides: menus.rides
        segments: menus.segments
        saved: menus.saved
        summary: summaryPage
        pages: rideScreen.pages
    }

    StatusBar {
        id: statusBar
        anchors { top: parent.top; left: parent.left; right: parent.right }
        values: root.ride.values
        showRideState: root.screen === "ride"
        opacity: root.introRunning ? intro.chrome : 1
        visible: !root.carPlayShown
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

    MenuScreens {
        id: menus
        anchors.fill: parent
        contentTop: statusBar.height
        app: root
        history: root.history
        strava: root.strava
        phone: root.phone
        settings: root.settings
        battery: root.battery
        gps: root.gps
        rideValues: root.ride.values
        onPowerOffRequested: root.session.powerOff()
    }


    // iPhone : appel entrant et nouveau message, en bandeau en bas de l'écran comme CarPlay 26, pendant la sortie et sur
    // la page CarPlay du menu. En pause, au-dessus du bouton pour terminer.
    readonly property bool phoneBanners: screen === "ride" || screen === "carplay"
    readonly property real bannerBottom: screen === "ride" ? (paused ? 150 : 34) : 16


    // Nouveau message : le toucher ouvre sa conversation dans la page CarPlay
    function openConversation(app, name) {
        const page = screen === "ride" ? rideScreen.showCarPlay() : menus.carPlay
        page.open(app, name)
    }
    Connections {
        target: root.phone
        function onMessageArrived(message) {
            // Déjà sous les yeux : la conversation ouverte sur la page CarPlay affichée
            const page = root.screen === "carplay" ? menus.carPlay : root.carPlayShown ? rideScreen.carPlay : null
            if (root.phoneBanners && !(page && page.app === message.app && page.conversation === message.name))
                messageBanner.show(message)
        }
    }


    RideScreen {
        id: rideScreen
        anchors { top: root.carPlayShown ? parent.top : statusBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        // Pendant le départ, la page n'apparaît qu'une fois la carte agrandie
        opacity: root.screen === "ride" && !launch.growing ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 250 } }
        ride: root.ride
        phone: root.phone
        tickMs: root.tickMs
        active: root.screen === "ride"
        paused: root.paused
        carPlayShown: root.carPlayShown
        onFinishRequested: root.finish()
    }

    // Sortie reprise au démarrage, en pause : le bandeau le dit dès la première image, avec ses chiffres
    Connections {
        id: resumeNotice
        target: root
        enabled: root.resumedAt !== "" && root.screen === "ride"
        function onFrameSwapped() {
            resumeNotice.enabled = false
            const values = root.ride.values
            rideScreen.lapBanner.show({ timerS: values.timerS, distanceKm: values.distanceKm, avgSpeedKmh: values.avgSpeedKmh,
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

    LaunchPanel {
        id: launch
        landingY: statusBar.height
    }

    MessageBanner {
        id: messageBanner
        objectName: "messageBanner"  // pour les essais
        anchors { left: parent.left; right: parent.right; margins: CarTheme.pt(8) }
        // Un appel qui sonne passe devant : le message se range au-dessus
        y: root.height - root.bannerBottom - height - (callBanner.shown ? callBanner.height + CarTheme.pt(6) : 0)
        visible: entry > 0 && root.phoneBanners
        onOpened: (app, name) => root.openConversation(app, name)
    }
    CallBanner {
        id: callBanner
        objectName: "callBanner"  // pour les essais
        anchors { left: parent.left; right: parent.right; margins: CarTheme.pt(8) }
        y: root.height - root.bannerBottom - height
        visible: entry > 0 && root.phoneBanners
        phone: root.phone
    }

    Intro {
        id: intro
        anchors.fill: parent
        target: home.logo
        autoplay: root.introEnabled && root.introAutoplay
        visible: root.introEnabled && !done
    }
}
