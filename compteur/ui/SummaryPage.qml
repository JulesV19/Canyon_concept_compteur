import QtQuick
import QtQuick.Controls.Basic

// Résumé d'une sortie, sur trois pages à balayer : le tracé et les chiffres clés, l'altitude et les zones
// cardio, puis les tours. En fin de sortie, en bas : Enregistrer (fichier FIT et historique), ou Supprimer,
// à maintenir pour éviter une fausse manœuvre. Rouverte depuis Mes sorties : Retour, ou Supprimer.
Item {
    id: page
    required property var summary        // résumé de la sortie (SessionModel.summary ou HistoryModel.opened)
    property bool saved: false           // sortie déjà enregistrée, rouverte depuis Mes sorties
    property alias currentIndex: pages.currentIndex
    readonly property int count: pages.count
    property bool saving: false          // enregistrement en cours (SessionModel.saving)
    property string saveError: ""        // dernier enregistrement refusé, en quelques mots (SessionModel.saveError)
    property bool stored: false          // enregistrée : « Enregistrée » s'affiche un instant, puis retour à l'accueil
    readonly property bool busy: saving || stored
    property bool slow: false            // écriture qui dure : « Enregistrement… » (pas de clignotement si elle est brève)
    signal save
    signal discard
    signal back
    signal done                          // enregistrée : l'écran peut partir

    readonly property var laps: summary.laps ?? []
    readonly property var zones: summary.hrZonesS ?? [0, 0, 0, 0, 0]

    // Nouveau résumé : première page, et tout se redessine
    function replay() {
        stored = false
        pages.currentIndex = 0
        reveal.restart()
    }
    function requestSave() {
        if (!busy)
            page.save()
    }
    function showSaved() {
        stored = true
        leave.start()
    }

    onSavingChanged: if (!saving) slow = false
    Timer {
        interval: 250
        running: page.saving
        onTriggered: page.slow = true
    }
    Timer {
        id: leave
        interval: 700
        onTriggered: page.done()
    }

    // 0 → 1 : le tracé se dessine, puis les chiffres arrivent. Rejoué à chaque changement de page.
    property real shown: 1
    NumberAnimation {
        id: reveal
        target: page
        property: "shown"
        from: 0
        to: 1
        duration: 1400
    }
    function span(a, b) {
        return Math.max(0, Math.min(1, (shown - a) / (b - a)))
    }
    function ease(x) {
        return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2
    }

    // Points ramenés dans une zone, centrés, en gardant leurs proportions
    function fit(points, box) {
        if (!points || points.length < 2 || box.width <= 0)
            return []
        let right = 0, bottom = 0
        for (const p of points) {
            right = Math.max(right, p.x)
            bottom = Math.max(bottom, p.y)
        }
        const s = Math.min(box.width / Math.max(right, 1e-6), box.height / Math.max(bottom, 1e-6))
        const dx = box.x + (box.width - right * s) / 2
        const dy = box.y + (box.height - bottom * s) / 2
        return points.map(p => Qt.point(dx + p.x * s, dy + p.y * s))
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.graphite
    }

    Text {
        id: title
        x: 24
        y: 6
        width: parent.width - 48
        text: page.summary.name ?? ""
        elide: Text.ElideRight
        color: Theme.lacquer
        font { family: Theme.sans; pixelSize: 30; weight: Font.DemiBold }
    }
    Text {
        id: date
        anchors { left: title.left; top: title.bottom; topMargin: 1 }
        text: page.summary.dateText ?? ""
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 19; weight: Font.DemiBold }
    }

    SwipeView {
        id: pages
        anchors {
            top: date.bottom; left: parent.left; right: parent.right; bottom: actions.top
            topMargin: 12; bottomMargin: 10
        }
        onCurrentIndexChanged: reveal.restart()

        SummaryOverview { sheet: page }
        SummaryClimb { sheet: page }
        SummaryLaps { sheet: page }
    }

    SummaryActions {
        id: actions
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        sheet: page
        count: pages.count
        currentIndex: pages.currentIndex
    }
}
