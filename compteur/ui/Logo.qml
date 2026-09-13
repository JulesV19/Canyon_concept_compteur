import QtQuick
import QtQuick.Shapes

// Logo Canyon, redessiné d'après CanyonBicycles.svg (Wikimedia Commons, 1024 × 144 unités).
// Une forme par lettre : dans l'intro, les lettres se dessinent au trait une à une autour du « Ʌ »,
// se remplissent, puis un reflet de laque penché comme elles traverse le logo.
Item {
    id: logo

    property color color: Theme.ash
    property color shine: Theme.lacquer
    property real fill: 1        // 0 : lettres au trait, 1 : lettres pleines
    property real unfold: 1      // 0 : seul le « Ʌ » est là, 1 : toutes les lettres sont dessinées
    property real aOpacity: 1    // le « Ʌ » seul (dans l'intro, il naît du cadre du vélo)
    property real sheen: -1      // position du reflet, de 0 (à gauche) à 1 (à droite)
    property real strokePx: 1.5  // trait des lettres, en pixels d'écran

    readonly property real k: width / 1024  // pixels par unité du dessin
    height: width * 144 / 1024

    // Contour du « Ʌ » dans le sens des aiguilles d'une montre, depuis son coin haut gauche (pour l'intro)
    readonly property var aPoints: [
        Qt.point(163.511, 4.065), Qt.point(207.5, 4.065), Qt.point(354.064, 144.188), Qt.point(316.461, 144.188),
        Qt.point(211.512, 41.637), Qt.point(210.593, 41.637), Qt.point(264.936, 143.008), Qt.point(235.119, 143.008)
    ]

    // rank : ordre d'apparition en partant du « Ʌ » (−1 : le « Ʌ » lui-même)
    readonly property var letters: [
        { rank: 0, svg: "M25.395,1.187c-29.314,0-34.205,24.226-9.661,54.105l41.547,50.386c14.962,18.172,28.737,32.367,34.855,37.182c0.169,0.129,0.336,0.18,0.582,0.18h42.101c-14.417-9.213-31.878-26.022-44.59-40.765L43.286,45.888c-10.001-12.171-8.335-18.653,3.262-17.075c5.853,0.796,21.905,8.591,39.55,24.83h36.195C94.022,21.834,61.046,1.187,25.395,1.187z M150.207,144.215h28.946c-1.413-11.015-6.277-23.98-16.313-36.063h-31.816C142.457,121.96,147.63,132.572,150.207,144.215z" },
        { rank: -1, svg: "M163.511,4.065L235.119,143.008L264.936,143.008L210.593,41.637L211.512,41.637L316.461,144.188L354.064,144.188L207.5,4.065z" },
        { rank: 0, svg: "M378.444,4.065L492.015,137.139L491.065,137.125L325.646,4.065L292.143,4.065L408.71,143.002L442.006,143.002L373.844,67.492L374.788,67.492L469.324,144.188L527.214,144.188L409.659,4.065z" },
        { rank: 1, svg: "M635.381,105.377L589.001,4.065L560.189,4.065L594.771,73.428L593.829,73.418L501.408,4.065L460.456,4.065L605.27,111.18L633.093,144.188L668.105,144.188z" },
        { rank: 2, svg: "M740.176,102.202c12.736,14.765,30.229,31.595,44.652,40.8H742.68c-0.247,0-0.416-0.035-0.589-0.161c-6.134-4.831-19.918-19.049-34.906-37.224l-41.587-50.439C641.017,25.257,645.919,1,675.264,1c38.451,0,73.806,23.99,103.477,60.077l21.449,26.074c20.326,24.688,26.599,39.927,29.647,57.037h-27.56c-2.594-11.646-7.771-22.271-19.208-36.092l-30.394-36.981c-23.372-28.343-48.561-41.403-56.249-42.449c-11.586-1.572-13.254,4.914-3.254,17.099L740.176,102.202z" },
        { rank: 3, svg: "M875.228,4.065L988.803,137.139L987.853,137.125L822.423,4.065L788.905,4.065L905.503,143.002L938.777,143.002L871.859,67.492L871.569,67.492L966.105,144.188L1024,144.188L906.421,4.065z" }
    ]

    // Tracé de la lettre de rang `rank` : décalé de 0,12 par rang, freiné en fin de course
    function progress(rank) {
        if (rank < 0)
            return 1
        const p = Math.max(0, Math.min(1, (unfold - 0.12 * rank) / 0.64))
        return 1 - Math.pow(1 - p, 3)
    }

    readonly property color base: Qt.rgba(color.r, color.g, color.b, fill)
    readonly property color glint: Qt.rgba(shine.r, shine.g, shine.b, fill)
    readonly property real sheenX: -200 + sheen * 1424

    Item {
        width: 1024
        height: 144
        scale: logo.k
        transformOrigin: Item.TopLeft

        Repeater {
            model: logo.letters
            delegate: Shape {
                id: letter
                required property var modelData
                readonly property real p: logo.progress(modelData.rank)
                // Chaque lettre arrive dans l'oblique du logo, d'en bas à droite vers sa place
                x: (1 - p) * 24
                y: (1 - p) * 46
                width: 1024
                height: 144
                opacity: modelData.rank < 0 ? logo.aOpacity : Math.min(1, 3 * p)
                preferredRendererType: Shape.CurveRenderer

                ShapePath {
                    strokeColor: Qt.rgba(logo.color.r, logo.color.g, logo.color.b, 1 - logo.fill)
                    strokeWidth: logo.fill < 1 && logo.k > 0 ? logo.strokePx / logo.k : -1
                    joinStyle: ShapePath.MiterJoin
                    trim.end: letter.p
                    // Reflet : une bande claire, penchée comme les lettres, qui traverse le logo
                    fillGradient: LinearGradient {
                        x1: logo.sheenX - letter.x - 98
                        y1: 123
                        x2: logo.sheenX - letter.x + 98
                        y2: 21
                        GradientStop { position: 0.3; color: logo.base }
                        GradientStop { position: 0.5; color: logo.glint }
                        GradientStop { position: 0.7; color: logo.base }
                    }
                    PathSvg { path: letter.modelData.svg }
                }
            }
        }
    }
}
