import QtQuick
import QtQuick.Controls.Basic

// Page cardio : la fréquence cardiaque et sa zone, la courbe des 10 dernières minutes aux couleurs des zones,
// puis le temps passé dans chaque zone, avec la moyenne et le maximum.
Item {
    id: page
    required property var ride     // RideModel : courbe cardio
    required property var values

    // La courbe suit chaque seconde quand la page est à l'écran ; voisine (elle peut arriver sous le doigt), elle est
    // dessinée une fois, en arrivant à côté ; ailleurs, rien n'est recalculé.
    readonly property bool live: SwipeView.isCurrentItem && visible
    readonly property bool near: SwipeView.isNextItem || SwipeView.isPreviousItem
    property var curve: []  // (âge en s, bpm), du plus ancien au plus récent : une moyenne toutes les 5 s
    function refresh() {
        curve = ride.heartRateCurve
    }
    onLiveChanged: if (live) refresh()
    onNearChanged: if (near) refresh()
    Connections {
        target: page.ride
        enabled: page.live
        function onChanged() { page.refresh() }
    }
    readonly property var bounds: values.hrZoneBounds ?? []           // début des zones 2 à 5, en bpm
    readonly property int zone: values.hrZone ?? 0                    // 1 à 5 ; 0 : inconnue
    readonly property var zoneTimes: values.hrZonesS ?? [0, 0, 0, 0, 0]
    readonly property color zoneColor: zone > 0 ? Theme.zones[zone - 1] : Theme.ash
    readonly property var zoneNames: ["Récupération", "Endurance", "Tempo", "Seuil", "Maximum"]

    // Zone (0 à 4) d'une fréquence cardiaque
    function zoneIndex(bpm) {
        let z = 0
        for (const bound of bounds)
            if (bpm >= bound)
                z++
        return z
    }

    CardioHero {
        id: top
        view: page
    }

    CardioChart {
        id: chart
        y: top.height + 4
        view: page
    }

    CardioZones {
        id: zonesPanel
        y: chart.y + chart.height + 10
        view: page
    }
}
