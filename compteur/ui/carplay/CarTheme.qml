pragma Singleton
import QtQuick

// CarPlay 26, thème clair. Les mesures d'Apple sont en points : CarPlay s'affiche en @2x sur les écrans de 800 × 480,
// donc 1 pt = 2 px ici (l'écran fait 240 × 320 pt). SF Pro vient du Mac (tools/carplay/ressources.py) ; sans elle, Qt
// retombe sur Barlow, la police de l'appli.
QtObject {
    function pt(value) {
        return 2 * value
    }
    // Commandes de lecture : play.fill, pause.fill, backward.fill et forward.fill des SF Symbols, relevés sur le rendu
    // du Mac à 1000 pt (coins arrondis en arcs, rayons mesurés), à la même échelle ; centrés comme Apple centre
    // l'image du symbole, marges comprises (d'où ▶ et ⏭ un peu à droite : le centrage optique)
    readonly property string playPath: "M6.38 5.8 A1.19 1.19 0 0 1 8.17 4.78 L18.96 11.09 A1.04 1.04 0 0 1 18.96 12.89 L8.17 19.19 A1.19 1.19 0 0 1 6.38 18.17 Z"
    readonly property string pausePath: "M6.65 5.81 A1.08 1.08 0 0 1 7.73 4.73 H9.9 A1.08 1.08 0 0 1 10.98 5.81 V18.18 A1.08 1.08 0 0 1 9.9 19.26 H7.73 A1.08 1.08 0 0 1 6.65 18.18 Z M13.02 5.81 A1.08 1.08 0 0 1 14.1 4.73 H16.27 A1.08 1.08 0 0 1 17.36 5.81 V18.18 A1.08 1.08 0 0 1 16.27 19.26 H14.1 A1.08 1.08 0 0 1 13.02 18.18 Z"
    readonly property string backwardPath: "M23 17.52 A1.16 1.16 0 0 1 21.25 18.52 L11.59 12.87 A1.03 1.03 0 0 1 11.59 11.1 L21.25 5.45 A1.16 1.16 0 0 1 23 6.45 Z M11.08 17.51 A1.16 1.16 0 0 1 9.33 18.51 L-0.33 12.86 A1.01 1.01 0 0 1 -0.33 11.12 L9.33 5.46 A1.16 1.16 0 0 1 11.08 6.46 Z"
    readonly property string forwardPath: "M1 6.45 A1.16 1.16 0 0 1 2.75 5.45 L12.41 11.1 A1.03 1.03 0 0 1 12.41 12.87 L2.75 18.52 A1.16 1.16 0 0 1 1 17.52 Z M12.92 6.46 A1.16 1.16 0 0 1 14.67 5.46 L24.33 11.12 A1.01 1.01 0 0 1 24.33 12.86 L14.67 18.51 A1.16 1.16 0 0 1 12.92 17.51 Z"
    // ⏸ pendant la lecture, ▶ sinon
    function playPause(playing) {
        return playing ? pausePath : playPath
    }

    // Une famille par graisse (voir ressources.py) : ne pas passer par font.weight
    readonly property string text: "SF Pro Text"                        // jusqu'à 19 pt, comme iOS
    readonly property string textSemibold: "SF Pro Text Semibold"
    readonly property string displaySemibold: "SF Pro Display Semibold"  // au-delà : titres
    readonly property string displayBold: "SF Pro Display Bold"

    // Couleurs système d'iOS, apparence claire
    readonly property color label: "#000000"
    readonly property color secondary: "#993C3C43"   // #3C3C43 à 60 %
    readonly property color tertiary: "#4D3C3C43"    // à 30 %
    readonly property color separator: "#4A3C3C43"   // à 29 %
    readonly property color fill: "#1F787880"        // fond des boutons ronds, des pistes
    readonly property color grouped: "#F2F2F7"       // fond des listes
    readonly property color card: "#FFFFFF"
    readonly property color glass: "#C7FFFFFF"       // « verre » de CarPlay 26, sans le flou (trop cher pour le Pi)
    readonly property color glassEdge: "#14000000"
    readonly property color banner: "#FAFAFC"        // bandeaux : opaques, les chiffres de la sortie ne transparaissent pas
    readonly property color blue: "#007AFF"
    readonly property color red: "#FF3B30"
    readonly property color green: "#34C759"
    readonly property color gray: "#8E8E93"
    readonly property color bubble: "#E9E9EB"        // bulle d'un message reçu
    readonly property color musicAccent: "#FA2D48"   // la couleur d'Apple Music
    // WhatsApp, apparence claire : fond des conversations, heure dans les bulles, vert des non-lus, noms dans les groupes
    readonly property color whatsappWallpaper: "#EFEAE2"
    readonly property color whatsappBar: "#F6F6F6"
    readonly property color whatsappTime: "#667781"
    readonly property color whatsappGreen: "#25D366"
    readonly property var whatsappNames: ["#1F7AEC", "#E542A3", "#35CD96", "#FA6533", "#C4532D", "#029D00", "#A62C71",
                                          "#DFB610"]

    // Applis de l'accueil : fichier de l'icône (apple/…png) et, s'il manque, sa couleur et son glyphe
    readonly property var apps: ({
        music: { label: "Musique", file: "musique", color: "#FF2D55", glyph: "♫" },
        phone: { label: "Téléphone", file: "telephone", color: "#34C759", glyph: "✆" },
        messages: { label: "Messages", file: "messages", color: "#34C759", glyph: "💬" },
        whatsapp: { label: "WhatsApp", file: "whatsapp", color: "#25D366", glyph: "✆" }
    })
}
