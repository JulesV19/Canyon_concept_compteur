import QtQuick

// Nouveau message, en bandeau en bas de l'écran comme CarPlay : l'icône de l'appli, l'expéditeur, le texte. Il reste
// cinq secondes ; le toucher ouvre la conversation.
Rectangle {
    id: banner
    property var message: ({})
    property bool shown: false
    signal opened(string app, string name)
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
    opacity: tap.pressed ? 0.8 : 1

    function show(arrived) {
        message = arrived
        shown = true
        hideTimer.restart()
    }

    Timer {
        id: hideTimer
        interval: 5000
        onTriggered: banner.shown = false
    }
    Rectangle {
        z: -1
        anchors { fill: parent; topMargin: CarTheme.pt(2); bottomMargin: -CarTheme.pt(3) }
        radius: parent.radius
        color: "#26000000"
    }

    AppIcon {
        id: icon
        anchors { left: parent.left; leftMargin: CarTheme.pt(12); verticalCenter: parent.verticalCenter }
        width: CarTheme.pt(40)
        app: banner.message.app ?? "messages"
    }
    Text {
        id: name
        anchors { left: icon.right; leftMargin: CarTheme.pt(10); right: parent.right; rightMargin: CarTheme.pt(18) }
        y: CarTheme.pt(11)
        elide: Text.ElideRight
        text: banner.message.name ?? ""
        color: CarTheme.label
        font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(15) }
    }
    Text {
        anchors { left: name.left; right: parent.right; rightMargin: CarTheme.pt(18); top: name.bottom }
        elide: Text.ElideRight
        text: (banner.message.sender ? banner.message.sender + " : " : "") + (banner.message.text ?? "")
        color: CarTheme.label
        font { family: CarTheme.text; pixelSize: CarTheme.pt(15) }
    }
    CarTap {
        id: tap
        onTapped: {
            banner.shown = false
            banner.opened(banner.message.app, banner.message.name)
        }
    }
}
