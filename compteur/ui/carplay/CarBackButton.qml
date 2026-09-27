import QtQuick

// Retour de CarPlay 26 : un chevron dans un rond de « verre », en haut à gauche
Rectangle {
    id: button
    signal clicked
    width: CarTheme.pt(34)
    height: width
    radius: width / 2
    color: CarTheme.glass
    border { color: CarTheme.glassEdge; width: 1 }
    opacity: tap.pressed ? 0.6 : 1

    CarGlyph {
        anchors.centerIn: parent
        anchors.horizontalCenterOffset: -CarTheme.pt(1)
        size: CarTheme.pt(18)
        path: "M15 4 L7 12 L15 20"
        stroke: 3
    }
    CarTap {
        id: tap
        // Le doigt n'a pas besoin de viser le rond
        margin: CarTheme.pt(8)
        onTapped: button.clicked()
    }
}
