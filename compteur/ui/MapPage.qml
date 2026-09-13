import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Shapes
import "Format.js" as Format

// Page carte : la carte OSM, et dessous la vitesse et les kilomètres restants sur un bandeau carbone.
Item {
    id: page
    required property var ride    // RideModel : origine, parcours et trace pour la carte
    required property var values
    property int animationMs: 1000

    readonly property bool hasRoute: values.routeKm !== undefined
    readonly property bool offRoute: values.offRoute === true
    // Page courante : la carte glisse en douceur ; ailleurs, elle se place sans animation
    readonly property bool current: SwipeView.isCurrentItem && visible
    // Page à l'écran, même en partie pendant un balayage (elle n'est courante qu'à mi-chemin). Hors de l'écran, la
    // carte n'est ni calculée ni dessinée : ni son image, ni la trace (voir MapView).
    readonly property bool onScreen: {
        const view = SwipeView.view
        if (!visible || !view)
            return false
        return SwipeView.isCurrentItem || Math.abs(x - view.contentItem.contentX) < width
    }

    MapView {
        id: map
        anchors { top: parent.top; left: parent.left; right: parent.right; bottom: sheet.top }
        visible: page.onScreen
        origin: page.ride.mapOrigin
        heading: page.values.heading ?? 0
        route: page.ride.routePath
        done: page.values.routeDoneLength ?? 0
        // La trace ne sert qu'en sortie libre ; elle ne se lit qu'à l'écran
        trackChunkCount: page.hasRoute ? 0 : page.ride.trackChunkCount
        trackChunk: index => page.ride.trackChunk(index)
        trackRecent: page.onScreen && !page.hasRoute ? page.ride.trackRecent : []
        live: page.values.state === "running" && page.values.autoPaused !== true
        active: page.current
        animationMs: page.animationMs
    }

    // La carte suit la position du cycliste
    function follow() {
        if (values.x !== undefined)
            map.moveTo(values.x, values.y)
    }
    onValuesChanged: follow()
    Component.onCompleted: follow()

    // Commandes : orientation (boussole) et zoom
    Column {
        anchors { top: parent.top; right: parent.right; topMargin: 12; rightMargin: 12 }
        spacing: 8

        MapButton {
            onClicked: map.headingUp = !map.headingUp
            // Boussole : la pointe rouge indique le nord
            Shape {
                anchors.centerIn: parent
                width: 12
                height: 26
                rotation: -map.shownBearing
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    fillColor: Theme.taillight
                    strokeColor: "transparent"
                    startX: 6; startY: 0
                    PathLine { x: 12; y: 13 }
                    PathLine { x: 0; y: 13 }
                    PathLine { x: 6; y: 0 }
                }
                ShapePath {
                    fillColor: Theme.lacquer
                    strokeColor: "transparent"
                    startX: 0; startY: 13
                    PathLine { x: 12; y: 13 }
                    PathLine { x: 6; y: 26 }
                    PathLine { x: 0; y: 13 }
                }
            }
        }
        MapButton {
            label: "+"
            onClicked: map.zoomBy(1)
        }
        MapButton {
            label: "−"
            onClicked: map.zoomBy(-1)
        }
    }

    // Hors parcours : une étiquette ambre, penchée comme le logo
    Item {
        id: offRouteTag
        anchors { top: parent.top; topMargin: 14; horizontalCenter: parent.horizontalCenter }
        visible: page.offRoute
        width: offRouteText.implicitWidth + 2 * slant + 16
        height: 32
        readonly property real slant: Theme.lean * height

        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: Theme.warning
                strokeColor: "transparent"
                startX: 0; startY: 0
                PathLine { x: offRouteTag.width - offRouteTag.slant; y: 0 }
                PathLine { x: offRouteTag.width; y: offRouteTag.height }
                PathLine { x: offRouteTag.slant; y: offRouteTag.height }
                PathLine { x: 0; y: 0 }
            }
        }
        Text {
            id: offRouteText
            anchors.centerIn: parent
            text: "Hors parcours"
            color: Theme.graphite
            font { family: Theme.sans; pixelSize: 16; weight: Font.DemiBold }
        }
    }

    // Mention obligatoire des données OpenStreetMap
    Text {
        anchors { left: parent.left; bottom: sheet.top; leftMargin: 10; bottomMargin: 6 }
        text: "© OpenStreetMap"
        color: Qt.rgba(Theme.ash.r, Theme.ash.g, Theme.ash.b, 0.7)
        font { family: Theme.sans; pixelSize: 11; weight: Font.Medium }
    }

    // Bandeau de données en carbone. Son bord haut se remplit de laque avec l'avancement sur le parcours,
    // qui glisse avec la carte.
    Rectangle {
        id: sheet
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 150
        color: Theme.carbon

        Image {
            anchors.fill: parent
            source: "textures/carbone.png"
            fillMode: Image.Tile
            smooth: false
        }
        Rectangle {
            width: parent.width
            height: 1
            color: Theme.hairline
        }
        Rectangle {
            visible: page.hasRoute
            width: parent.width * Math.min(1, map.shownProgress)
            height: 3
            color: page.offRoute ? Theme.warning : Theme.lacquer
        }

        Metric {
            x: 24
            label: "Vitesse"
            value: Format.number(page.values.speedKmh, 1)
            unit: "km/h"
        }

        // Filet penché comme le logo
        Shape {
            id: divider
            x: parent.width / 2
            y: 22
            height: parent.height - 44
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Theme.hairline
                strokeWidth: 1
                fillColor: "transparent"
                startX: -Theme.lean * divider.height / 2; startY: 0
                PathLine { x: Theme.lean * divider.height / 2; y: divider.height }
            }
        }

        Metric {
            x: parent.width / 2 + Theme.lean * divider.height / 2 + 14
            label: page.hasRoute ? (page.offRoute ? "Hors parcours" : "Restant") : "Distance"
            labelColor: page.offRoute ? Theme.warning : Theme.ash
            value: Format.number(page.hasRoute ? page.values.routeRemainingKm : page.values.distanceKm, 1)
            unit: "km"
        }
    }

    // Une mesure du bandeau : libellé, grande valeur en chiffres penchés, unité
    component Metric: Item {
        id: metric
        property string label
        property color labelColor: Theme.ash
        property string value
        property string unit
        height: parent.height

        Text {
            y: 20
            text: metric.label
            color: metric.labelColor
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
        Text {
            id: metricValue
            anchors { baseline: parent.bottom; baselineOffset: -26 }
            text: metric.value
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 66; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            x: metricValue.implicitWidth + 8
            anchors.baseline: metricValue.baseline
            text: metric.unit
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 17; weight: Font.Medium }
        }
    }

    // Bouton à coins coupés comme les panneaux, par-dessus la carte
    component MapButton: Item {
        id: button
        property string label
        signal clicked
        width: 50
        height: 50
        readonly property real cut: 12
        readonly property real cutX: cut * Theme.lean
        scale: tap.pressed ? 0.92 : 1
        Behavior on scale { NumberAnimation { duration: 120 } }

        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: tap.pressed ? Theme.ash : Qt.rgba(Theme.carbonRaised.r, Theme.carbonRaised.g, Theme.carbonRaised.b, 0.94)
                strokeColor: Theme.hairline
                strokeWidth: 1
                joinStyle: ShapePath.MiterJoin
                startX: 0.5; startY: 0.5
                PathLine { x: button.width - button.cutX; y: 0.5 }
                PathLine { x: button.width - 0.5; y: button.cut }
                PathLine { x: button.width - 0.5; y: button.height - 0.5 }
                PathLine { x: button.cutX; y: button.height - 0.5 }
                PathLine { x: 0.5; y: button.height - button.cut }
                PathLine { x: 0.5; y: 0.5 }
            }
        }
        Text {
            anchors.centerIn: parent
            text: button.label
            color: tap.pressed ? Theme.graphite : Theme.lacquer
            font { family: Theme.sans; pixelSize: 28; weight: Font.DemiBold }
        }
        TapHandler {
            id: tap
            onTapped: button.clicked()
        }
    }
}
