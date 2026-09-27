import QtQuick
import QtQuick.Shapes
import ".."

// L'icône du compteur, comme celle du constructeur dans une voiture : le « Ʌ » du logo, laque sur graphite
Rectangle {
    id: icon
    property real size: CarTheme.pt(60)
    width: size
    height: size
    radius: size * 0.225
    gradient: Gradient {
        GradientStop { position: 0; color: Theme.carbonRaised }
        GradientStop { position: 1; color: Theme.graphite }
    }

    Shape {
        id: mark
        readonly property real k: icon.width * 0.62 / 190
        x: (icon.width - 190 * k) / 2 - 163.5 * k
        y: (icon.height - 140 * k) / 2 - 4 * k
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: Theme.lacquer
            strokeColor: "transparent"
            scale: Qt.size(mark.k, mark.k)
            PathSvg { path: "M163.511,4.065L235.119,143.008L264.936,143.008L210.593,41.637L211.512,41.637L316.461,144.188L354.064,144.188L207.5,4.065z" }
        }
    }
}
