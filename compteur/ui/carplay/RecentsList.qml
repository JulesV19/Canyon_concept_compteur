import QtQuick

// Téléphone, Récents : le nom (en rouge pour un appel manqué, « (2) » s'il a appelé plusieurs fois), le type d'appel et
// l'heure. Rappeler n'est pas possible : l'iPhone ne passe pas d'appel pour un accessoire Bluetooth.
Rectangle {
    id: screen
    required property var phone
    signal backRequested
    color: CarTheme.card

    CarNavBar {
        id: nav
        anchors { top: parent.top; left: parent.left; right: parent.right }
        title: "Récents"
        onBackRequested: screen.backRequested()
    }

    ListView {
        id: list
        anchors { top: nav.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: screen.phone.recents

        delegate: Item {
            id: row
            required property var modelData
            required property int index
            readonly property bool missed: modelData.category === "missed_call"
            width: ListView.view.width
            height: CarTheme.pt(56)

            // L'heure sur la ligne du nom, comme iOS : la ligne du dessous a toute la largeur
            Text {
                id: name
                anchors { left: parent.left; leftMargin: CarTheme.pt(16); right: time.left; rightMargin: CarTheme.pt(8) }
                y: CarTheme.pt(8)
                elide: Text.ElideRight
                text: row.modelData.name + (row.modelData.count > 1 ? " (" + row.modelData.count + ")" : "")
                color: row.missed ? CarTheme.red : CarTheme.label
                font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(17) }
            }
            Text {
                anchors { left: name.left; right: parent.right; rightMargin: CarTheme.pt(16); top: name.bottom }
                elide: Text.ElideRight
                text: row.modelData.app === "whatsapp" ? "Audio WhatsApp" : row.modelData.label
                color: CarTheme.secondary
                font { family: CarTheme.text; pixelSize: CarTheme.pt(15) }
            }
            Text {
                id: time
                anchors { right: parent.right; rightMargin: CarTheme.pt(16); baseline: name.baseline }
                text: row.modelData.time
                color: CarTheme.secondary
                font { family: CarTheme.text; pixelSize: CarTheme.pt(15) }
            }
            // Filet en retrait, comme les listes d'iOS ; pas sous la dernière ligne
            Rectangle {
                visible: row.index < list.count - 1
                anchors { bottom: parent.bottom; left: parent.left; right: parent.right; leftMargin: CarTheme.pt(16) }
                height: 1
                color: CarTheme.separator
            }
        }
    }

    Text {
        anchors.centerIn: list
        visible: list.count === 0
        text: "Aucun appel récent"
        color: CarTheme.secondary
        font { family: CarTheme.text; pixelSize: CarTheme.pt(17) }
    }
}
