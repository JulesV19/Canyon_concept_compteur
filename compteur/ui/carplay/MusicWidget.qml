import QtQuick

// Widget « À l'écoute » : titre, artiste, progression, ⏮ ⏯ ⏭. Toucher le reste ouvre Musique.
CarWidget {
    id: widget
    required property var phone
    readonly property var music: phone.values.music ?? ({})
    readonly property bool hasTrack: (music.title ?? "") !== ""

    Column {
        id: titles
        anchors { top: parent.top; topMargin: CarTheme.pt(10); left: parent.left; right: parent.right }
        anchors { leftMargin: CarTheme.pt(14); rightMargin: CarTheme.pt(14) }

        Text {
            width: parent.width
            elide: Text.ElideRight
            text: widget.hasTrack ? widget.music.title : "Pas de lecture en cours"
            color: CarTheme.label
            font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(15) }
        }
        Text {
            width: parent.width
            elide: Text.ElideRight
            text: widget.hasTrack ? widget.music.artist || widget.music.album : "Musique"
            color: CarTheme.secondary
            font { family: CarTheme.text; pixelSize: CarTheme.pt(13) }
        }
    }

    // Progression, fine, sous le titre
    Rectangle {
        id: track
        anchors { top: titles.bottom; topMargin: CarTheme.pt(7); left: titles.left; right: titles.right }
        height: CarTheme.pt(3)
        radius: height / 2
        color: CarTheme.fill
        visible: widget.hasTrack && (widget.music.durationS ?? 0) > 0

        Rectangle {
            width: parent.width * Math.min(1, (widget.music.positionS ?? 0) / Math.max(1, widget.music.durationS ?? 1))
            height: parent.height
            radius: parent.radius
            color: CarTheme.gray
        }
    }

    Row {
        anchors { top: track.bottom; horizontalCenter: parent.horizontalCenter }
        spacing: CarTheme.pt(22)

        // Modèle fixe : les boutons ne sont pas refaits à chaque seconde (un toucher en cours serait perdu)
        Repeater {
            model: [
                { action: "previous", size: 27, path: CarTheme.backwardPath },
                { action: "toggle", size: 38, path: "" },
                { action: "next", size: 27, path: CarTheme.forwardPath }
            ]
            delegate: Item {
                id: button
                required property var modelData
                objectName: "carPlayWidget-" + modelData.action  // pour les essais
                width: CarTheme.pt(48)
                height: CarTheme.pt(44)
                opacity: !widget.hasTrack ? 0.3 : buttonTap.pressed ? 0.5 : 1

                CarGlyph {
                    anchors.centerIn: parent
                    size: CarTheme.pt(button.modelData.size)
                    path: button.modelData.path || CarTheme.playPause(widget.music.playing)
                }
                CarTap {
                    id: buttonTap
                    enabled: widget.hasTrack
                    onTapped: {
                        const action = button.modelData.action
                        if (action === "previous") widget.phone.previous()
                        else if (action === "next") widget.phone.next()
                        else widget.phone.playPause()
                    }
                }
            }
        }
    }
}
