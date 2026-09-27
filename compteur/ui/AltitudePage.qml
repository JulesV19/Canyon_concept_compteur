import QtQuick
import QtQuick.Controls.Basic
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
        height: 140

        HeroFigure {
            x: 24
            label: "ALTITUDE"
            value: Format.number(page.values.altitudeM)
            unit: "m"
        }
        SlantRule {
            x: top.width / 2 - 4
            y: 14
            height: top.height - 28
        }
        HeroFigure {
            id: gradeFigure
            x: top.width / 2 + 24
            label: "PENTE"
            value: Format.number(page.values.gradePct)
            unit: "%"
        }
        GradeWedge {
            x: gradeFigure.x + gradeFigure.valueEnd + 12
            y: gradeFigure.valueBaseline - height
            width: 44
            height: 30
            visible: page.hasGrade && Math.round(page.values.gradePct) !== 0
            grade: page.values.gradePct ?? 0
        }
    }

    AltitudeZoom {
        id: zoom
        y: top.height + 4
        view: page
    }

    AltitudeOverall {
        y: zoom.y + zoom.height + 10
        view: page
    }
}
