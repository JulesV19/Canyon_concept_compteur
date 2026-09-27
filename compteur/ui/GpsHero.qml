import QtQuick
import "Format.js" as Format

// Satellites utilisés en grand, état et précision
Panel {
    id: hero
    required property var view  // la page GPS : ses valeurs et son état
    scrolled: true
    height: 140

    Text {
        x: 22
        y: 14
        text: "SATELLITES"
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5 }
    }
    Text {
        id: used
        x: 18
        anchors { baseline: parent.top; baselineOffset: 120 }
        text: view.present ? view.values.used : "--"
        color: Theme.lacquer
        font { family: Theme.numbers; pixelSize: 92; weight: Font.Bold; italic: true; features: ({ "tnum": 1 }) }
    }
    Text {
        x: used.x + used.implicitWidth + 10
        anchors.baseline: used.baseline
        visible: view.present
        text: "/ " + view.values.inView
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
    }

    SlantRule {
        x: hero.width * 0.5
        y: 20
        height: 100
    }

    // État, puis précision estimée
    Item {
        x: hero.width * 0.5 + 34
        y: 16
        width: hero.width - x - 18
        height: 116

        StateChip {
            text: view.stateText
            dot: view.stateColor
        }
        Text {
            y: 48
            text: "PRÉCISION"
            color: Theme.ash
            font { family: Theme.numbers; pixelSize: 20; weight: Font.DemiBold; letterSpacing: 1.5 }
        }
        Text {
            id: accuracy
            anchors { baseline: parent.top; baselineOffset: 108 }
            text: view.located ? "≈ " + Format.number(view.values.accuracyM) : "--"
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 42; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            x: accuracy.implicitWidth + 5
            anchors.baseline: accuracy.baseline
            visible: view.located
            text: "m"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
        }
    }
}
