import QtQuick
import QtQuick.Shapes

// Bas du résumé : les tirets des pages, puis Supprimer (à maintenir) et Enregistrer, ou Retour pour une sortie
// rouverte depuis Mes sorties
Item {
    id: actions
    required property var sheet   // SummaryPage : son état (enregistrement...) et ses signaux
    required property int count  // pages du résumé
    required property int currentIndex
    height: dashes.height + 16 + 68 + 18

    Dashes {
        id: dashes
        anchors.horizontalCenter: parent.horizontalCenter
        y: discardButton.y - 16 - height
        count: actions.count
        currentIndex: actions.currentIndex
        opacity: holdHint.visible || saveFailure.visible ? 0 : 1
    }

    // Enregistrement refusé (carte pleine...) : la raison, à la place des tirets. Enregistrer réessaie ; Supprimer reste
    // possible.
    Text {
        id: saveFailure
        anchors { horizontalCenter: parent.horizontalCenter; verticalCenter: dashes.verticalCenter }
        width: parent.width - 32
        visible: sheet.saveError !== "" && !sheet.busy && !holdHint.visible
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: "Pas enregistrée : " + sheet.saveError
        color: Theme.danger
        font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold }
    }

    // Un simple appui sur Supprimer rappelle qu'il faut maintenir
    Text {
        id: holdHint
        anchors { horizontalCenter: parent.horizontalCenter; verticalCenter: dashes.verticalCenter }
        opacity: 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 200 } }
        text: "Maintenir pour supprimer"
        color: Theme.danger
        font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold }

        Timer {
            id: hideHint
            interval: 2000
            onTriggered: holdHint.opacity = 0
        }
    }

    HoldButton {
        id: discardButton
        x: 16
        y: parent.height - height - 18
        width: 150
        height: 68
        text: "Supprimer"
        fillColor: Theme.danger
        enabled: !sheet.busy
        onActivated: sheet.discard()
        onInterrupted: {
            holdHint.opacity = 1
            hideHint.restart()
        }
    }

    // Enregistrer, en laque (fin de sortie), ou Retour (sortie rouverte depuis Mes sorties)
    Panel {
        id: mainButton
        readonly property color ink: sheet.saved && !mainTap.pressed ? Theme.lacquer : Theme.graphite
        x: discardButton.x + discardButton.width + 10
        y: discardButton.y
        width: parent.width - x - 16
        height: 68
        color: sheet.saved ? (mainTap.pressed ? Theme.ash : Theme.carbonRaised)
                          : (mainTap.pressed ? Qt.darker(Theme.lacquer, 1.15) : Theme.lacquer)
        woven: false
        outline: sheet.saved ? Theme.hairline : "transparent"
        scale: mainTap.pressed ? 0.97 : 1
        Behavior on scale { NumberAnimation { duration: 120 } }

        Row {
            anchors.centerIn: parent
            spacing: 12

            Item {
                width: 20
                height: 22
                anchors.verticalCenter: parent.verticalCenter

                // Flèche vers le bas (enregistrer), puis coche une fois la sortie enregistrée ; chevron pour Retour
                Shape {
                    anchors.fill: parent
                    visible: !waiting.visible
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        strokeColor: mainButton.ink
                        strokeWidth: 3
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.RoundJoin
                        PathSvg {
                            path: sheet.saved ? "M 14 2 L 5 11 L 14 20"
                                : sheet.stored ? "M 2 12 L 8 18 L 19 5" : "M 10 1 L 10 14 M 4 9 L 10 15 L 16 9 M 2 20 L 18 20"
                        }
                    }
                }
                // Anneau qui tourne pendant une écriture qui dure, comme l'attente du GPS sur l'accueil
                Shape {
                    id: waiting
                    anchors.fill: parent
                    visible: sheet.saving && sheet.slow
                    preferredRendererType: Shape.CurveRenderer
                    RotationAnimation on rotation {
                        running: waiting.visible
                        from: 0
                        to: 360
                        duration: 900
                        loops: Animation.Infinite
                    }
                    ShapePath {
                        strokeColor: mainButton.ink
                        strokeWidth: 3
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        PathAngleArc { centerX: 10; centerY: 11; radiusX: 8; radiusY: 8; startAngle: 0; sweepAngle: 270 }
                    }
                }
            }
            Text {
                text: sheet.saved ? "Retour" : sheet.stored ? "Enregistrée"
                    : sheet.saving && sheet.slow ? "Enregistrement…" : "Enregistrer"
                color: mainButton.ink
                font { family: Theme.sans; pixelSize: 28; weight: Font.DemiBold }
            }
        }
        TapHandler {
            id: mainTap
            onTapped: sheet.saved ? sheet.back() : sheet.requestSave()
        }
    }
}
