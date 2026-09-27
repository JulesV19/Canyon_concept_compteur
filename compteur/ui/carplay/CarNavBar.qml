import QtQuick

// Barre de navigation d'une appli de CarPlay : retour à gauche, titre au centre
Item {
    id: bar
    property string title
    signal backRequested
    height: CarTheme.pt(44)

    CarBackButton {
        objectName: "carPlayBack"  // pour les essais
        anchors { left: parent.left; leftMargin: CarTheme.pt(10); verticalCenter: parent.verticalCenter }
        onClicked: bar.backRequested()
    }
    Text {
        anchors { centerIn: parent }
        width: parent.width - CarTheme.pt(2 * 52)
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: bar.title
        color: CarTheme.label
        font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(17) }
    }
}
