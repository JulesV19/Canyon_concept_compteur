import QtQuick

// Le monde vu depuis un point de la carte (lookX, lookY) : placé là où ce point doit tomber, il tourne autour de
// lui, à l'échelle du zoom. Ce qu'on y met est en coordonnées carte.
Item {
    id: world
    default property alias content: inner.data
    property real lookX
    property real lookY
    property real zoomScale: 1

    Item {
        scale: world.zoomScale
        transformOrigin: Item.TopLeft

        Item {
            id: inner
            x: -world.lookX
            y: -world.lookY
        }
    }
}
