import QtQuick
import "MapGeometry.js" as MapGeometry

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
        mapHeading = (mapHeading + 0.4 * MapGeometry.turn(mapHeading, heading) + 360) % 360
        Qt.callLater(map.glide)
    }
    readonly property int tileZoom: Math.max(8, Math.min(16, Math.round(zoom)))
    readonly property real scaleFactor: Math.pow(2, zoom - 16)
    property bool ready: false
    readonly property bool animated: ready && animationMs > 0 && active
    // Position, cap et avancement glissent ensemble, à vitesse constante, pendant un peu plus qu'un pas de mesure :
    // la carte ne s'arrête jamais entre deux mesures et la route reste dans l'axe de la flèche.
    readonly property int glideMs: Math.round(animationMs * 1.1)

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
        const b = from.bearing + MapGeometry.turn(from.bearing, bearing) * p
        const h = from.heading + MapGeometry.turn(from.heading, heading) * p
        const d = from.done + (done - from.done) * p
        const turning = p === 1 || Math.abs(MapGeometry.turn(shownBearing, b)) >= bearingStep
        glideProgress = p
        if (!turning && Math.hypot(x - shownX, y - shownY) < pixel && Math.abs(MapGeometry.turn(shownHeading, h)) < 1
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

    // Tuiles qui couvrent l'image de la carte (voir MapTileLayer)
    function updateTiles() {
        tileLayer.update()
    }

    Component.onCompleted: {
        mapHeading = heading
        ready = true
        place()
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

    // Le parcours en tronçons (voir MapGeometry.routeChunks)
    readonly property var routeChunks: MapGeometry.routeChunks(route)
    readonly property real routeLength: {
        const last = routeChunks[routeChunks.length - 1]
        return last ? last.start + last.length : 0
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

            MapWorld {
                x: map.cacheMargin + map.anchorX
                y: map.cacheMargin + map.anchorY
                rotation: -map.cacheBearing
                lookX: map.cacheX
                lookY: map.cacheY
                zoomScale: map.scaleFactor

                MapTileLayer {
                    id: tileLayer
                    view: map
                }

                MapRoute { view: map }
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
        MapWorld {
            x: map.cacheMargin + map.anchorX
            y: map.cacheMargin + map.anchorY
            rotation: -map.cacheBearing
            lookX: map.cacheX
            lookY: map.cacheY
            zoomScale: map.scaleFactor

            MapRouteDone { view: map }

            // Sortie libre : la trace derrière soi
            MapFreeTrack { view: map }
        }
    }

    MapPuck { view: map }

    // Pincer pour zoomer
    PinchHandler {
        id: pinch
        target: null
        property real startZoom: 16
        onActiveChanged: if (active) startZoom = map.zoom
        onActiveScaleChanged: if (active) map.zoom = Math.max(12, Math.min(16.5, startZoom + Math.log2(activeScale)))
    }
}
