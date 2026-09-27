import QtQuick

// Widget du dernier message (Messages ou WhatsApp, le plus récent) : pastille, nom, texte ; le toucher ouvre la
// conversation. Sans message : un rappel discret.
CarWidget {
    id: widget
    required property var phone
    signal conversationRequested(string app, string name)
    // Le plus récent des deux : chaque liste a le sien en tête, trié par l'iPhone ; à égalité d'heure, Messages
    readonly property var latest: {
        const messages = phone.messages[0]
        const whatsapp = phone.whatsapp[0]
        if (!messages && !whatsapp)
            return null
        if (!whatsapp || (messages && messages.sortKey >= whatsapp.sortKey))
            return { app: "messages", item: messages }
        return { app: "whatsapp", item: whatsapp }
    }
    onOpened: if (latest) conversationRequested(latest.app, latest.item.name)

    Row {
        x: CarTheme.pt(14)
        y: CarTheme.pt(11)
        spacing: CarTheme.pt(5)
        AppIcon {
            width: CarTheme.pt(16)
            app: widget.latest ? widget.latest.app : "messages"
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: widget.latest ? CarTheme.apps[widget.latest.app].label + " · " + widget.latest.item.time : "Messages"
            color: CarTheme.secondary
            font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(12) }
        }
    }
    CarAvatar {
        id: avatar
        visible: widget.latest !== null
        x: CarTheme.pt(14)
        y: CarTheme.pt(36)
        size: CarTheme.pt(40)
        initials: widget.latest ? widget.latest.item.initials : ""
    }
    Column {
        visible: widget.latest !== null
        anchors { left: avatar.right; leftMargin: CarTheme.pt(10); right: parent.right; rightMargin: CarTheme.pt(14) }
        y: CarTheme.pt(33)
        Text {
            width: parent.width
            elide: Text.ElideRight
            text: widget.latest ? widget.latest.item.name : ""
            color: CarTheme.label
            font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(15) }
        }
        Text {
            width: parent.width
            maximumLineCount: 2
            wrapMode: Text.Wrap
            elide: Text.ElideRight
            text: widget.latest ? (widget.latest.item.sender ? widget.latest.item.sender + " : " : "") + widget.latest.item.text : ""
            color: CarTheme.secondary
            font { family: CarTheme.text; pixelSize: CarTheme.pt(13) }
        }
    }
    Text {
        visible: widget.latest === null
        anchors.centerIn: parent
        text: "Aucun message"
        color: CarTheme.secondary
        font { family: CarTheme.text; pixelSize: CarTheme.pt(15) }
    }
}
