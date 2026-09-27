import QtQuick
import QtQuick.Shapes
import "Format.js" as Format

// Menu de l'accueil : Mes sorties, Segments Strava, CarPlay, Réglages, et Éteindre, à maintenir pour éviter une fausse
// manœuvre. Au clavier : ↑ ↓ pour choisir, Entrée ou → pour ouvrir.
Item {
    id: page
    required property var history  // HistoryModel : sorties enregistrées
    required property var strava   // StravaModel : segments en favori
    required property var phone    // PhoneModel : l'iPhone, pour CarPlay
    signal back
    signal ridesRequested
    signal segmentsRequested
    signal carPlayRequested
    signal settingsRequested
    signal powerOffRequested

    readonly property var rides: history.rides
    readonly property real totalKm: rides.reduce((sum, ride) => sum + (ride.distanceKm ?? 0), 0)
    property int focusRow: 0        // ligne choisie au clavier
    property bool keyboard: false   // la ligne choisie n'est soulignée qu'au clavier
    property string powerError: ""  // arrêt refusé par le système, en quelques mots

    function moveFocus(delta) {
        keyboard = true
        focusRow = (focusRow + delta + 4) % 4
    }
    function activate() {
        keyboard = true
        if (focusRow === 0)
            ridesRequested()
        else if (focusRow === 1)
            segmentsRequested()
        else if (focusRow === 2)
            carPlayRequested()
        else
            settingsRequested()
    }
    // Ouvert depuis l'accueil : on repart de Mes sorties (en revenant des réglages, le menu n'a pas bougé)
    onVisibleChanged: {
        if (visible) {
            focusRow = 0
            keyboard = false
            powerError = ""
        }
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.graphite
    }

    PageHeader {
        id: header
        title: "Menu"
        onBack: page.back()
    }

    Panel {
        id: panel
        x: 16
        y: header.height + 4
        width: parent.width - 32
        height: 4 * 92 + 3

        Column {
            anchors.fill: parent

            MenuRow {
                width: panel.width
                label: "Mes sorties"
                hint: page.rides.length === 0 ? "Aucune sortie enregistrée"
                    : page.rides.length + (page.rides.length > 1 ? " sorties · " : " sortie · ")
                      + Format.number(page.totalKm) + " km"
                focused: page.keyboard && page.focusRow === 0
                onTapped: {
                    page.keyboard = false
                    page.focusRow = 0
                    page.ridesRequested()
                }

                // La dernière sortie, en vignette
                Outline {
                    anchors { right: parent.right; rightMargin: 58; verticalCenter: parent.verticalCenter }
                    width: 56
                    height: 48
                    points: page.rides.length ? page.rides[0].outline : []
                    color: Theme.ash
                }
            }

            Separator {}

            MenuRow {
                readonly property int count: page.strava.segments.length
                width: panel.width
                label: "Segments Strava"
                hint: !page.strava.connected ? "Pas encore relié à Strava"
                    : page.strava.syncing ? "Synchro en cours…"
                    : count > 0 ? count + (count > 1 ? " segments en favori" : " segment en favori")
                    : page.strava.error !== "" ? "Synchro inachevée : " + page.strava.error
                    : "Aucun segment en favori"
                focused: page.keyboard && page.focusRow === 1
                onTapped: {
                    page.keyboard = false
                    page.focusRow = 1
                    page.segmentsRequested()
                }

                StravaMark {
                    anchors { right: parent.right; rightMargin: 73; verticalCenter: parent.verticalCenter }
                    width: 26
                }
            }

            Separator {}

            MenuRow {
                width: panel.width
                label: "CarPlay"
                hint: !page.phone.values.available ? "Bluetooth indisponible"
                    : page.phone.values.connected ? page.phone.values.name + " connecté"
                    : "Aucun iPhone connecté"
                focused: page.keyboard && page.focusRow === 2
                onTapped: {
                    page.keyboard = false
                    page.focusRow = 2
                    page.carPlayRequested()
                }
            }

            Separator {}

            MenuRow {
                width: panel.width
                label: "Réglages"
                hint: "FC max, auto-pause, luminosité, batterie, GPS"
                focused: page.keyboard && page.focusRow === 3
                onTapped: {
                    page.keyboard = false
                    page.focusRow = 3
                    page.settingsRequested()
                }
            }
        }
    }

    // Le système a refusé de s'arrêter : la raison, au-dessus du bouton. Le compteur reste allumé, rien n'est perdu.
    Text {
        anchors { left: parent.left; right: parent.right; bottom: powerButton.top; leftMargin: 16; rightMargin: 16; bottomMargin: 14 }
        visible: page.powerError !== ""
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: "Impossible d'éteindre : " + page.powerError
        color: Theme.danger
        font { family: Theme.sans; pixelSize: 20; weight: Font.DemiBold }
    }

    HoldButton {
        id: powerButton
        x: 16
        y: parent.height - height - 18
        width: parent.width - 32
        height: 68
        text: "Maintenir pour éteindre"
        onActivated: page.powerOffRequested()
    }

    component Separator: Rectangle {
        x: 20
        width: panel.width - 40
        height: 1
        color: Theme.hairline
    }

    // Une entrée du menu : libellé, précision en dessous, chevron à droite
    component MenuRow: Item {
        id: row
        property string label
        property string hint
        property bool focused    // choisie au clavier : un trait laque sur le bord gauche
        signal tapped
        height: 92

        Rectangle {
            anchors.fill: parent
            color: Theme.carbonRaised
            visible: tap.pressed
        }
        Rectangle {
            y: 14
            width: 3
            height: parent.height - 28
            color: Theme.lacquer
            visible: row.focused
        }
        Text {
            id: rowLabel
            x: 24
            y: 20
            text: row.label
            color: Theme.lacquer
            font { family: Theme.sans; pixelSize: 28; weight: Font.DemiBold }
        }
        Text {
            x: 24
            anchors { top: rowLabel.bottom; topMargin: 2 }
            width: row.width - x - 128  // jusqu'à la vignette
            text: row.hint
            elide: Text.ElideRight
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 20; weight: Font.DemiBold }
        }
        Shape {
            x: row.width - 24 - width
            anchors.verticalCenter: parent.verticalCenter
            width: 11
            height: 20
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Theme.ash
                strokeWidth: 2.5
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                startX: 1; startY: 1
                PathLine { x: 10; y: 10 }
                PathLine { x: 1; y: 19 }
            }
        }
        TapHandler {
            id: tap
            onTapped: row.tapped()
        }
    }
}
