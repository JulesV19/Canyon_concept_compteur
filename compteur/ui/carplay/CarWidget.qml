import QtQuick

// Widget du tableau de bord de CarPlay 26 : une carte de verre clair aux grands coins arrondis. Toucher la carte (hors
// de ses boutons) ouvre ce qu'elle résume.
Rectangle {
    id: widget
    signal opened
    radius: CarTheme.pt(22)
    color: CarTheme.glass
    border { color: CarTheme.glassEdge; width: 1 }
    opacity: tap.pressed ? 0.75 : 1

    CarTap {
        id: tap
        onTapped: widget.opened()
    }
}
