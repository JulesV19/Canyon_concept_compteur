import QtQuick

// Bouton − ou + : un appui change d'un cran ; maintenu, il défile (enregistré au lâcher)
Panel {
    id: stepButton
    property string glyph
    signal step
    signal done
    width: 52
    height: 52
    cut: 12
    woven: false
    ground: Theme.carbon
    color: press.pressed ? Theme.ash : Theme.carbonRaised

    Text {
        anchors.centerIn: parent
        text: stepButton.glyph
        color: press.pressed ? Theme.graphite : Theme.lacquer
        font { family: Theme.sans; pixelSize: 30; weight: Font.DemiBold }
    }
    TapHandler {
        id: press
        onPressedChanged: {
            if (pressed) {
                stepButton.step()
                repeat.interval = 450
                repeat.start()
            } else {
                repeat.stop()
                stepButton.done()
            }
        }
    }
    Timer {
        id: repeat
        repeat: true
        onTriggered: {
            stepButton.step()
            interval = 70
        }
    }
}
