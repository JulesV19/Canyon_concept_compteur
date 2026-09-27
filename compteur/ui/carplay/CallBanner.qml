import QtQuick

// Appel entrant, en bandeau compact en bas de l'écran comme CarPlay 26 : la page reste visible au-dessus. Refuser
// (rouge) ou Accepter (vert) ; l'iPhone décide, le bandeau part quand il ne sonne plus.
Rectangle {
    id: banner
    required property var phone
    readonly property var call: phone.values.call ?? null
    readonly property bool shown: call !== null
    height: CarTheme.pt(64)
    radius: CarTheme.pt(28)
    color: CarTheme.banner
    border { color: CarTheme.glassEdge; width: 1 }
    // Il monte du bas de l'écran, comme sur CarPlay (un instant court) ; il repart d'un coup
    property real entry: 0
    onShownChanged: {
        rise.stop()
        if (shown)
            rise.restart()
        else
            entry = 0
    }
    NumberAnimation { id: rise; target: banner; property: "entry"; from: 0; to: 1; duration: 300; easing.type: Easing.OutCubic }
    visible: entry > 0
    transform: Translate { y: (1 - banner.entry) * (banner.height + CarTheme.pt(24)) }

    // Ombre douce sous le verre
    Rectangle {
        z: -1
        anchors { fill: parent; topMargin: CarTheme.pt(2); bottomMargin: -CarTheme.pt(3) }
        radius: parent.radius
        color: "#26000000"
    }

    Column {
        anchors { left: parent.left; leftMargin: CarTheme.pt(20); right: parent.right }
        anchors.rightMargin: CarTheme.pt(10 + 40 + 8 + 40 + 8)
        anchors.verticalCenter: parent.verticalCenter

        Text {
            width: parent.width
            elide: Text.ElideRight
            text: banner.call?.app === "whatsapp" ? "Audio WhatsApp" : "iPhone"
            color: CarTheme.secondary
            font { family: CarTheme.text; pixelSize: CarTheme.pt(13) }
        }
        Text {
            width: parent.width
            elide: Text.ElideRight
            text: banner.call?.name ?? ""
            color: CarTheme.label
            font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(17) }
        }
    }

    Repeater {
        model: [{ positive: false }, { positive: true }]
        delegate: Rectangle {
            id: button
            required property var modelData
            required property int index
            objectName: modelData.positive ? "carPlayAnswer" : "carPlayDecline"  // pour les essais
            x: banner.width - CarTheme.pt(10) - (2 - index) * width - (1 - index) * CarTheme.pt(8)
            anchors.verticalCenter: parent.verticalCenter
            width: CarTheme.pt(40)
            height: width
            radius: width / 2
            color: modelData.positive ? CarTheme.green : CarTheme.red
            opacity: buttonTap.pressed ? 0.6 : 1

            CarGlyph {
                anchors.centerIn: parent
                size: CarTheme.pt(22)
                color: "white"
                // Combiné de phone.fill ; raccroché (phone.down.fill) : le même, tourné
                rotation: button.modelData.positive ? 0 : 135
                path: "M6.6 2.6 C7.3 2.4 8 2.7 8.3 3.4 L9.8 6.8 C10.1 7.5 9.9 8.2 9.3 8.6 L7.9 9.6 C8.9 11.8 12 14.9 14.4 16.1 L15.4 14.7 C15.8 14.1 16.6 13.9 17.3 14.2 L20.6 15.7 C21.3 16 21.6 16.7 21.4 17.4 L20.9 19.5 C20.6 20.6 19.6 21.4 18.5 21.3 C10.3 20.6 3.4 13.7 2.7 5.5 C2.6 4.4 3.4 3.4 4.5 3.1 Z"
            }
            CarTap {
                id: buttonTap
                onTapped: button.modelData.positive ? banner.phone.answer() : banner.phone.decline()
            }
        }
    }
}
