import QtQuick

// Pastille d'un contact, comme iOS : initiales blanches sur un dégradé gris ; sans initiales (un numéro), la silhouette
Rectangle {
    id: avatar
    property string initials
    property real size: CarTheme.pt(40)
    width: size
    height: size
    radius: size / 2
    gradient: Gradient {
        GradientStop { position: 0; color: "#A5ABB9" }
        GradientStop { position: 1; color: "#858994" }
    }

    Text {
        anchors.centerIn: parent
        visible: avatar.initials !== ""
        text: avatar.initials
        color: "white"
        font { family: CarTheme.textSemibold; pixelSize: avatar.size * 0.42 }
    }
    CarGlyph {
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom }
        visible: avatar.initials === ""
        size: avatar.size * 0.8
        color: "white"
        path: "M12 12.5 A4.6 4.6 0 1 0 12 3.3 A4.6 4.6 0 1 0 12 12.5 Z M3 24 C3 18.4 7 15 12 15 C17 15 21 18.4 21 24 Z"
    }
}
