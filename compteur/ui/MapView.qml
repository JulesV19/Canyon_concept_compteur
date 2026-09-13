import QtQuick
import QtQuick.Shapes

// Carte OSM hors ligne : tuiles pré-rendues (image://tiles), parcours, trace et position.
// Coordonnées « monde » : pixels Web Mercator au zoom 16 (tuiles de 512 px), comptés depuis `origin`.
// Sur le Pi, c'est le processeur qui dessine : la carte doit coûter peu. Tuiles et parcours sont gardés dans une image un
// peu plus grande que l'écran, qui glisse sans être redessinée (voir slide) ; elle n'est refaite que lorsque la carte
// tourne, zoome, reçoit une tuile ou a glissé de toute sa marge (voir cacheState). Par-dessus, seul ce qui change est
// dessiné à chaque image : le creux du parcours derrière soi et la trace de la sortie libre, en tronçons dont seuls ceux
// à l'écran comptent. La carte ne glisse qu'à l'écran (`active`), et seulement quand elle a bougé d'un pixel (voir step).
// Invisible (page hors de l'écran), elle ne fait rien du tout ; elle se replace et refait son image en réapparaissant.
Item {
    id: map
    clip: true

    property point origin
    property real centerX          // dernière position mesurée : la carte y glisse
    property real centerY
    property real heading
    property real zoom: 16
    property bool headingUp: true
    property var route: []
    property real done: 0          // longueur faite le long du parcours, en coordonnées carte
    property int trackChunkCount: 0  // trace de la sortie libre : nombre de tronçons finis...
    property var trackChunk: function (index) { return [] }  // ... et chacun d'eux, demandé une seule fois
    property var trackRecent: []   // trace : tronçon en cours, depuis la fin du dernier tronçon fini
    property bool live: false      // en train de rouler : le bout de la trace suit la position, le halo respire
    property bool active: true     // carte à l'écran ; ailleurs, elle se place sans glisser, et rien ne s'anime
    property int animationMs: 1000

    // Cap en haut : la position est plus bas, pour voir loin devant
    readonly property real anchorX: width / 2
    readonly property real anchorY: headingUp ? height * 0.68 : height / 2

    // La carte suit le cap du vélo en douceur, sans à-coups dans les virages ni sur les petites
    // irrégularités du tracé. La flèche, elle, montre le cap exact et tourne avec la route.
    property real mapHeading
    readonly property real bearing: headingUp ? mapHeading : 0
    onHeadingChanged: {
        if (!ready) {
            mapHeading = heading
            return
        }
        const diff = ((heading - mapHeading) % 360 + 540) % 360 - 180
        mapHeading = (mapHeading + 0.4 * diff + 360) % 360
        Qt.callLater(map.glide)
    }
    readonly property int tileZoom: Math.max(8, Math.min(16, Math.round(zoom)))
    readonly property real scaleFactor: Math.pow(2, zoom - 16)
    property bool ready: false
    readonly property bool animated: ready && animationMs > 0 && active
    // Position, cap et avancement glissent ensemble, à vitesse constante, pendant un peu plus qu'un pas de mesure :
    // la carte ne s'arrête jamais entre deux mesures et la route reste dans l'axe de la flèche.
    readonly property int glideMs: Math.round(animationMs * 1.1)
    property string tileKey

    // Ce qui est affiché : position, cap de la carte, cap de la flèche et avancement. Ils glissent vers la dernière
    // mesure au rythme d'un minuteur à 25 par seconde, mais ne changent qu'une fois le déplacement visible, d'un pixel
    // au moins : à vélo, la carte avance d'une dizaine de pixels par seconde, inutile de la redessiner 25 fois. Sans
    // animation, tout se place directement.
    readonly property int frameMs: 40
    // Pas d'angle qui déplace d'un pixel le coin de carte le plus loin de la position : en deçà, la carte ne tourne pas
    readonly property real bearingStep: 180 / Math.PI / Math.max(1, Math.hypot(Math.max(anchorX, width - anchorX),
                                                                              Math.max(anchorY, height - anchorY)))
    property real shownX
    property real shownY
    property real shownBearing
    property real shownHeading
    property real shownDone: 0
    property real breath: 0          // 0 → 1 : respiration du halo, toutes les 2,8 s
    property var glideFrom: ({})
    property real glideStart: 0
    property real glideProgress: 1   // 0 → 1 : glissement en cours ; 1 : arrivé

    // L'image de la carte : dessinée depuis cette position et ce cap, avec une marge autour de l'écran
    readonly property int cacheMargin: 48
    property real cacheX
    property real cacheY
    property real cacheBearing
    // Où tombe l'image par rapport à la position affichée, en pixels d'écran
    readonly property point slide: slideOffset()
    // L'image ne vaut que pour le parcours, long à dessiner : sans parcours (sortie libre), les tuiles se dessinent aussi
    // vite directement. Et quand le processeur dessine à une densité d'écran autre que 1 (captures en x2 sur le Mac),
    // Qt place mal le contenu de l'image : la carte est alors dessinée directement.
    readonly property bool cached: route.length > 0
                                   && (GraphicsInfo.api !== GraphicsInfo.Software || Screen.devicePixelRatio === 1)
    // Tout ce qui change l'image : elle n'est refaite que dans ces cas-là, jamais d'elle-même (pas même pour une
    // capture du miroir)
    property int tilesShown: 0  // compte les tuiles qui arrivent, apparaissent en fondu ou partent
    readonly property var cacheState: [cached, cacheX, cacheY, cacheBearing, scaleFactor, tileZoom, anchorX, anchorY,
                                       width, height, routeChunks, tilesShown]
    onCacheStateChanged: if (cached && visible) cacheImage.scheduleUpdate()
    // De retour à l'écran : la carte se place, et son image est refaite dans tous les cas (ce qui a changé pendant
    // l'absence n'a pas été dessiné, et place() peut ne rien changer à cacheState)
    onVisibleChanged: {
        if (!visible || !ready)
            return
        place()
        if (cached)
            cacheImage.scheduleUpdate()
    }

    // Écart d'angle le plus court, en degrés
    function turn(from, to) {
        return ((to - from) % 360 + 540) % 360 - 180
    }
    function slideOffset() {
        const k = scaleFactor
        const t = -cacheBearing * Math.PI / 180
        const dx = (cacheX - shownX) * k
        const dy = (cacheY - shownY) * k
        return Qt.point(dx * Math.cos(t) - dy * Math.sin(t), dx * Math.sin(t) + dy * Math.cos(t))
    }
    // Nouvelle image de la carte quand elle tourne, ou quand elle a glissé de presque toute sa marge
    function keepCache() {
        const s = slideOffset()
        if (shownBearing === cacheBearing && Math.abs(s.x) < cacheMargin - 1 && Math.abs(s.y) < cacheMargin - 1)
            return
        cacheX = shownX
        cacheY = shownY
        cacheBearing = shownBearing
        updateTiles()
    }
    function place() {
        shownX = centerX
        shownY = centerY
        shownBearing = bearing
        shownHeading = heading
        shownDone = done
        glideProgress = 1
        cacheX = shownX
        cacheY = shownY
        cacheBearing = shownBearing
        updateTiles()
    }
    // Hors de l'écran, la carte ne dessine rien ; seules ses tuiles suivent la position (elles se chargent sur d'autres
    // fils, sans rien dessiner), pour qu'elle réapparaisse complète
    function preload() {
        cacheX = centerX
        cacheY = centerY
        updateTiles()
    }
    function glide() {
        if (!ready)
            return
        if (!visible) {
            preload()
            return
        }
        if (!animated) {
            place()
            return
        }
        // Grand saut (nouvelle sortie ailleurs) : on s'y place au lieu de traverser la région
        if (Math.hypot(centerX - shownX, centerY - shownY) > 2000) {
            shownX = centerX
            shownY = centerY
            keepCache()
        }
        if (Math.abs(done - shownDone) > 2000)
            shownDone = done
        glideFrom = { x: shownX, y: shownY, bearing: shownBearing, heading: shownHeading, done: shownDone }
        glideStart = Date.now()
        glideProgress = 0
    }
    // Un pas du glissement. Rien ne change tant que l'écart reste invisible (moins d'un pixel ; d'un degré pour la
    // flèche) : rien n'est alors redessiné. Dès qu'un écart se voit, ou à l'arrivée, tout change ensemble : position,
    // flèche et avancement tiennent dans une seule image au lieu de redessiner la carte chacun à son tour. La carte, elle,
    // ne tourne que d'un pas visible : chaque rotation refait son image (voir keepCache).
    function step() {
        const p = Math.min(1, (Date.now() - glideStart) / glideMs)
        const from = glideFrom
        const pixel = 1 / scaleFactor  // un pixel d'écran, en coordonnées carte
        const x = from.x + (centerX - from.x) * p
        const y = from.y + (centerY - from.y) * p
        const b = from.bearing + turn(from.bearing, bearing) * p
        const h = from.heading + turn(from.heading, heading) * p
        const d = from.done + (done - from.done) * p
        const turning = p === 1 || Math.abs(turn(shownBearing, b)) >= bearingStep
        glideProgress = p
        if (!turning && Math.hypot(x - shownX, y - shownY) < pixel && Math.abs(turn(shownHeading, h)) < 1
                && Math.abs(d - shownDone) < pixel)
            return
        shownX = x
        shownY = y
        if (turning)
            shownBearing = b
        shownHeading = h
        shownDone = d
        keepCache()
    }
    onCenterXChanged: Qt.callLater(map.glide)
    onCenterYChanged: Qt.callLater(map.glide)
    onBearingChanged: Qt.callLater(map.glide)
    onDoneChanged: Qt.callLater(map.glide)
    onActiveChanged: if (ready) place()

    Timer {
        interval: map.frameMs
        repeat: true
        running: map.animated && (map.glideProgress < 1 || map.live)
        onTriggered: {
            if (map.glideProgress < 1)
                map.step()
            if (map.live)
                map.breath = (Date.now() % 2800) / 2800
        }
    }

    function zoomBy(step) {
        zoom = Math.max(12, Math.min(16, Math.round(zoom) + step))
    }

    // Tuiles qui couvrent l'image de la carte, quelle que soit la rotation. On ne touche qu'à celles qui changent.
    function updateTiles() {
        if (!ready || width <= 0 || height <= 0)
            return
        const z = tileZoom
        const size = 512 * Math.pow(2, 16 - z)
        const radius = Math.hypot(Math.max(anchorX, width - anchorX) + cacheMargin,
                                  Math.max(anchorY, height - anchorY) + cacheMargin) / scaleFactor
        const cx = origin.x + cacheX
        const cy = origin.y + cacheY
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
            tiles.append({ key: k, level: z, tx: wanted[k].x * size - origin.x, ty: wanted[k].y * size - origin.y, size: size })
    }

    Component.onCompleted: {
        mapHeading = heading
        ready = true
        place()
        syncTrackChunks()
    }
    onScaleFactorChanged: {
        keepCache()
        updateTiles()
    }
    onAnchorYChanged: updateTiles()
    onWidthChanged: updateTiles()
    onHeightChanged: updateTiles()

    // Nouvelle position : la carte y glisse (ou s'y place, voir glide)
    function moveTo(x, y) {
        centerX = x
        centerY = y
    }
    Behavior on zoom { enabled: map.ready && !pinch.active; NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }

    // Avancement dessiné : il glisse avec la carte, et le creux du parcours avance sous la flèche sans à-coups
    readonly property real shownProgress: routeLength > 0 ? shownDone / routeLength : 0

    // Le parcours en tronçons de 100 points, chacun avec sa position le long du tracé. Deux tronçons voisins
    // partagent un point : leurs bouts arrondis se recouvrent, et le trait paraît continu.
    readonly property var routeChunks: {
        const chunks = []
        let start = 0
        for (let i = 0; i + 1 < route.length; i += 100) {
            const points = route.slice(i, i + 101)
            let length = 0
            for (let k = 1; k < points.length; k++)
                length += Math.hypot(points[k].x - points[k - 1].x, points[k].y - points[k - 1].y)
            chunks.push({ points: points, start: start, length: length })
            start += length
        }
        return chunks
    }
    readonly property real routeLength: {
        const last = routeChunks[routeChunks.length - 1]
        return last ? last.start + last.length : 0
    }

    // Sortie libre : les tronçons finis de la trace, ajoutés un à un. Chacun lit ses points une seule fois (trackChunk) :
    // un tronçon qui arrive ne fait ni relire ni redessiner les autres.
    ListModel { id: finishedTrack }
    onTrackChunkCountChanged: syncTrackChunks()
    function syncTrackChunks() {
        if (trackChunkCount < finishedTrack.count)
            finishedTrack.clear()
        for (let i = finishedTrack.count; i < trackChunkCount; i++)
            finishedTrack.append({ chunk: i })
    }
    // Tronçon en cours, sans son dernier point : le bout de la trace le rejoint en glissant avec la carte
    readonly property var recentTrack: trackRecent.length > 1 ? trackRecent.slice(0, -1) : []
    readonly property var trackTip: {
        const n = trackRecent.length
        if (n === 0)
            return []
        return [trackRecent[Math.max(0, n - 2)], live ? Qt.point(shownX, shownY) : trackRecent[n - 1]]
    }

    ListModel { id: tiles }

    Timer {
        id: staleTiles
        interval: 800
        onTriggered: {
            for (let i = tiles.count - 1; i >= 0; i--)
                if (tiles.get(i).level !== map.tileZoom)
                    tiles.remove(i)
        }
    }

    // Terres, le temps que les tuiles arrivent
    Rectangle {
        anchors.fill: parent
        color: Theme.mapLand
    }

    // L'image de la carte et ce qui change par-dessus glissent ensemble, d'un nombre entier de pixels : l'image est
    // recopiée telle quelle, sans être redessinée ni rééchantillonnée
    Item {
        x: Math.round(map.slide.x) - map.cacheMargin
        y: Math.round(map.slide.y) - map.cacheMargin
        width: map.width + 2 * map.cacheMargin
        height: map.height + 2 * map.cacheMargin

        // Tuiles et parcours prévu : dessinés dans l'image quand elle est refaite, ou directement sans image
        Item {
            id: cacheContent
            anchors.fill: parent

            World {
                x: map.cacheMargin + map.anchorX
                y: map.cacheMargin + map.anchorY
                rotation: -map.cacheBearing
                lookX: map.cacheX
                lookY: map.cacheY
                zoomScale: map.scaleFactor

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
                        z: level === map.tileZoom ? 1 : 0
                        width: size
                        height: size
                        source: "image://tiles/" + key
                        sourceSize: Qt.size(512, 512)
                        asynchronous: true
                        smooth: true
                        opacity: status === Image.Ready ? 1 : 0
                        Behavior on opacity { NumberAnimation { duration: 200 } }
                        onOpacityChanged: map.tilesShown++
                        Component.onDestruction: map.tilesShown++
                    }
                }

                // Parcours prévu : un trait de laque avec un liseré graphite, comme les tracés de l'accueil. En
                // tronçons, pour que seuls ceux dans l'image soient dessinés : tous les liserés d'abord, puis la laque,
                // pour que les raccords ne se voient pas.
                Repeater {
                    model: map.routeChunks
                    delegate: TrackLine {
                        required property var modelData
                        z: 2
                        points: modelData.points
                        stroke: Theme.graphite
                        thickness: 12 / map.scaleFactor
                    }
                }
                Repeater {
                    model: map.routeChunks
                    delegate: TrackLine {
                        required property var modelData
                        z: 2.1
                        points: modelData.points
                        stroke: Theme.lacquer
                        thickness: 7 / map.scaleFactor
                    }
                }
            }
        }
        // Leur image, figée : refaite seulement quand ce qu'elle montre change (voir cacheState)
        ShaderEffectSource {
            id: cacheImage
            objectName: "cacheImage"  // pour les essais : refaire l'image et la comparer à celle affichée
            anchors.fill: parent
            visible: map.cached
            sourceItem: map.cached ? cacheContent : null
            hideSource: map.cached
            live: false
            smooth: false
        }

        // Par-dessus, dessiné quand ça change : ce qui avance avec soi
        World {
            x: map.cacheMargin + map.anchorX
            y: map.cacheMargin + map.anchorY
            rotation: -map.cacheBearing
            lookX: map.cacheX
            lookY: map.cacheY
            zoomScale: map.scaleFactor

            // Derrière soi, le parcours se creuse : ce qui est fait reste lisible sans voler la vedette.
            // Le creux suit le parcours lui-même, pas la trace GPS, pour rester bien centré. Seul le tronçon
            // où l'on roule se redessine ; les autres sont pleins ou vides.
            Repeater {
                model: map.routeChunks
                delegate: Shape {
                    id: routeChunk
                    required property var modelData
                    readonly property real reached: Math.max(0, Math.min(1,
                        (map.shownDone - modelData.start) / Math.max(modelData.length, 1e-6)))
                    visible: reached > 0
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        strokeColor: Theme.graphite
                        strokeWidth: 3 / map.scaleFactor
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.RoundJoin
                        trim.end: routeChunk.reached
                        PathPolyline { path: routeChunk.modelData.points }
                    }
                }
            }

            // Sortie libre : la trace se dessine en laque derrière soi, avec un liseré graphite. Tous les liserés
            // d'abord, puis la laque : les raccords entre tronçons ne se voient pas.
            Item {
                visible: map.route.length === 0

                Repeater {
                    model: finishedTrack
                    delegate: TrackLine {
                        required property int chunk
                        points: map.trackChunk(chunk)
                        stroke: Theme.graphite
                        thickness: 12 / map.scaleFactor
                    }
                }
                TrackLine { points: map.recentTrack; stroke: Theme.graphite; thickness: 12 / map.scaleFactor }
                TrackLine { points: map.trackTip; stroke: Theme.graphite; thickness: 12 / map.scaleFactor }
                Repeater {
                    model: finishedTrack
                    delegate: TrackLine {
                        required property int chunk
                        points: map.trackChunk(chunk)
                        stroke: Theme.lacquer
                        thickness: 7 / map.scaleFactor
                    }
                }
                TrackLine { points: map.recentTrack; stroke: Theme.lacquer; thickness: 7 / map.scaleFactor }
                TrackLine { points: map.trackTip; stroke: Theme.lacquer; thickness: 7 / map.scaleFactor }
            }
        }
    }

    // Position : le « Ʌ » du logo, redressé, pointé dans le sens de la marche. Son disque graphite
    // le détache du parcours en laque ; en roulant, un halo respire autour.
    Item {
        id: puck
        width: 48
        height: 48
        x: map.anchorX - width / 2
        y: map.anchorY - height / 2
        rotation: map.shownHeading - map.shownBearing

        Rectangle {
            anchors.centerIn: parent
            width: 48
            height: 48
            radius: 24
            color: Theme.lacquer
            opacity: 0.16
            // Par pas d'un pixel sur le rayon : entre deux, rien à redessiner
            scale: map.live && map.animated ? Math.round((0.9 - 0.2 * Math.cos(2 * Math.PI * map.breath)) * 24) / 24 : 1
        }
        Rectangle {
            anchors.centerIn: parent
            width: 34
            height: 34
            radius: 17
            color: Theme.graphite
            border { color: Theme.lacquer; width: 2 }
        }
        Shape {
            anchors.centerIn: parent
            width: 20
            height: 19
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: Theme.lacquer
                strokeColor: "transparent"
                startX: 8.5; startY: 0
                PathLine { x: 11.5; y: 0 }
                PathLine { x: 20; y: 19 }
                PathLine { x: 15; y: 19 }
                PathLine { x: 10; y: 7.5 }
                PathLine { x: 5; y: 19 }
                PathLine { x: 0; y: 19 }
                PathLine { x: 8.5; y: 0 }
            }
        }
    }

    // Pincer pour zoomer
    PinchHandler {
        id: pinch
        target: null
        property real startZoom: 16
        onActiveChanged: if (active) startZoom = map.zoom
        onActiveScaleChanged: if (active) map.zoom = Math.max(12, Math.min(16.5, startZoom + Math.log2(activeScale)))
    }

    // Le monde vu depuis un point de la carte (lookX, lookY) : placé là où ce point doit tomber, il tourne autour de
    // lui, à l'échelle du zoom. Ce qu'on y met est en coordonnées carte.
    component World: Item {
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

    // Un trait : tronçon du parcours ou de la trace
    component TrackLine: Shape {
        id: line
        property var points: []
        property color stroke
        property real thickness
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: line.stroke
            strokeWidth: line.thickness
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathPolyline { path: line.points }
        }
    }
}
