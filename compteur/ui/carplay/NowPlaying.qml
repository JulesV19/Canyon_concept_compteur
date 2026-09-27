import QtQuick

// « À l'écoute » de CarPlay : pochette, titre, artiste, progression, ⏮ ⏯ ⏭ et volume. L'iPhone n'envoie pas la
// pochette en Bluetooth (AMS) : on montre celle d'un morceau sans pochette, comme Musique.
Item {
    id: screen
    required property var phone          // PhoneModel : commandes
    readonly property var music: phone.values.music ?? ({})
    readonly property bool hasTrack: (music.title ?? "") !== ""
    signal backRequested

    function clock(seconds) {
        const s = Math.max(0, Math.round(seconds))
        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0")
    }

    CarBackButton {
        objectName: "carPlayBack"  // pour les essais
        anchors { left: parent.left; leftMargin: CarTheme.pt(10); top: parent.top; topMargin: CarTheme.pt(4) }
        onClicked: screen.backRequested()
    }

    // Pochette absente : le carré gris et la note de Musique
    Rectangle {
        id: artwork
        anchors { top: parent.top; topMargin: CarTheme.pt(6); horizontalCenter: parent.horizontalCenter }
        width: CarTheme.pt(112)
        height: width
        radius: CarTheme.pt(10)
        gradient: Gradient {
            GradientStop { position: 0; color: "#E5E5EA" }
            GradientStop { position: 1; color: "#C7C7CC" }
        }
        border { color: CarTheme.glassEdge; width: 1 }

        CarGlyph {
            anchors.centerIn: parent
            size: parent.width * 0.5
            color: "#99FFFFFF"
            path: "M20 2.5 V15.6 A3.4 2.9 0 1 1 18 13.1 V7.2 L10 8.9 V18.6 A3.4 2.9 0 1 1 8 16.1 V5.2 Z"
        }
    }

    Text {
        id: title
        anchors { top: artwork.bottom; topMargin: CarTheme.pt(10); left: parent.left; right: parent.right }
        anchors { leftMargin: CarTheme.pt(16); rightMargin: CarTheme.pt(16) }
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: screen.hasTrack ? screen.music.title : "Pas de lecture en cours"
        color: CarTheme.label
        font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(17) }
    }
    Text {
        id: artist
        anchors { top: title.bottom; topMargin: CarTheme.pt(1); left: title.left; right: title.right }
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: [screen.music.artist, screen.music.album].filter(s => s).join(" — ")
        color: CarTheme.secondary
        font { family: CarTheme.text; pixelSize: CarTheme.pt(15) }
    }

    // Progression : une piste fine, le temps écoulé à gauche, le temps restant à droite
    Item {
        id: progress
        readonly property real duration: screen.music.durationS ?? 0
        readonly property real position: screen.music.positionS ?? 0
        anchors { top: artist.bottom; topMargin: CarTheme.pt(10); left: parent.left; right: parent.right }
        anchors { leftMargin: CarTheme.pt(20); rightMargin: CarTheme.pt(20) }
        height: CarTheme.pt(4 + 4 + 13)
        visible: screen.hasTrack && duration > 0

        Rectangle {
            id: track
            width: parent.width
            height: CarTheme.pt(4)
            radius: height / 2
            color: CarTheme.fill

            Rectangle {
                width: parent.width * Math.min(1, progress.position / Math.max(1, progress.duration))
                height: parent.height
                radius: parent.radius
                color: CarTheme.gray
            }
        }
        Text {
            anchors { left: parent.left; bottom: parent.bottom }
            text: screen.clock(progress.position)
            color: CarTheme.secondary
            font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(11); features: ({ "tnum": 1 }) }
        }
        Text {
            anchors { right: parent.right; bottom: parent.bottom }
            text: "-" + screen.clock(progress.duration - progress.position)
            color: CarTheme.secondary
            font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(11); features: ({ "tnum": 1 }) }
        }
    }

    // Aléatoire, ⏮ ⏯ ⏭, répétition ; un mode actif prend la couleur de Musique sur une pastille claire
    Row {
        id: controls
        anchors { top: progress.bottom; topMargin: CarTheme.pt(4); horizontalCenter: parent.horizontalCenter }
        spacing: CarTheme.pt(2)

        // Modèle fixe : les boutons ne sont pas refaits à chaque seconde (un toucher en cours serait perdu)
        Repeater {
            model: [
                { action: "shuffle", size: 20, stroke: 2,
                  path: "M3 7 H6.5 C10.5 7 12.5 17 16.5 17 H20 M3 17 H6.5 C8.4 17 9.7 15.3 10.7 13.4 M12.9 10.2 C13.9 8.4 15 7 16.5 7 H20 M17.5 4.5 L20 7 L17.5 9.5 M17.5 14.5 L20 17 L17.5 19.5" },
                { action: "previous", size: 30, path: CarTheme.backwardPath },
                { action: "toggle", size: 48, path: "" },
                { action: "next", size: 30, path: CarTheme.forwardPath },
                { action: "repeat", size: 20, stroke: 2,
                  path: "M4 11.5 V9.5 A3 3 0 0 1 7 6.5 H19 M16.5 4 L19 6.5 L16.5 9 M20 12.5 V14.5 A3 3 0 0 1 17 17.5 H5 M7.5 15 L5 17.5 L7.5 20" }
            ]
            delegate: Item {
                id: button
                required property var modelData
                readonly property bool small: modelData.stroke !== undefined
                readonly property bool on: modelData.action === "shuffle" ? (screen.music.shuffle ?? 0) > 0
                    : modelData.action === "repeat" && (screen.music.repeat ?? 0) > 0
                objectName: "carPlay-" + modelData.action  // pour les essais
                width: CarTheme.pt(small ? 34 : 52)
                height: CarTheme.pt(48)
                opacity: !screen.hasTrack ? 0.3 : buttonTap.pressed ? 0.5 : 1

                Rectangle {
                    anchors.centerIn: parent
                    visible: button.on
                    width: CarTheme.pt(30)
                    height: width
                    radius: CarTheme.pt(8)
                    color: CarTheme.fill
                }
                CarGlyph {
                    anchors.centerIn: parent
                    size: CarTheme.pt(button.modelData.size)
                    stroke: button.modelData.stroke ?? 0
                    color: button.on ? CarTheme.musicAccent
                        : button.small ? CarTheme.secondary : CarTheme.label
                    path: button.modelData.path || CarTheme.playPause(screen.music.playing)
                }
                // Répéter un seul morceau : le « 1 » de Musique
                Text {
                    visible: button.modelData.action === "repeat" && screen.music.repeat === 1
                    anchors { centerIn: parent; horizontalCenterOffset: CarTheme.pt(0.5); verticalCenterOffset: CarTheme.pt(0.5) }
                    text: "1"
                    color: CarTheme.musicAccent
                    font { family: CarTheme.textSemibold; pixelSize: CarTheme.pt(8) }
                }
                CarTap {
                    id: buttonTap
                    enabled: screen.hasTrack
                    onTapped: {
                        const action = button.modelData.action
                        if (action === "previous") screen.phone.previous()
                        else if (action === "next") screen.phone.next()
                        else if (action === "shuffle") screen.phone.shuffle()
                        else if (action === "repeat") screen.phone.repeat()
                        else screen.phone.playPause()
                    }
                }
            }
        }
    }

    // Volume de l'iPhone : le haut-parleur de gauche baisse, celui de droite monte
    Item {
        id: volume
        anchors { top: controls.bottom; topMargin: CarTheme.pt(4); left: parent.left; right: parent.right }
        anchors { leftMargin: CarTheme.pt(16); rightMargin: CarTheme.pt(16) }
        height: CarTheme.pt(28)
        visible: screen.hasTrack

        CarGlyph {
            id: quiet
            anchors { left: parent.left; verticalCenter: parent.verticalCenter }
            size: CarTheme.pt(18)
            color: downTap.pressed ? CarTheme.label : CarTheme.gray
            path: "M3 9 H7 L12 4.5 V19.5 L7 15 H3 Z"
            CarTap { id: downTap; margin: CarTheme.pt(10); onTapped: screen.phone.volumeDown() }
        }
        Rectangle {
            anchors { left: quiet.right; right: loud.left; leftMargin: CarTheme.pt(8); rightMargin: CarTheme.pt(8) }
            anchors.verticalCenter: parent.verticalCenter
            height: CarTheme.pt(4)
            radius: height / 2
            color: CarTheme.fill

            Rectangle {
                width: parent.width * Math.min(1, Math.max(0, screen.music.volume ?? 0))
                height: parent.height
                radius: parent.radius
                color: CarTheme.gray
            }
        }
        Item {
            id: loud
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            width: CarTheme.pt(18)
            height: CarTheme.pt(18)

            CarGlyph {
                size: CarTheme.pt(18)
                color: upTap.pressed ? CarTheme.label : CarTheme.gray
                path: "M1 9 H4.5 L9 4.5 V19.5 L4.5 15 H1 Z"
            }
            CarGlyph {
                size: CarTheme.pt(18)
                color: upTap.pressed ? CarTheme.label : CarTheme.gray
                stroke: 1.8
                path: "M12.5 9 Q14.5 12 12.5 15 M16 6 Q20 12 16 18 M19.5 3.5 Q25 12 19.5 20.5"
            }
            CarTap { id: upTap; margin: CarTheme.pt(10); onTapped: screen.phone.volumeUp() }
        }
    }
}
