import QtQuick

// Parcours prévu : un trait de laque avec un liseré graphite, comme les tracés de l'accueil. En
// tronçons, pour que seuls ceux dans l'image soient dessinés : tous les liserés d'abord, puis la laque,
// pour que les raccords ne se voient pas.
Item {
    id: route
    required property Item view  // la carte (MapView)
    z: 2

    Repeater {
        model: route.view.routeChunks
        delegate: MapTrackLine {
            required property var modelData
            z: 2
            points: modelData.points
            stroke: Theme.graphite
            thickness: 12 / route.view.scaleFactor
        }
    }
    Repeater {
        model: route.view.routeChunks
        delegate: MapTrackLine {
            required property var modelData
            z: 2.1
            points: modelData.points
            stroke: Theme.lacquer
            thickness: 7 / route.view.scaleFactor
        }
    }
}
