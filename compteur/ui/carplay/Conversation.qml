import QtQuick

// Une conversation, avec le texte des messages reçus (CarPlay les fait lire par Siri ; ici on les lit). Chaque appli a
// son allure : Messages, bulles grises sur blanc, l'heure au-dessus après un silence ; WhatsApp, bulles blanches sur
// son fond beige, l'heure dans la bulle, le jour dans une pastille.
Rectangle {
    id: screen
    required property var phone
    property string kind: "messages"
    property string name
    readonly property bool whatsapp: kind === "whatsapp"
    // Relue dans la liste à chaque changement : un nouveau message s'ajoute en bas
    readonly property var conversation: (phone[kind] ?? []).find(c => c.name === name) ?? ({ initials: "", messages: [] })
    readonly property var messages: conversation.messages
    readonly property bool group: messages.some(m => m.sender !== "")
    signal backRequested
    color: whatsapp ? CarTheme.whatsappWallpaper : CarTheme.card

    function nameColor(sender) {
        let hash = 0
        for (let i = 0; i < sender.length; ++i)
            hash = (hash * 31 + sender.charCodeAt(i)) % 997
        return CarTheme.whatsappNames[hash % CarTheme.whatsappNames.length]
    }
    // Dernière bulle d'une suite du même expéditeur : elle porte la queue (et, dans un groupe Messages, la pastille)
    function endsRun(index) {
        const next = messages[index + 1]
        return !next || next.sender !== messages[index].sender || next.stamp !== "" || next.day !== messages[index].day
    }
    function startsRun(index) {
        const previous = messages[index - 1]
        return !previous || previous.sender !== messages[index].sender || messages[index].stamp !== ""
            || previous.day !== messages[index].day
    }

    ListView {
        id: list
        anchors { top: header.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: screen.messages
        topMargin: CarTheme.pt(6)
        bottomMargin: CarTheme.pt(10)
        // Le dernier message en bas, comme dans l'appli ; aussi quand la liste est relue (un message arrivé ailleurs),
        // sans quoi la vue repartirait du haut
        onModelChanged: Qt.callLater(positionViewAtEnd)
        Component.onCompleted: positionViewAtEnd()

        delegate: Item {
            id: message
            required property var modelData
            required property int index
            readonly property bool first: screen.startsRun(index)
            readonly property bool last: screen.endsRun(index)
            readonly property bool dayChanged: index === 0 || screen.messages[index - 1].day !== modelData.day
            width: ListView.view.width
            height: column.height + (last ? CarTheme.pt(8) : CarTheme.pt(2))

            Column {
                id: column
                width: parent.width

                // Messages : « Aujourd'hui 16:12 », le jour en gras
                Row {
                    visible: !screen.whatsapp && message.modelData.stamp !== ""
                    anchors.horizontalCenter: parent.horizontalCenter
                    topPadding: CarTheme.pt(8)
                    bottomPadding: CarTheme.pt(6)
                    Text {
                        text: message.modelData.day + " "
                        color: CarTheme.secondary
                        font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(11) }
                    }
                    Text {
                        text: message.modelData.time
                        color: CarTheme.secondary
                        font { family: CarTheme.text; pixelSize: CarTheme.pt(11) }
                    }
                }
                // WhatsApp : le jour dans une pastille blanche
                Item {
                    visible: screen.whatsapp && message.dayChanged
                    width: parent.width
                    height: CarTheme.pt(36)
                    Rectangle {
                        anchors.centerIn: parent
                        width: chip.implicitWidth + CarTheme.pt(16)
                        height: CarTheme.pt(22)
                        radius: CarTheme.pt(7)
                        color: "#FFFFFF"
                        Text {
                            id: chip
                            anchors.centerIn: parent
                            text: message.modelData.day
                            color: CarTheme.whatsappTime
                            font { family: CarTheme.text; pixelSize: CarTheme.pt(12) }
                        }
                    }
                }
                // Groupe Messages : le nom au-dessus de la première bulle
                Text {
                    visible: !screen.whatsapp && screen.group && message.first && message.modelData.sender !== ""
                    x: bubble.x + CarTheme.pt(12)
                    bottomPadding: CarTheme.pt(2)
                    text: message.modelData.sender
                    color: CarTheme.secondary
                    font { family: CarTheme.text; pixelSize: CarTheme.pt(11) }
                }

                Item {
                    width: parent.width
                    height: bubble.height

                    // Groupe Messages : la pastille de l'expéditeur, à côté de sa dernière bulle
                    CarAvatar {
                        visible: !screen.whatsapp && screen.group && message.last
                        x: CarTheme.pt(8)
                        anchors.bottom: parent.bottom
                        size: CarTheme.pt(28)
                        initials: message.modelData.initials
                    }

                    Rectangle {
                        id: bubble
                        readonly property real maxWidth: parent.width * 0.74
                        x: !screen.whatsapp && screen.group ? CarTheme.pt(42) : CarTheme.pt(screen.whatsapp ? 14 : 12)
                        width: Math.min(maxWidth, body.implicitWidth + 2 * padding)
                        height: (sender.visible ? sender.height : 0) + body.height + CarTheme.pt(screen.whatsapp ? 12 : 14)
                        readonly property real padding: CarTheme.pt(screen.whatsapp ? 8 : 12)
                        radius: CarTheme.pt(screen.whatsapp ? 8 : 18)
                        color: screen.whatsapp ? "#FFFFFF" : CarTheme.bubble

                        // Queue de Messages : en bas à gauche, sous la dernière bulle d'une suite
                        Canvas {
                            visible: !screen.whatsapp && message.last
                            x: -CarTheme.pt(5)
                            y: parent.height - CarTheme.pt(16)
                            width: CarTheme.pt(14)
                            height: CarTheme.pt(16)
                            onPaint: {
                                const c = getContext("2d")
                                const u = CarTheme.pt(1)
                                c.reset()
                                c.fillStyle = CarTheme.bubble
                                c.beginPath()
                                c.moveTo(7 * u, 0)
                                c.bezierCurveTo(7 * u, 9 * u, 4 * u, 13.5 * u, 0, 16 * u)
                                c.bezierCurveTo(5 * u, 16.5 * u, 9.5 * u, 15 * u, 13 * u, 12 * u)
                                c.lineTo(13 * u, 0)
                                c.closePath()
                                c.fill()
                            }
                        }
                        // Queue de WhatsApp : en haut à gauche, sur la première bulle d'une suite
                        Canvas {
                            visible: screen.whatsapp && message.first
                            x: -CarTheme.pt(7)
                            y: 0
                            width: CarTheme.pt(12)
                            height: CarTheme.pt(10)
                            onPaint: {
                                const c = getContext("2d")
                                const u = CarTheme.pt(1)
                                c.reset()
                                c.fillStyle = "#FFFFFF"
                                c.beginPath()
                                c.moveTo(1.5 * u, 0)
                                c.lineTo(12 * u, 0)
                                c.lineTo(12 * u, 10 * u)
                                c.lineTo(2 * u, 1.8 * u)
                                c.quadraticCurveTo(0, 0.4 * u, 1.5 * u, 0)
                                c.closePath()
                                c.fill()
                            }
                        }

                        // Groupe WhatsApp : le nom en couleur, dans la bulle
                        Text {
                            id: sender
                            visible: screen.whatsapp && message.first && message.modelData.sender !== ""
                            x: bubble.padding
                            y: CarTheme.pt(5)
                            width: bubble.maxWidth - 2 * bubble.padding
                            elide: Text.ElideRight
                            text: message.modelData.sender
                            color: screen.nameColor(message.modelData.sender)
                            font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(13) }
                        }
                        Text {
                            id: body
                            x: bubble.padding
                            y: (sender.visible ? sender.y + sender.height : 0) + CarTheme.pt(screen.whatsapp ? 5 : 7)
                            width: Math.min(implicitWidth, bubble.maxWidth - 2 * bubble.padding)
                            wrapMode: Text.Wrap
                            // WhatsApp : des espaces insécables gardent la place de l'heure au bout de la dernière ligne
                            text: message.modelData.text + (screen.whatsapp ? " ".repeat(12) : "")
                            color: CarTheme.label
                            font { family: CarTheme.text; pixelSize: CarTheme.pt(screen.whatsapp ? 16 : 17) }
                        }
                        Text {
                            visible: screen.whatsapp
                            anchors { right: parent.right; rightMargin: CarTheme.pt(7); bottom: parent.bottom; bottomMargin: CarTheme.pt(4) }
                            text: message.modelData.time
                            color: CarTheme.whatsappTime
                            font { family: CarTheme.text; pixelSize: CarTheme.pt(11); features: ({ "tnum": 1 }) }
                        }
                    }
                }
            }
        }
    }

    // En-tête : Messages centre la pastille et le nom ; WhatsApp les aligne à gauche, après le retour
    Rectangle {
        id: header
        anchors { top: parent.top; left: parent.left; right: parent.right }
        height: CarTheme.pt(screen.whatsapp ? 48 : 64)
        color: screen.whatsapp ? CarTheme.whatsappBar : CarTheme.card

        CarBackButton {
            objectName: "carPlayBack"  // pour les essais
            anchors { left: parent.left; leftMargin: CarTheme.pt(10); verticalCenter: parent.verticalCenter }
            onClicked: screen.backRequested()
        }
        Column {
            visible: !screen.whatsapp
            anchors.centerIn: parent
            spacing: CarTheme.pt(3)
            CarAvatar {
                anchors.horizontalCenter: parent.horizontalCenter
                size: CarTheme.pt(36)
                initials: screen.conversation.initials
            }
            // Le nom, dans une capsule de verre comme iOS 26
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(header.width - CarTheme.pt(110), title.implicitWidth + CarTheme.pt(14))
                height: CarTheme.pt(18)
                radius: height / 2
                color: CarTheme.grouped
                Text {
                    id: title
                    anchors.centerIn: parent
                    width: parent.width - CarTheme.pt(12)
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    text: screen.name
                    color: CarTheme.label
                    font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(11) }
                }
            }
        }
        Row {
            visible: screen.whatsapp
            anchors { left: parent.left; leftMargin: CarTheme.pt(52); right: parent.right; verticalCenter: parent.verticalCenter }
            spacing: CarTheme.pt(8)
            CarAvatar {
                size: CarTheme.pt(32)
                initials: screen.conversation.initials
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - CarTheme.pt(48)
                elide: Text.ElideRight
                text: screen.name
                color: CarTheme.label
                font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(17) }
            }
        }
        Rectangle {
            anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
            height: 1
            color: screen.whatsapp ? CarTheme.separator : "transparent"
        }
    }
}
