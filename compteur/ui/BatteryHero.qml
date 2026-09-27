import QtQuick
import "Format.js" as Format

// Charge en grand, état et autonomie, puis la batterie en segments penchés
Panel {
    id: hero
    required property var view  // la page Batterie : ses valeurs et son état
    x: 16
    width: parent.width - 32
    height: 164

    Text {
        x: 22
        y: 12
        text: "CHARGE"
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5 }
    }
    Text {
        id: whole
        x: 18
        anchors { baseline: parent.top; baselineOffset: 112 }
        text: view.present ? Math.floor(view.tenths / 10) : "--"
        color: Theme.lacquer
        font { family: Theme.numbers; pixelSize: 100; weight: Font.Bold; italic: true; features: ({ "tnum": 1 }) }
    }
    Text {
        id: tenth
        x: whole.x + whole.implicitWidth + 2
        anchors.baseline: whole.baseline
        visible: view.present
        text: "," + view.tenths % 10
        color: Theme.lacquer
        font { family: Theme.numbers; pixelSize: 42; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
    }
    Text {
        x: (view.present ? tenth.x + tenth.implicitWidth : whole.x + whole.implicitWidth) + 6
        anchors.baseline: whole.baseline
        text: "%"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 26; weight: Font.DemiBold }
    }

    SlantRule {
        x: hero.width * 0.52
        y: 18
        height: 96
    }

    // État, puis autonomie (en décharge) ou temps avant la charge complète
    Item {
        x: hero.width * 0.52 + 26
        y: 16
        width: hero.width - x - 18
        height: 110

        StateChip {
            text: view.stateText
            dot: view.stateColor
            charging: view.state === "charge"
        }
        Text {
            y: 46
            text: view.state === "charge" ? "PLEINE DANS" : "AUTONOMIE"
            color: Theme.ash
            font { family: Theme.numbers; pixelSize: 20; weight: Font.DemiBold; letterSpacing: 1.5 }
        }
        Text {
            anchors { baseline: parent.top; baselineOffset: 102 }
            text: Format.span(view.state === "charge" ? view.values.fullInS : view.values.autonomyS)
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 42; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
    }

    // Dix cases de 10 %
    SlantedBar {
        x: 22
        y: 128
        width: hero.width - 44
        height: 18
        count: 10
        progress: view.percent / 100
        color: view.fillColor
    }
}
