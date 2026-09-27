import QtQuick
import "carplay"

// Les écrans du menu (bouton ≡ de l'accueil) et la navigation entre eux
Item {
    id: menus
    required property var app  // la fenêtre (Main) : son écran, et sa largeur
    required property var history
    required property var strava
    required property var phone
    required property var settings
    required property var battery
    required property var gps
    required property var rideValues
    property real contentTop: 0  // haut des écrans, sous la barre d'état (CarPlay prend tout l'écran)
    readonly property alias menu: menuPage
    readonly property alias settingsScreen: settingsPage
    readonly property alias gpsScreen: gpsPage
    readonly property alias rides: ridesPage
    readonly property alias segments: segmentsPage
    readonly property alias saved: savedPage
    readonly property alias carPlay: menuCarPlay
    signal powerOffRequested()

    // Écrans du menu ouverts, du premier au dernier : chacun reste en place sous celui qui glisse par-dessus
    readonly property var trail: ({
        menu: ["menu"],
        settings: ["menu", "settings"],
        battery: ["menu", "settings", "battery"],
        gps: ["menu", "settings", "gps"],
        rides: ["menu", "rides"],
        saved: ["menu", "rides", "saved"],
        segments: ["menu", "segments"],
        carplay: ["menu", "carplay"]
    })[app.screen] ?? []
    function inMenu(name) {
        return trail.indexOf(name) >= 0
    }
    // Retour à l'écran précédent du menu (à l'accueil depuis le menu)
    function back() {
        if (trail.length)
            app.screen = trail.length > 1 ? trail[trail.length - 2] : "home"
    }
    function openRides() {
        ridesPage.replay()
        app.screen = "rides"
    }
    function openSegments() {
        strava.check()  // relié depuis le démarrage ?
        segmentsPage.replay()
        app.screen = "segments"
    }
    function openRide(index) {
        history.open(index)
        savedPage.replay()
        app.screen = "saved"
    }
    function deleteRide() {
        if (app.screen !== "saved")
            return
        history.removeOpened()
        app.screen = "rides"
    }

    // Menu : chaque écran glisse depuis la droite, par-dessus le précédent. Seul l'écran affiché répond au doigt :
    // un toucher ne traverse jamais jusqu'à l'écran recouvert. Au repos, l'écran est posé juste à droite de la
    // fenêtre, à `menus.app.width` et non à sa propre largeur : celle-ci vaut encore zéro quand la liaison est évaluée la
    // première fois, l'écran partait donc de la gauche et traversait l'accueil en 320 ms au lancement — les sept à la
    // fois, par-dessus l'intro, au moment le plus lourd du compteur.
    MenuPage {
        id: menuPage
        anchors { top: parent.top; topMargin: menus.contentTop; bottom: parent.bottom }
        width: parent.width
        x: menus.inMenu("menu") ? 0 : menus.app.width
        enabled: menus.app.screen === "menu"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        history: menus.history
        strava: menus.strava
        phone: menus.phone
        onBack: menus.back()
        onRidesRequested: menus.openRides()
        onSegmentsRequested: menus.openSegments()
        onCarPlayRequested: menus.app.screen = "carplay"
        onSettingsRequested: menus.app.screen = "settings"
        onPowerOffRequested: menus.powerOffRequested()
    }

    SettingsPage {
        id: settingsPage
        anchors { top: parent.top; topMargin: menus.contentTop; bottom: parent.bottom }
        width: parent.width
        x: menus.inMenu("settings") ? 0 : menus.app.width
        enabled: menus.app.screen === "settings"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        settings: menus.settings
        battery: menus.battery
        gps: menus.gps
        onBack: menus.back()
        onBatteryRequested: menus.app.screen = "battery"
        onGpsRequested: {
            gpsPage.replay()
            menus.app.screen = "gps"
        }
    }

    GpsPage {
        id: gpsPage
        objectName: "gpsPage"  // pour les essais
        anchors { top: parent.top; topMargin: menus.contentTop; bottom: parent.bottom }
        width: parent.width
        x: menus.inMenu("gps") ? 0 : menus.app.width
        enabled: menus.app.screen === "gps"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        gps: menus.gps
        onBack: menus.back()
    }

    BatteryPage {
        id: batteryPage
        anchors { top: parent.top; topMargin: menus.contentTop; bottom: parent.bottom }
        width: parent.width
        x: menus.inMenu("battery") ? 0 : menus.app.width
        enabled: menus.app.screen === "battery"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        battery: menus.battery
        onBack: menus.back()
    }

    RidesPage {
        id: ridesPage
        anchors { top: parent.top; topMargin: menus.contentTop; bottom: parent.bottom }
        width: parent.width
        x: menus.inMenu("rides") ? 0 : menus.app.width
        enabled: menus.app.screen === "rides"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        history: menus.history
        onBack: menus.back()
        onOpenRequested: index => menus.openRide(index)
    }

    SegmentsPage {
        id: segmentsPage
        objectName: "segmentsPage"  // pour les essais
        anchors { top: parent.top; topMargin: menus.contentTop; bottom: parent.bottom }
        width: parent.width
        x: menus.inMenu("segments") ? 0 : menus.app.width
        enabled: menus.app.screen === "segments"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        strava: menus.strava
        onBack: menus.back()
    }

    // CarPlay, depuis le menu : tout l'écran, barre d'état comprise ; l'icône Compteur ramène au menu
    CarPlayPage {
        id: menuCarPlay
        objectName: "menuCarPlay"  // pour les essais
        y: 0
        height: parent.height
        width: parent.width
        x: menus.inMenu("carplay") ? 0 : menus.app.width
        enabled: menus.app.screen === "carplay"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        phone: menus.phone
        values: menus.rideValues
        active: menus.app.screen === "carplay"
        onExitRequested: menus.back()
    }

    // Une sortie rouverte depuis Mes sorties : le même résumé, avec Retour et Supprimer
    SummaryPage {
        id: savedPage
        anchors { top: parent.top; topMargin: menus.contentTop; bottom: parent.bottom }
        width: parent.width
        x: menus.inMenu("saved") ? 0 : menus.app.width
        enabled: menus.app.screen === "saved"
        visible: x < width
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        summary: menus.history.opened
        saved: true
        onBack: menus.back()
        onDiscard: menus.deleteRide()
    }
}
