pragma Singleton
import QtQuick

// Couleurs et polices communes à toute l'interface.
QtObject {
    // Identité « Graphite », accordée au Canyon Ultimate Ash Grey : le gris est la marque,
    // la couleur ne sert qu'à informer.
    readonly property color graphite: "#151618"      // fond : la teinte du carbone brut
    readonly property color carbon: "#202225"        // panneaux (avec la trame carbone)
    readonly property color carbonRaised: "#2B2D31"  // boutons, bandeaux
    readonly property color ash: "#A9ACAA"           // gris cendre du cadre : libellés, traits, logo
    readonly property color lacquer: "#EDEEEC"       // chiffres et textes : blanc cassé, reflet de laque
    readonly property color hairline: "#1FFFFFFF"    // filets et contours
    readonly property color mapLand: "#1C1D20"       // fond de carte, identique aux terres des tuiles (tools/carte/style.mjs)

    // Couleurs d'information
    readonly property color ok: "#3CCB7F"
    readonly property color warning: "#F5A524"       // hors parcours, pause, recherche GPS, pente
    readonly property color danger: "#F2542D"
    readonly property color taillight: "#FF3B30"     // enregistrement en cours, nord, forte pente
    readonly property var zones: ["#7D8A96", "#3FA7D6", "#3CCB7F", "#F5A524", "#F2542D"]

    // Pente de la route : neutre sur le plat ; ambre, orange puis rouge quand ça grimpe ; bleu dans les descentes
    function gradeColor(grade) {
        if (grade >= 9) return taillight
        if (grade >= 6) return danger
        if (grade >= 3) return warning
        if (grade <= -3) return zones[1]
        return lacquer
    }

    // Pente des lettres du logo (≈ 27°) : décalage horizontal par pixel de hauteur. C'est le motif de l'interface.
    readonly property real lean: 0.52

    // Barlow (dessinée d'après les panneaux routiers) ; chiffres en Semi Condensed italique, penchés comme le logo
    readonly property string sans: "Barlow"
    readonly property string numbers: "Barlow Semi Condensed"
}
