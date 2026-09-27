import QtQuick

// Sur le Mac, le clavier remplace les boutons physiques (voir le README pour la liste des touches)
Item {
    id: keys
    required property var app  // la fenêtre (Main) : son écran, et ses actions
    required property Item intro
    required property Item home
    required property Item menu
    required property Item settings
    required property Item gps
    required property Item rides
    required property Item segments
    required property Item saved
    required property Item summary
    required property Item pages  // pages de la sortie

    readonly property string screen: app.screen

    // Espace ou Entrée : l'action principale de l'écran (pendant l'intro : la passer)
    function confirm() {
        if (screen === "home")
            home.requestStart()
        else if (screen === "menu")
            menu.activate()
        else if (screen === "settings")
            settings.activate()
        else if (screen === "rides")
            rides.activate()
        else if (screen === "segments")
            segments.activate()
        else if (screen === "saved")
            app.back()
        else if (screen === "summary")
            summary.requestSave()
    }
    // Page suivante (1) ou précédente (−1), en boucle
    function turn(view, delta) {
        view.currentIndex = (view.currentIndex + view.count + delta) % view.count
    }

    Shortcut {
        sequence: "Space"
        context: Qt.ApplicationShortcut
        onActivated: {
            if (keys.app.introRunning)
                keys.intro.skip()
            else if (keys.screen === "ride")
                keys.app.ride.startPause()
            else
                keys.confirm()
        }
    }
    Shortcut {
        sequences: ["Return", "Enter"]
        context: Qt.ApplicationShortcut
        onActivated: {
            if (keys.app.introRunning)
                keys.intro.skip()
            else if (keys.screen !== "ride")
                keys.confirm()
        }
    }
    Shortcut {
        sequence: "L"
        context: Qt.ApplicationShortcut
        enabled: keys.screen === "ride"
        onActivated: keys.app.ride.lap()
    }
    Shortcut {
        sequences: ["P", "Right"]
        context: Qt.ApplicationShortcut
        onActivated: {
            if (keys.screen === "home")
                keys.home.next()
            else if (keys.screen === "settings")
                keys.settings.adjust(1)
            else if (keys.screen === "menu" || keys.screen === "rides")
                keys.confirm()
            else if (keys.screen === "summary")
                keys.turn(keys.summary, 1)
            else if (keys.screen === "saved")
                keys.turn(keys.saved, 1)
            else if (keys.screen === "ride")
                keys.turn(keys.pages, 1)
        }
    }
    Shortcut {
        sequence: "Left"
        context: Qt.ApplicationShortcut
        onActivated: {
            if (keys.screen === "home")
                keys.home.previous()
            else if (keys.screen === "settings")
                keys.settings.adjust(-1)
            else if (["menu", "rides", "segments", "battery", "gps", "carplay"].indexOf(keys.screen) >= 0)
                keys.app.back()
            else if (keys.screen === "summary")
                keys.turn(keys.summary, -1)
            else if (keys.screen === "saved")
                keys.turn(keys.saved, -1)
            else if (keys.screen === "ride")
                keys.turn(keys.pages, -1)
        }
    }
    // ↑ ↓ : ligne précédente ou suivante des listes (défilement sur la page GPS)
    function moveFocus(delta) {
        const list = screen === "menu" ? menu : screen === "settings" ? settings
            : screen === "segments" ? segments : screen === "gps" ? gps : rides
        list.moveFocus(delta)
    }
    readonly property bool listed: ["menu", "settings", "rides", "segments", "gps"].indexOf(screen) >= 0
    Shortcut {
        sequence: "Up"
        context: Qt.ApplicationShortcut
        enabled: keys.listed
        onActivated: keys.moveFocus(-1)
    }
    Shortcut {
        sequence: "Down"
        context: Qt.ApplicationShortcut
        enabled: keys.listed
        onActivated: keys.moveFocus(1)
    }
    Shortcut {
        sequence: "M"
        context: Qt.ApplicationShortcut
        enabled: keys.screen === "home" && !keys.app.introRunning
        onActivated: keys.app.screen = "menu"
    }
    Shortcut {
        sequence: "R"
        context: Qt.ApplicationShortcut
        enabled: keys.screen === "home" && !keys.app.introRunning
        onActivated: keys.app.screen = "settings"
    }
    Shortcut {
        sequence: "E"
        context: Qt.ApplicationShortcut
        enabled: keys.screen === "ride" && keys.app.paused
        onActivated: keys.app.finish()
    }
    // Échap : écran précédent dans le menu ; quitter depuis l'accueil seulement. Jamais pendant une sortie ni sur son
    // résumé : elle n'est pas encore enregistrée (et un futur bouton « retour » pourrait être relié à Échap).
    Shortcut {
        sequence: "Esc"
        context: Qt.ApplicationShortcut
        onActivated: {
            if (keys.app.menuTrail.length)
                keys.app.back()
            else if (keys.screen === "home")
                Qt.quit()
        }
    }
    Shortcut {
        sequences: ["Backspace", "Delete"]
        context: Qt.ApplicationShortcut
        enabled: keys.screen === "summary" || keys.screen === "saved"
        onActivated: {
            if (keys.screen === "summary")
                keys.app.closeSummary(false)
            else
                keys.app.deleteRide()
        }
    }
    // Q : quitter, depuis l'accueil seulement
    Shortcut {
        sequence: "Q"
        context: Qt.ApplicationShortcut
        enabled: keys.screen === "home"
        onActivated: Qt.quit()
    }
}
