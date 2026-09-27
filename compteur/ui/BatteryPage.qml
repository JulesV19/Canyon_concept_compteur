import QtQuick

// Batterie, en direct : la charge et l'autonomie, la prévision (la charge depuis la mise en route, prolongée jusqu'à
// vide), puis le détail des mesures de la jauge et de l'alimentation du Pi. Ouverte depuis les Réglages ; elle sert
// surtout pendant les essais d'autonomie. Tout suit la mise à jour de chaque seconde, sans animation.
Item {
    id: page
    required property var battery  // BatteryModel
    signal back

    readonly property var values: battery.values
    readonly property string state: values.state ?? "absente"
    readonly property bool present: state !== "absente"
    readonly property real percent: values.percent ?? 0
    readonly property int tenths: Math.round(percent * 10)  // au dixième, en entier : pas d'erreur d'arrondi (60,3 × 10)
    readonly property bool low: values.low === true
    // La couleur informe : verte en charge ou pleine, rouge quand la batterie est faible, ambre sans jauge
    readonly property color stateColor: state === "charge" || state === "pleine" ? Theme.ok
        : state === "absente" ? Theme.warning : low ? Theme.danger : Theme.ash
    readonly property color fillColor: state === "charge" ? Theme.ok : low ? Theme.danger : Theme.lacquer
    readonly property string stateText: ({ charge: "En charge", pleine: "Pleine", decharge: "En décharge",
                                           absente: "Jauge absente" })[state] ?? ""

    // La courbe ne se relit que page à l'écran
    property var curve: []
    onVisibleChanged: if (visible) curve = battery.curve
    Connections {
        target: page.battery
        enabled: page.visible
        function onCurveChanged() { page.curve = page.battery.curve }
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.graphite
    }

    PageHeader {
        id: header
        title: "Batterie"
        onBack: page.back()
    }
    // D'où viennent les mesures : la jauge, ou la batterie simulée
    Text {
        anchors { right: parent.right; rightMargin: 26; verticalCenter: header.verticalCenter }
        text: page.values.source ?? ""
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold; letterSpacing: 0.6 }
    }

    BatteryHero {
        id: hero
        y: header.height + 4
        view: page
    }

    BatteryForecast {
        id: forecast
        y: hero.y + hero.height + 8
        view: page
    }

    BatteryDetails {
        id: details
        y: forecast.y + forecast.height + 8
        view: page
    }
}
