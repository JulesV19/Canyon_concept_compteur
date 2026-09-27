import QtQuick

// Aucun iPhone : comment l'associer. Une fois associé, il se reconnecte seul dès que le compteur est allumé.
Item {
    id: connect
    property bool available: true  // faux : pas de Bluetooth sur ce compteur

    Column {
        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: CarTheme.pt(18) }
        spacing: CarTheme.pt(10)

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: connect.available ? "Connectez votre iPhone" : "Bluetooth indisponible"
            color: CarTheme.label
            font { family: CarTheme.displayBold; pixelSize: CarTheme.pt(22) }
        }
        Rectangle {
            visible: connect.available
            width: parent.width
            height: steps.implicitHeight + CarTheme.pt(20)
            radius: CarTheme.pt(14)
            color: CarTheme.glass
            border { color: CarTheme.glassEdge; width: 1 }

            Column {
                id: steps
                x: CarTheme.pt(12)
                y: CarTheme.pt(10)
                width: parent.width - 2 * x
                spacing: CarTheme.pt(8)

                Repeater {
                    model: ["Sur l'iPhone : Réglages, puis Bluetooth.",
                            "Touchez « Compteur » et associez.",
                            "Autorisez le partage des notifications."]
                    delegate: Row {
                        required property string modelData
                        required property int index
                        spacing: CarTheme.pt(8)

                        Rectangle {
                            width: CarTheme.pt(20)
                            height: width
                            radius: width / 2
                            color: CarTheme.blue

                            Text {
                                anchors.centerIn: parent
                                text: index + 1
                                color: "white"
                                font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(12) }
                            }
                        }
                        Text {
                            width: steps.width - CarTheme.pt(28)
                            wrapMode: Text.WordWrap
                            text: modelData
                            color: CarTheme.label
                            font { family: CarTheme.text; pixelSize: CarTheme.pt(14) }
                        }
                    }
                }
            }
        }
    }
}
