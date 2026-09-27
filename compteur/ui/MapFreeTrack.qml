import QtQuick

// Sortie libre : la trace se dessine en laque derrière soi, avec un liseré graphite. Tous les liserés d'abord, puis la
// laque : les raccords entre tronçons ne se voient pas.
Item {
    id: track
    required property Item view  // la carte (MapView)
    visible: view.route.length === 0

    // Les tronçons finis de la trace, ajoutés un à un. Chacun lit ses points une seule fois (trackChunk) :
    // un tronçon qui arrive ne fait ni relire ni redessiner les autres.
    ListModel { id: finishedTrack }
    function syncTrackChunks() {
        if (view.trackChunkCount < finishedTrack.count)
            finishedTrack.clear()
        for (let i = finishedTrack.count; i < view.trackChunkCount; i++)
            finishedTrack.append({ chunk: i })
    }
    // Tronçon en cours, sans son dernier point : le bout de la trace le rejoint en glissant avec la carte
    readonly property var recentTrack: view.trackRecent.length > 1 ? view.trackRecent.slice(0, -1) : []
    readonly property var trackTip: {
        const n = view.trackRecent.length
        if (n === 0)
            return []
        return [view.trackRecent[Math.max(0, n - 2)], view.live ? Qt.point(view.shownX, view.shownY) : view.trackRecent[n - 1]]
    }
    Component.onCompleted: syncTrackChunks()
    Connections {
        target: track.view
        function onTrackChunkCountChanged() {
            track.syncTrackChunks()
        }
    }

    Repeater {
        model: finishedTrack
        delegate: MapTrackLine {
            required property int chunk
            points: track.view.trackChunk(chunk)
            stroke: Theme.graphite
            thickness: 12 / track.view.scaleFactor
        }
    }
    MapTrackLine { points: track.recentTrack; stroke: Theme.graphite; thickness: 12 / track.view.scaleFactor }
    MapTrackLine { points: track.trackTip; stroke: Theme.graphite; thickness: 12 / track.view.scaleFactor }
    Repeater {
        model: finishedTrack
        delegate: MapTrackLine {
            required property int chunk
            points: track.view.trackChunk(chunk)
            stroke: Theme.lacquer
            thickness: 7 / track.view.scaleFactor
        }
    }
    MapTrackLine { points: track.recentTrack; stroke: Theme.lacquer; thickness: 7 / track.view.scaleFactor }
    MapTrackLine { points: track.trackTip; stroke: Theme.lacquer; thickness: 7 / track.view.scaleFactor }
}
