import QtQuick
import QtQuick.Window

// Icône d'une appli, en squircle comme sur CarPlay, avec sa pastille rouge de non-lus. L'image vient du Mac
// (apple/…png, hors dépôt) ; sans elle, une icône de sa couleur avec un glyphe.
Item {
    id: icon
    property string app  // clé de CarTheme.apps
    property int badge: 0
    readonly property var info: CarTheme.apps[app] ?? { label: "", file: "", color: "#8E8E93", glyph: "" }
    width: CarTheme.pt(60)
    height: width

    Image {
        id: image
        anchors.fill: parent
        source: icon.info.file ? Qt.resolvedUrl("apple/" + icon.info.file + ".png") : ""
        // Décodée à la taille affichée : rien à réduire à chaque image
        sourceSize { width: icon.width * Screen.devicePixelRatio; height: icon.height * Screen.devicePixelRatio }
        smooth: true
    }
    Rectangle {
        anchors.fill: parent
        visible: image.status !== Image.Ready
        radius: width * 0.225
        color: icon.info.color

        Text {
            anchors.centerIn: parent
            text: icon.info.glyph
            color: "white"
            font { family: CarTheme.textSemibold; pixelSize: parent.width * 0.5 }
        }
    }

    // Pastille : un rond rouge, qui s'allonge au-delà de 9
    Rectangle {
        visible: icon.badge > 0
        x: icon.width - width * 0.7
        y: -height * 0.3
        height: Math.round(icon.width * 0.36)  // 21 pt pour une icône de 60
        width: Math.max(height, count.implicitWidth + height * 0.55)
        radius: height / 2
        color: CarTheme.red

        Text {
            id: count
            anchors.centerIn: parent
            text: icon.badge
            color: "white"
            font { family: CarTheme.textSemibold; pixelSize: parent.height * 0.66; features: ({ "tnum": 1 }) }
        }
    }
}
