import QtQuick

// Carte « Sortie libre » de l'accueil : ton Ultimate au trait, pour partir sans parcours.
Panel {
    id: card
    property real draw: 1  // 0 → 1 : le vélo se dessine

    function ease(x) {
        return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2
    }
    function part(a, b) {
        return ease(Math.max(0, Math.min(1, (draw - a) / (b - a))))
    }

    Text {
        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 24; rightMargin: 24 + card.cutX; topMargin: 18 }
        text: "Sortie libre"
        color: Theme.lacquer
        font { family: Theme.sans; pixelSize: 28; weight: Font.DemiBold }
    }

    BikeLine {
        x: 36
        y: 64
        width: parent.width - 72
        height: parent.height - 64 - 70
        wheels: card.part(0, 0.7)
        frame: card.part(0.1, 0.85)
        parts: card.part(0.45, 1)
    }

    Text {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 24; rightMargin: 24; bottomMargin: 22 }
        text: "Ta trace s'affiche sur la carte."
        color: Theme.ash
        wrapMode: Text.WordWrap
        font { family: Theme.sans; pixelSize: 20; weight: Font.DemiBold }
    }
}
