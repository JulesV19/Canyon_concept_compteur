import QtQuick

// Page CarPlay : un clone de CarPlay 26 (thème clair), nourri par l'iPhone en Bluetooth (voir compteur/iphone/). Elle a sa
// propre barre d'état et son accueil ; ouverte depuis le menu, ou parmi les pages de la sortie.
Item {
    id: page
    required property var phone   // PhoneModel
    required property var values  // RideModel.values : barre d'état
    property bool active: true    // à l'écran
    signal exitRequested          // l'icône Compteur

    readonly property var info: phone.values
    property string app: ""           // appli ouverte ; "" : l'accueil
    property string conversation: ""  // Messages, WhatsApp : conversation ouverte ; "" : la liste
    property bool backward: false     // retour d'une conversation à sa liste : l'écran arrive par la gauche
    onActiveChanged: if (!active) {
        pop.stop()
        open("", "")
    }
    // Ouvrir une appli voit ses pastilles s'effacer, comme sur CarPlay ; aussi en la quittant (reçu pendant qu'elle
    // était ouverte)
    function open(name, conversationName) {
        if (name !== "")
            pop.stop()  // une appli touchée sur l'accueil pendant qu'une autre se ferme
        if (app !== "" && app !== "music")
            phone.markRead(app)
        backward = false
        app = name
        conversation = conversationName ?? ""
        if (app !== "" && app !== "music")
            phone.markRead(app)
    }

    // Fermer une appli : l'inverse de l'ouverture, elle repart à droite et découvre l'accueil
    function close() {
        if (!screen.item) {
            open("")
            return
        }
        if (pop.running)
            return
        push.stop()
        pop.start()
    }

    // Fond d'écran (tools/carplay/fond.py), calé en haut : pendant la sortie, la page est un peu moins haute
    Image {
        anchors { top: parent.top; left: parent.left; right: parent.right }
        height: width * 4 / 3
        source: "fond.png"
        sourceSize { width: 480; height: 640 }
    }

    // Dans une appli, la barre d'état prend le fond de l'appli (Musique garde le fond d'écran) ; elle arrive avec elle
    Rectangle {
        x: screen.item ? screen.item.x : 0
        width: parent.width
        anchors { top: parent.top; bottom: content.top }
        visible: page.info.connected && page.app !== "" && page.app !== "music"
        color: page.app === "whatsapp" && page.conversation !== "" ? CarTheme.whatsappBar : CarTheme.card
    }

    CarStatusBar {
        id: status
        anchors { top: parent.top; left: parent.left; right: parent.right }
        values: page.values
        active: page.active
        phoneBattery: page.info.battery ?? -1
    }

    Item {
        id: content
        anchors { top: status.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }

        CarConnect {
            anchors.fill: parent
            visible: !page.info.connected
            available: page.info.available
        }

        CarHome {
            anchors.fill: parent
            // Encore là pendant que l'appli arrive par-dessus
            visible: page.info.connected && (page.app === "" || push.running || pop.running)
            phone: page.phone
            onAppRequested: app => page.open(app)
            onConversationRequested: (app, name) => page.open(app, name)
            onExitRequested: page.exitRequested()
        }

        // Les applis ne se construisent qu'ouvertes : fermées, elles ne coûtent rien
        Loader {
            id: screen
            anchors.fill: parent
            active: page.info.connected && page.app !== ""
            // Chaque écran arrive par la droite, comme sur iOS ; au retour à une liste, par la gauche
            onLoaded: push.restart()
            sourceComponent: page.conversation !== "" ? conversationScreen
                : ({ music: musicScreen, phone: recentsScreen, messages: listScreen, whatsapp: listScreen })[page.app]
                  ?? null
        }
    }

    NumberAnimation {
        id: push
        target: screen.item
        property: "x"
        from: page.backward ? -content.width / 3 : content.width
        to: 0
        duration: 280
        easing.type: Easing.OutCubic
    }

    SequentialAnimation {
        id: pop
        NumberAnimation {
            target: screen.item
            property: "x"
            to: content.width
            duration: push.duration
            easing.type: Easing.InCubic  // la course de l'ouverture (OutCubic), jouée à l'envers
        }
        ScriptAction { script: page.open("") }
    }

    Component {
        id: musicScreen
        NowPlaying {
            phone: page.phone
            onBackRequested: page.close()

            // Son propre fond d'écran, le même, à la même place : elle arrive par-dessus l'accueil et le couvre, comme
            // les autres applis
            Item {
                anchors.fill: parent
                z: -1
                clip: true
                Image {
                    y: -content.y
                    width: page.width
                    height: width * 4 / 3
                    source: "fond.png"
                    sourceSize { width: 480; height: 640 }
                }
            }
        }
    }
    Component {
        id: recentsScreen
        RecentsList {
            phone: page.phone
            onBackRequested: page.close()
        }
    }
    Component {
        id: listScreen
        ConversationList {
            phone: page.phone
            kind: page.app
            onBackRequested: page.close()
            onConversationRequested: name => {
                page.backward = false
                page.conversation = name
            }
        }
    }
    Component {
        id: conversationScreen
        Conversation {
            phone: page.phone
            kind: page.app
            name: page.conversation
            onBackRequested: {
                page.backward = true
                page.conversation = ""
            }
        }
    }
}
