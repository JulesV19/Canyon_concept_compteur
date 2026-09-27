import QtQuick

// Messages ou WhatsApp : les conversations, la plus récente en haut. Pastille du contact, nom, heure et chevron, puis
// le dernier message sur deux lignes. Non lu : le point bleu de Messages, ou le compte vert de WhatsApp.
Rectangle {
    id: screen
    required property var phone
    property string kind: "messages"  // ou "whatsapp"
    readonly property bool whatsapp: kind === "whatsapp"
    signal backRequested
    signal conversationRequested(string name)
    color: CarTheme.card

    CarNavBar {
        id: nav
        anchors { top: parent.top; left: parent.left; right: parent.right }
        title: CarTheme.apps[screen.kind].label
        onBackRequested: screen.backRequested()
    }

    ListView {
        id: list
        anchors { top: nav.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: screen.phone[screen.kind]

        delegate: Item {
            id: row
            required property var modelData
            required property int index
            readonly property bool unread: modelData.unread > 0
            objectName: "carPlayConversation-" + modelData.name  // pour les essais
            width: ListView.view.width
            height: CarTheme.pt(76)
            opacity: tap.pressed ? 0.6 : 1

            // Point bleu de Messages, dans la marge
            Rectangle {
                visible: row.unread && !screen.whatsapp
                x: CarTheme.pt(5)
                anchors.verticalCenter: avatar.verticalCenter
                width: CarTheme.pt(10)
                height: width
                radius: width / 2
                color: CarTheme.blue
            }
            CarAvatar {
                id: avatar
                x: CarTheme.pt(18)
                y: CarTheme.pt(12)
                size: CarTheme.pt(40)
                initials: row.modelData.initials
            }
            Text {
                id: name
                anchors { left: avatar.right; leftMargin: CarTheme.pt(10); right: time.left; rightMargin: CarTheme.pt(6) }
                y: CarTheme.pt(9)
                elide: Text.ElideRight
                text: row.modelData.name
                color: CarTheme.label
                font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(17) }
            }
            Text {
                id: time
                anchors { right: screen.whatsapp ? parent.right : chevron.left; baseline: name.baseline }
                anchors.rightMargin: screen.whatsapp ? CarTheme.pt(14) : CarTheme.pt(4)
                text: row.modelData.time
                color: screen.whatsapp && row.unread ? CarTheme.whatsappGreen : CarTheme.secondary
                font { family: CarTheme.text; pixelSize: CarTheme.pt(15) }
            }
            CarGlyph {
                id: chevron
                visible: !screen.whatsapp  // WhatsApp n'en a pas
                anchors { right: parent.right; rightMargin: CarTheme.pt(14); verticalCenter: time.verticalCenter }
                size: CarTheme.pt(12)
                color: CarTheme.tertiary
                stroke: 3.4
                path: "M8 3 L17 12 L8 21"
            }
            Text {
                anchors { left: name.left; right: badge.visible ? badge.left : chevron.right; top: name.bottom }
                anchors.rightMargin: badge.visible ? CarTheme.pt(6) : 0
                maximumLineCount: 2
                wrapMode: Text.Wrap
                elide: Text.ElideRight
                // Groupe WhatsApp : « Thomas : … », comme l'appli
                text: (screen.whatsapp && row.modelData.sender ? row.modelData.sender + " : " : "") + row.modelData.text
                color: CarTheme.secondary
                font { family: CarTheme.text; pixelSize: CarTheme.pt(15) }
            }
            // Compte vert de WhatsApp
            Rectangle {
                id: badge
                visible: row.unread && screen.whatsapp
                anchors { right: parent.right; rightMargin: CarTheme.pt(14) }
                y: CarTheme.pt(38)
                height: CarTheme.pt(20)
                width: Math.max(height, badgeCount.implicitWidth + CarTheme.pt(10))
                radius: height / 2
                color: CarTheme.whatsappGreen

                Text {
                    id: badgeCount
                    anchors.centerIn: parent
                    text: row.modelData.unread
                    color: "white"
                    font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(13); features: ({ "tnum": 1 }) }
                }
            }
            Rectangle {
                visible: row.index < list.count - 1
                anchors { bottom: parent.bottom; left: name.left; right: parent.right }
                height: 1
                color: CarTheme.separator
            }
            CarTap {
                id: tap
                onTapped: screen.conversationRequested(row.modelData.name)
            }
        }
    }

    Text {
        anchors.centerIn: list
        visible: list.count === 0
        text: "Aucun message"
        color: CarTheme.secondary
        font { family: CarTheme.text; pixelSize: CarTheme.pt(17) }
    }
}
