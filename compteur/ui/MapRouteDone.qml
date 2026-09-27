import QtQuick
import QtQuick.Shapes

// Derrière soi, le parcours se creuse : ce qui est fait reste lisible sans voler la vedette.
// Le creux suit le parcours lui-même, pas la trace GPS, pour rester bien centré. Seul le tronçon
// où l'on roule se redessine ; les autres sont pleins ou vides.
Item {
    id: route
    required property Item view  // la carte (MapView)

    Repeater {
        model: route.view.routeChunks
        delegate: Shape {
            id: routeChunk
            required property var modelData
            readonly property real reached: Math.max(0, Math.min(1,
                (route.view.shownDone - modelData.start) / Math.max(modelData.length, 1e-6)))
            visible: reached > 0
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Theme.graphite
                strokeWidth: 3 / route.view.scaleFactor
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                trim.end: routeChunk.reached
                PathPolyline { path: routeChunk.modelData.points }
            }
        }
    }
}
