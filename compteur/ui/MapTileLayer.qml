import QtQuick

// Tuiles de la carte (image://tiles), en coordonnées carte : seules celles qui couvrent l'image de la carte sont là.
// Celles d'un autre zoom restent le temps que les nouvelles arrivent.
Item {
    id: tiling
    required property Item view  // la carte (MapView)
    property string tileKey

    // Tuiles qui couvrent l'image de la carte, quelle que soit la rotation. On ne touche qu'à celles qui changent.
    function update() {
        if (!view.ready || view.width <= 0 || view.height <= 0)
            return
        const z = view.tileZoom
        const size = 512 * Math.pow(2, 16 - z)
        const radius = Math.hypot(Math.max(view.anchorX, view.width - view.anchorX) + view.cacheMargin,
                                  Math.max(view.anchorY, view.height - view.anchorY) + view.cacheMargin) / view.scaleFactor
        const cx = view.origin.x + view.cacheX
        const cy = view.origin.y + view.cacheY
        const x0 = Math.floor((cx - radius) / size), x1 = Math.floor((cx + radius) / size)
        const y0 = Math.floor((cy - radius) / size), y1 = Math.floor((cy + radius) / size)
        const key = [z, x0, x1, y0, y1].join("/")
        if (key === tileKey)
            return
        tileKey = key

        const wanted = {}
        for (let x = x0; x <= x1; x++)
            for (let y = y0; y <= y1; y++)
                wanted[z + "/" + x + "/" + y] = { x: x, y: y }
        for (let i = tiles.count - 1; i >= 0; i--) {
            const tile = tiles.get(i)
            if (tile.key in wanted)
                delete wanted[tile.key]
            else if (tile.level === z)
                tiles.remove(i)
            else
                staleTiles.restart()  // autre zoom : gardée le temps que les nouvelles tuiles arrivent
        }
        for (const k in wanted)
            tiles.append({ key: k, level: z, tx: wanted[k].x * size - view.origin.x, ty: wanted[k].y * size - view.origin.y, size: size })
    }

    ListModel { id: tiles }

    Timer {
        id: staleTiles
        interval: 800
        onTriggered: {
            for (let i = tiles.count - 1; i >= 0; i--)
                if (tiles.get(i).level !== tiling.view.tileZoom)
                    tiles.remove(i)
        }
    }

    Repeater {
        model: tiles
        delegate: Image {
            required property string key
            required property int level
            required property real tx
            required property real ty
            required property real size
            x: tx
            y: ty
            z: level === tiling.view.tileZoom ? 1 : 0
            width: size
            height: size
            source: "image://tiles/" + key
            sourceSize: Qt.size(512, 512)
            asynchronous: true
            smooth: true
            opacity: status === Image.Ready ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 200 } }
            onOpacityChanged: tiling.view.tilesShown++
            Component.onDestruction: tiling.view.tilesShown++
        }
    }
}
