import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Shapes
import "Format.js" as Format

// Page altitude : l'altitude et la pente ; les 5 prochains km en gros plan, colorés selon la pente ; tout le
// parcours en bande fine, avec la position, le D+ fait et ce qui reste à grimper. En sortie libre (ou sur un
// parcours sans altitudes) : les 5 derniers km roulés, et toute la sortie.
Item {
    id: page
    required property var ride     // RideModel : profils du parcours et de la sortie
    required property var values

    // Mise à jour chaque seconde quand la page est à l'écran ; une fois quand elle devient voisine (elle peut
    // arriver sous le doigt) ; jamais ailleurs.
    readonly property bool live: SwipeView.isCurrentItem && visible
    readonly property bool near: SwipeView.isNextItem || SwipeView.isPreviousItem
    readonly property bool onRoute: ride.routeProfile.length > 1
    property var profile: []          // (km, m) du parcours, ou de la sortie
    property bool profileStale: true  // parcours changé, ou profil roulé allongé
    // Position dessinée, à 20 m près : le gros plan n'est recalculé et redessiné que tous les 20 m
    property real doneKm: 0
    readonly property real totalKm: profile.length ? profile[profile.length - 1].x : 0
    function update() {
        if (profileStale) {
            profileStale = false
            profile = onRoute ? ride.routeProfile : ride.rideProfile
        }
        const km = Math.floor((onRoute ? (values.routeDoneKm ?? 0) : (values.distanceKm ?? 0)) * 50) / 50
        if (km !== doneKm)
            doneKm = km
    }
    onLiveChanged: if (live) update()
    onNearChanged: if (near) update()
    onValuesChanged: if (live) update()
    Connections {
        target: page.ride
        function onRouteChanged() { page.profileStale = true }
        function onProfileChanged() { page.profileStale = true }
    }
    readonly property real windowKm: 5
    readonly property bool hasGrade: values.gradePct !== null && values.gradePct !== undefined

    // Les 5 km du gros plan : (km depuis le bord gauche, altitude). Devant soi sur un parcours ; derrière soi
    // en sortie libre, la position étant alors au bord droit.
    readonly property var windowPoints: {
        const pts = profile
        if (pts.length < 2)
            return []
        const from = onRoute ? doneKm : doneKm - windowKm
        const to = from + windowKm
        const out = []
        // Premier point du gros plan, par dichotomie : le profil d'un parcours compte des centaines de points
        let first = 0, last = pts.length - 1
        while (first < last) {
            const middle = (first + last) >> 1
            if (pts[middle].x < from)
                first = middle + 1
            else
                last = middle
        }
        for (let i = first; i < pts.length; i++) {
            const p = pts[i]
            if (p.x < from)
                continue
            const a = i > 0 ? pts[i - 1] : null
            if (out.length === 0 && a && a.x < from)
                out.push(Qt.point(0, a.y + (p.y - a.y) * (from - a.x) / (p.x - a.x)))
            if (p.x > to) {
                if (a)
                    out.push(Qt.point(windowKm, a.y + (p.y - a.y) * (to - a.x) / (p.x - a.x)))
                break
            }
            out.push(Qt.point(p.x - from, p.y))
        }
        return out
    }
    readonly property real windowAscent: {
        let up = 0
        for (let i = 1; i < windowPoints.length; i++)
            up += Math.max(0, windowPoints[i].y - windowPoints[i - 1].y)
        return up
    }

    // Altitude et pente, en grand
    Item {
        id: top
        width: parent.width
        height: 120

        HeroFigure {
            x: 24
            label: "Altitude"
            value: Format.number(page.values.altitudeM)
            unit: "m"
        }
        Divider {
            x: top.width / 2 - 4
            y: 14
            height: top.height - 28
        }
        HeroFigure {
            id: gradeFigure
            x: top.width / 2 + 24
            label: "Pente"
            value: Format.number(page.values.gradePct)
            unit: "%"
        }
        GradeWedge {
            x: gradeFigure.x + gradeFigure.valueEnd + 12
            y: gradeFigure.valueBaseline - height
            width: 40
            height: 26
            visible: page.hasGrade && Math.round(page.values.gradePct) !== 0
            grade: page.values.gradePct ?? 0
        }
    }

    // Gros plan sur 5 km : l'aire sous la courbe prend la couleur de la pente
    Panel {
        id: zoom
        x: 16
        y: top.height + 4
        width: parent.width - 32
        height: 240
        readonly property rect box: Qt.rect(22, 52, width - 44, height - 52 - 36)
        readonly property color blue: Theme.zones[1]
        // Au moins 40 m de haut : les faux plats restent plats
        readonly property var extent: {
            let low = Infinity, high = -Infinity
            for (const p of page.windowPoints) {
                low = Math.min(low, p.y)
                high = Math.max(high, p.y)
            }
            const middle = (low + high) / 2
            const half = Math.max(20, (high - low) / 2 + 4)
            return { low: middle - half, high: middle + half }
        }
        function toBox(p) {
            return Qt.point(box.x + p.x / page.windowKm * box.width,
                            box.y + box.height - (p.y - extent.low) / (extent.high - extent.low) * box.height)
        }
        function closeArea(run, base) {
            return run.concat([Qt.point(run[run.length - 1].x, base), Qt.point(run[0].x, base), run[0]])
        }
        readonly property var line: page.windowPoints.map(p => toBox(p))
        // Aires sous la courbe, d'un seul tenant par classe de pente : plat, descente, puis montée à 3, 6 et 9 %
        readonly property var areas: {
            const groups = [[], [], [], [], []]
            const pts = page.windowPoints
            const n = pts.length
            const base = box.y + box.height
            let run = null, runClass = -1
            for (let i = 0; i + 1 < n; i++) {
                // Pente lissée sur les voisins (≈ 150 m), en %
                const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 2)]
                const grade = b.x > a.x ? (b.y - a.y) / ((b.x - a.x) * 10) : 0
                const k = grade >= 9 ? 4 : grade >= 6 ? 3 : grade >= 3 ? 2 : grade <= -3 ? 1 : 0
                if (k !== runClass) {
                    if (run)
                        groups[runClass].push(closeArea(run, base))
                    run = [line[i]]
                    runClass = k
                }
                run.push(line[i + 1])
            }
            if (run)
                groups[runClass].push(closeArea(run, base))
            return groups
        }

        Text {
            x: 22
            y: 14
            text: page.onRoute ? "Les 5 prochains km" : "Les 5 derniers km"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
        Row {
            anchors { right: parent.right; top: parent.top; rightMargin: 22 + zoom.cutX; topMargin: 10 }
            spacing: 4
            visible: zoom.line.length > 1
            Text {
                id: climbValue
                text: Format.number(page.windowAscent)
                color: Theme.lacquer
                font { family: Theme.numbers; pixelSize: 24; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
            }
            Text {
                anchors.baseline: climbValue.baseline
                text: "m D+"
                color: Theme.ash
                font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
            }
        }

        // Aires en aplats : le moteur simple suffit (leur bord haut est couvert par le trait), et coûte bien moins
        // au GPU que le moteur de courbes. Le trait, lui, reste lissé. Les deux se calculent hors du fil de
        // l'interface.
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.GeometryRenderer
            asynchronous: true
            ShapePath {
                fillColor: Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.16)
                strokeColor: "transparent"
                PathMultiline { paths: zoom.areas[0] }
            }
            ShapePath {
                fillColor: Qt.rgba(zoom.blue.r, zoom.blue.g, zoom.blue.b, 0.6)
                strokeColor: "transparent"
                PathMultiline { paths: zoom.areas[1] }
            }
            ShapePath {
                fillColor: Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.85)
                strokeColor: "transparent"
                PathMultiline { paths: zoom.areas[2] }
            }
            ShapePath {
                fillColor: Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.85)
                strokeColor: "transparent"
                PathMultiline { paths: zoom.areas[3] }
            }
            ShapePath {
                fillColor: Qt.rgba(Theme.taillight.r, Theme.taillight.g, Theme.taillight.b, 0.9)
                strokeColor: "transparent"
                PathMultiline { paths: zoom.areas[4] }
            }
        }
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            asynchronous: true
            ShapePath {
                strokeColor: Theme.lacquer
                strokeWidth: 2
                fillColor: "transparent"
                joinStyle: ShapePath.RoundJoin
                capStyle: ShapePath.RoundCap
                PathPolyline { path: zoom.line }
            }
        }

        // Axe : un repère par km
        Rectangle {
            x: zoom.box.x
            y: zoom.box.y + zoom.box.height
            width: zoom.box.width
            height: 1
            color: Theme.hairline
        }
        Repeater {
            model: 6
            delegate: Rectangle {
                required property int index
                x: zoom.box.x + index / 5 * zoom.box.width - 0.5
                y: zoom.box.y + zoom.box.height
                width: 1
                height: 6
                color: Theme.hairline
            }
        }
        Text {
            x: zoom.box.x
            y: zoom.box.y + zoom.box.height + 10
            text: page.onRoute ? "0" : "−5 km"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 12; weight: Font.Medium }
        }
        Text {
            anchors { right: parent.right; rightMargin: 22 }
            y: zoom.box.y + zoom.box.height + 10
            text: page.onRoute ? "5 km" : "0"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 12; weight: Font.Medium }
        }

        // Position : au bord gauche sur un parcours, au bord droit en sortie libre
        Rectangle {
            readonly property var at: zoom.line.length ? zoom.line[page.onRoute ? 0 : zoom.line.length - 1]
                                                      : Qt.point(0, 0)
            visible: zoom.line.length > 1
            x: at.x - width / 2
            y: at.y - height / 2
            width: 14
            height: 14
            radius: 7
            color: Theme.lacquer
            border { color: Theme.carbon; width: 3 }
        }
        Text {
            x: zoom.box.x
            y: zoom.box.y
            width: zoom.box.width
            height: zoom.box.height
            visible: zoom.line.length < 2
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            text: "Pas d'altitude pour l'instant"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
    }

    // Tout le parcours (ou toute la sortie) en bande fine : la partie faite en laque
    Panel {
        id: overall
        x: 16
        y: zoom.y + zoom.height + 10
        width: parent.width - 32
        height: parent.height - y - 8
        readonly property rect box: Qt.rect(22, 44, width - 44, 52)
        readonly property real markX: page.onRoute
            ? box.x + Math.max(0, Math.min(1, page.doneKm / Math.max(page.totalKm, 1e-6))) * box.width
            : box.x + box.width
        // Profil ramené dans la bande (au plus 300 points)
        readonly property var line: {
            const pts = page.profile
            const n = pts.length
            if (n < 2)
                return []
            let low = Infinity, high = -Infinity
            for (const p of pts) {
                low = Math.min(low, p.y)
                high = Math.max(high, p.y)
            }
            const range = Math.max(40, high - low)
            const total = page.totalKm || 1
            const toBox = p => Qt.point(box.x + p.x / total * box.width,
                                        box.y + box.height - (p.y - low) / range * box.height)
            const step = Math.ceil(n / 300)
            const out = []
            for (let i = 0; i < n; i += step)
                out.push(toBox(pts[i]))
            if ((n - 1) % step !== 0)
                out.push(toBox(pts[n - 1]))
            return out
        }
        readonly property var area: line.length
            ? line.concat([Qt.point(box.x + box.width, box.y + box.height), Qt.point(box.x, box.y + box.height)])
            : []

        Text {
            x: 22
            y: 14
            text: page.onRoute ? "Parcours" : "Ma sortie"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
        Text {
            anchors { right: parent.right; top: parent.top; rightMargin: 22 + overall.cutX; topMargin: 14 }
            visible: page.totalKm > 0
            text: Format.number(page.totalKm, 1) + " km"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }

        // À faire, en cendre (aplat au moteur simple, trait lissé)
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.GeometryRenderer
            asynchronous: true
            ShapePath {
                fillColor: Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.12)
                strokeColor: "transparent"
                PathPolyline { path: overall.area }
            }
        }
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            asynchronous: true
            ShapePath {
                strokeColor: Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.6)
                strokeWidth: 1.5
                fillColor: "transparent"
                joinStyle: ShapePath.RoundJoin
                PathPolyline { path: overall.line }
            }
        }
        // Fait, en laque
        Item {
            width: overall.markX
            height: overall.height
            clip: true

            Shape {
                width: overall.width
                height: overall.height
                preferredRendererType: Shape.GeometryRenderer
                asynchronous: true
                ShapePath {
                    fillColor: Qt.rgba(Theme.lacquer.r, Theme.lacquer.g, Theme.lacquer.b, 0.22)
                    strokeColor: "transparent"
                    PathPolyline { path: overall.area }
                }
            }
            Shape {
                width: overall.width
                height: overall.height
                preferredRendererType: Shape.CurveRenderer
                asynchronous: true
                ShapePath {
                    strokeColor: Theme.lacquer
                    strokeWidth: 2
                    fillColor: "transparent"
                    joinStyle: ShapePath.RoundJoin
                    PathPolyline { path: overall.line }
                }
            }
        }
        Rectangle {
            visible: page.onRoute && overall.line.length > 1
            x: overall.markX - 1
            y: overall.box.y - 6
            width: 2
            height: overall.box.height + 12
            color: Theme.lacquer
        }

        Row {
            x: 22
            y: overall.box.y + overall.box.height + 14
            spacing: 44
            SmallFigure {
                label: "D+"
                value: Format.number(page.values.ascentM)
                unit: "m"
            }
            SmallFigure {
                label: page.onRoute ? "Reste à grimper" : "D−"
                value: Format.number(page.onRoute ? page.values.routeAscentLeftM : page.values.descentM)
                unit: "m"
            }
        }
    }

    // Filet penché comme le logo
    component Divider: Shape {
        id: divider
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: Theme.hairline
            strokeWidth: 1
            fillColor: "transparent"
            startX: -Theme.lean * divider.height / 2; startY: 0
            PathLine { x: Theme.lean * divider.height / 2; y: divider.height }
        }
    }

    // Un chiffre du bas : libellé, valeur en chiffres penchés, unité
    component SmallFigure: Item {
        id: small
        property string label
        property string value
        property string unit
        width: Math.max(smallLabel.implicitWidth, smallValue.implicitWidth + 5 + smallUnit.implicitWidth)
        height: 60

        Text {
            id: smallLabel
            text: small.label
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
        }
        Text {
            id: smallValue
            anchors { baseline: parent.top; baselineOffset: 46 }
            text: small.value
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 32; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            id: smallUnit
            x: smallValue.implicitWidth + 5
            anchors.baseline: smallValue.baseline
            text: small.unit
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 14; weight: Font.Medium }
        }
    }
}
