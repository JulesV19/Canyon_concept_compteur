import QtQuick

// État d'un capteur : nom, pastille (verte : prêt ; ambre qui clignote : pas encore) et valeur
Item {
    id: sensor
    property string label
    property string value
    property string unit
    property bool ready
    property bool numeric: false
    property int beat  // numéro de la mise à jour : la pastille ambre clignote au rythme des secondes

    Text {
        text: sensor.label
        color: Theme.ash
        font { family: Theme.numbers; pixelSize: 22; weight: Font.DemiBold; letterSpacing: 1.5; capitalization: Font.AllUppercase }
    }
    Row {
        anchors.bottom: parent.bottom
        spacing: 8

        Rectangle {
            id: dot
            anchors.verticalCenter: valueText.verticalCenter
            width: 11
            height: 11
            radius: 5.5
            color: sensor.ready ? Theme.ok : Theme.warning
            opacity: !sensor.ready && sensor.beat % 2 === 1 ? 0.25 : 1
        }
        Text {
            id: valueText
            text: sensor.value
            color: Theme.lacquer
            font {
                family: sensor.numeric ? Theme.numbers : Theme.sans
                pixelSize: sensor.numeric ? 40 : 28
                weight: Font.DemiBold
                italic: sensor.numeric
                features: ({ "tnum": 1 })
            }
        }
        Text {
            anchors.baseline: valueText.baseline
            text: sensor.unit
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
        }
    }
}
