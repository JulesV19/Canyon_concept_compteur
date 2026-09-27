import QtQuick

// Bouton à maintenir : une barre laque se remplit pendant l'appui, et l'action part quand elle est pleine.
// Évite les fausses manœuvres (gants, pavés).
Panel {
    id: button
    property string text
    property int holdMs: 1000
    property real progress: 0
    property color fillColor: Theme.lacquer  // couleur de la barre qui se remplit
    signal activated
    signal interrupted                       // relâché trop tôt

    color: Theme.carbonRaised
    woven: false
    cut: 18

    Rectangle {
        id: fill
        width: parent.width * button.progress
        height: parent.height
        color: button.fillColor
    }
    Text {
        anchors.centerIn: parent
        text: button.text
        color: Theme.lacquer
        font { family: Theme.sans; pixelSize: 26; weight: Font.DemiBold }
    }
    // Le même texte en graphite, sur la partie remplie
    Item {
        width: fill.width
        height: parent.height
        clip: true
        Text {
            x: (button.width - width) / 2
            anchors.verticalCenter: parent.verticalCenter
            text: button.text
            color: Theme.graphite
            font { family: Theme.sans; pixelSize: 26; weight: Font.DemiBold }
        }
    }

    NumberAnimation {
        id: charge
        target: button
        property: "progress"
        to: 1
        onFinished: {
            if (button.progress >= 1) {
                button.progress = 0
                button.activated()
            }
        }
    }
    NumberAnimation {
        id: release
        target: button
        property: "progress"
        to: 0
        duration: 200
    }

    TapHandler {
        onPressedChanged: {
            if (pressed) {
                release.stop()
                charge.duration = button.holdMs * (1 - button.progress)
                charge.start()
            } else if (charge.running) {
                charge.stop()
                release.start()
                button.interrupted()
            }
        }
    }
}
