import QtQuick
import QtQuick.Controls

// Accueil de CarPlay, en deux pages qui défilent au doigt, comme CarPlay 26 : d'abord le tableau de bord (le widget
// « À l'écoute », puis le dernier message), puis les applis en grille, avec leurs
// pastilles et leur nom. Des points en bas disent où l'on est. Comme l'icône du constructeur dans une voiture, la
// dernière appli ramène au compteur. Glisser vers la gauche depuis les applis ramène d'abord au tableau de bord ; de là
// seulement, on quitte la page (vers les tours pendant la sortie).
Item {
    id: home
    required property var phone
    readonly property var unread: phone.values.unread ?? ({})
    signal appRequested(string app)
    signal conversationRequested(string app, string name)
    signal exitRequested

    readonly property var apps: ["music", "phone", "messages", "whatsapp", "compteur"]

    SwipeView {
        id: pages
        objectName: "carPlayHomePages"  // pour les essais
        anchors { top: parent.top; left: parent.left; right: parent.right; bottom: dots.top }
        clip: true

        // Tableau de bord
        Item {
            MusicWidget {
                id: music
                objectName: "carPlayMusicWidget"  // pour les essais
                anchors { top: parent.top; left: parent.left; right: parent.right; margins: CarTheme.pt(10) }
                anchors.topMargin: CarTheme.pt(4)
                height: CarTheme.pt(106)
                phone: home.phone
                onOpened: home.appRequested("music")
            }

            MessageWidget {
                anchors { top: music.bottom; topMargin: CarTheme.pt(10); left: music.left; right: music.right }
                anchors.bottom: parent.bottom
                anchors.bottomMargin: CarTheme.pt(4)
                phone: home.phone
                onConversationRequested: (app, name) => home.conversationRequested(app, name)
            }
        }

        // Applis : trois par ligne, l'icône et son nom, comme l'écran d'accueil de CarPlay
        Item {
            Grid {
                anchors.centerIn: parent
                columns: 3
                columnSpacing: CarTheme.pt(4)
                rowSpacing: CarTheme.pt(10)

                Repeater {
                    model: home.apps
                    delegate: Item {
                        id: cell
                        required property string modelData
                        objectName: "carPlayIcon-" + modelData  // pour les essais
                        width: CarTheme.pt(74)
                        height: CarTheme.pt(80)
                        opacity: tap.pressed ? 0.6 : 1

                        AppIcon {
                            id: icon
                            visible: cell.modelData !== "compteur"
                            anchors { top: parent.top; topMargin: CarTheme.pt(4); horizontalCenter: parent.horizontalCenter }
                            width: CarTheme.pt(56)
                            app: cell.modelData
                            badge: home.unread[cell.modelData] ?? 0
                        }
                        CompteurIcon {
                            visible: cell.modelData === "compteur"
                            anchors.centerIn: icon
                            size: icon.width
                        }
                        Text {
                            anchors { top: icon.bottom; topMargin: CarTheme.pt(4); left: parent.left; right: parent.right }
                            horizontalAlignment: Text.AlignHCenter
                            elide: Text.ElideRight
                            text: cell.modelData === "compteur" ? "Compteur" : CarTheme.apps[cell.modelData].label
                            color: CarTheme.label
                            font { family: CarTheme.text; pixelSize: CarTheme.pt(12) }
                        }
                        CarTap {
                            id: tap
                            onTapped: cell.modelData === "compteur" ? home.exitRequested() : home.appRequested(cell.modelData)
                        }
                    }
                }
            }
        }
    }

    // Points de page, comme sur iOS : noir pour la page affichée, gris pour l'autre
    Row {
        id: dots
        anchors { bottom: parent.bottom; bottomMargin: CarTheme.pt(6); horizontalCenter: parent.horizontalCenter }
        spacing: CarTheme.pt(8)

        Repeater {
            model: pages.count
            delegate: Rectangle {
                required property int index
                width: CarTheme.pt(7)
                height: width
                radius: width / 2
                color: index === pages.currentIndex ? "#CC000000" : "#40000000"
            }
        }
    }
}
