import QtQuick

// GPS, en direct : l'état de la réception et la précision, le ciel (où sont les satellites, et lesquels servent), le
// signal de chacun, puis le détail : position, précision, heure, liaison. Ouverte depuis les Réglages ; elle sert surtout
// pendant les essais (placement de l'antenne, temps jusqu'à la première position). Plus haute que l'écran : elle défile
// au doigt, ou avec ↑ ↓. Tout suit la mise à jour de chaque seconde ; le ciel, celle du GPS (toutes les 5 s).
Item {
    id: page
    required property var gps  // GpsModel
    signal back

    readonly property var values: gps.values
    readonly property string state: values.state ?? "absent"
    readonly property bool present: state !== "absent"
    readonly property bool located: state === "2d" || state === "3d"
    // La couleur informe : verte en 3D, ambre en recherche ou en 2D (sans altitude), rouge sans GPS
    readonly property color stateColor: state === "3d" ? Theme.ok : state === "absent" ? Theme.danger : Theme.warning
    readonly property string stateText: ({ absent: "GPS absent", recherche: "Recherche", "2d": "Position 2D",
                                           "3d": "Position 3D" })[state] ?? ""

    // Le ciel ne se relit que page à l'écran
    property var satellites: []
    onVisibleChanged: if (visible) satellites = gps.satellites
    Connections {
        target: page.gps
        enabled: page.visible
        function onSatellitesChanged() { page.satellites = page.gps.satellites }
    }

    // À l'ouverture : en haut de la page
    function replay() {
        flick.contentY = 0
    }
    // ↑ ↓ : fait défiler la page
    function moveFocus(delta) {
        flick.contentY = Math.max(0, Math.min(flick.contentHeight - flick.height, flick.contentY + delta * 160))
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.graphite
    }

    PageHeader {
        id: header
        title: "GPS"
        onBack: page.back()
    }
    // D'où viennent les mesures : le GPS, ou le GPS simulé
    Text {
        anchors { right: parent.right; rightMargin: 26; verticalCenter: header.verticalCenter }
        text: page.values.source ?? ""
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold; letterSpacing: 0.6 }
    }

    Flickable {
        id: flick
        objectName: "gpsScroll"  // pour les essais
        anchors { top: header.bottom; topMargin: 4; left: parent.left; right: parent.right; bottom: parent.bottom }
        contentHeight: column.height + 16
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Column {
            id: column
            x: 16
            width: flick.width - 32
            spacing: 10

            GpsHero {
                view: page
                width: column.width
            }
            GpsSky {
                view: page
                width: column.width
            }
            GpsSignal {
                view: page
                width: column.width
            }
            GpsDetails {
                view: page
                width: column.width
            }

            Text {
                x: 8
                visible: (page.values.firmware ?? "") !== ""
                text: "Micrologiciel " + page.values.firmware
                color: Theme.ash
                font { family: Theme.sans; pixelSize: 17; weight: Font.DemiBold }
            }
        }
    }
}
