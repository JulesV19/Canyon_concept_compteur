import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Shapes
import "Format.js" as Format

// Page segment, ajoutée aux pages de la sortie au départ d'un segment en favori. En très grand, l'écart au record au
// même point du segment (vert et « − » en avance, rouge et « + » en retard), ou le chrono s'il n'y a pas de record ;
// puis ce qui reste, le profil, la vitesse, le cardio et le KOM. À l'arrivée, le résultat, quelques secondes.
Item {
    id: page
    required property var ride     // RideModel : profil du segment
    required property var values
    property var result: null      // segment fini, montré quelques secondes
    property bool inPages: false   // dans les pages de la sortie (Main.qml l'y ajoute et l'en retire)
    objectName: "segmentPage"      // pour les essais

    readonly property bool finished: result !== null
    readonly property var seg: result ?? values.segment ?? ({})
    readonly property bool hasRecord: seg.prS !== null && seg.prS !== undefined
    readonly property int gap: Math.round(seg.gapS ?? 0)
    readonly property color gapColor: gap < 0 ? Theme.ok : gap > 0 ? Theme.taillight : Theme.lacquer
    readonly property real remainingM: (seg.remainingKm ?? 0) * 1000

    // Position sur le profil : mise à jour chaque seconde quand la page est à l'écran, une fois quand elle devient
    // voisine (elle peut arriver sous le doigt), jamais ailleurs
    readonly property bool live: SwipeView.isCurrentItem && visible
    readonly property bool near: SwipeView.isNextItem || SwipeView.isPreviousItem
    property real profileKm: 0
    function updateProfile() {
        profileKm = seg.doneKm ?? 0
    }
    onLiveChanged: if (live) updateProfile()
    onNearChanged: if (near) updateProfile()
    onSegChanged: if (live) updateProfile()

    // Entrée : la page glisse dans l'oblique du logo pendant que les bandes orange passent, et le logo se dessine
    property real entry: 1
    function enter() {
        mark.play()
        entryAnimation.restart()
    }
    // Arrivée : le logo se redessine ; record battu, un reflet de laque traverse le temps
    function celebrate(record) {
        mark.play()
        if (record)
            heroSheen.restart()
    }
    opacity: entry
    transform: Translate { x: (1 - page.entry) * 18 * Theme.lean; y: (1 - page.entry) * 18 }
    NumberAnimation {
        id: entryAnimation
        target: page
        property: "entry"
        from: 0
        to: 1
        duration: 350
        easing.type: Easing.OutCubic
    }

    // En-tête : le logo, le nom du segment, sa longueur et sa pente (ou « Terminé »)
    StravaMark {
        id: mark
        x: 24
        y: 10
        width: 20
    }
    Text {
        id: name
        x: 54
        y: 6
        width: headerInfo.x - x - 12
        elide: Text.ElideRight
        text: page.seg.name ?? ""
        color: Theme.lacquer
        font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
    }
    Text {
        id: headerInfo
        anchors { right: parent.right; rightMargin: 24; baseline: name.baseline }
        text: page.finished ? "Terminé"
            : Format.number(page.seg.lengthKm, 1) + " km · " + Format.number(page.seg.gradePct, 1) + " %"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
    }

    Text {
        x: 24
        y: 52
        text: page.finished ? "Ton temps" : page.hasRecord ? "Sur ton record" : "Chrono du segment"
        color: Theme.ash
        font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
    }
    Row {
        anchors { right: parent.right; rightMargin: 24 }
        y: 52
        spacing: 5
        visible: !(page.finished && page.seg.newRecord === true)

        Text {
            id: recordLabel
            text: page.hasRecord ? "Record" : "Premier passage"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
        Text {
            visible: page.hasRecord
            anchors.baseline: recordLabel.baseline
            text: Format.clock(page.seg.prS)
            color: Theme.lacquer
            font { family: Theme.sans; pixelSize: 15; weight: Font.DemiBold; features: ({ "tnum": 1 }) }
        }
    }
    // Record battu (ou premier temps) : une étiquette penchée comme le logo
    Item {
        id: recordTag
        readonly property real slant: Theme.lean * height
        visible: page.finished && page.seg.newRecord === true
        anchors { right: parent.right; rightMargin: 24 }
        y: 48
        width: tagRow.implicitWidth + 2 * slant + 10
        height: 26

        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: Theme.carbonRaised
                strokeColor: "transparent"
                startX: 0; startY: 0
                PathLine { x: recordTag.width - recordTag.slant; y: 0 }
                PathLine { x: recordTag.width; y: recordTag.height }
                PathLine { x: recordTag.slant; y: recordTag.height }
                PathLine { x: 0; y: 0 }
            }
        }
        Row {
            id: tagRow
            anchors.centerIn: parent
            spacing: 7

            Rectangle {
                width: 8
                height: 8
                radius: 4
                color: Theme.ok
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: page.hasRecord ? "Nouveau record" : "Premier temps"
                color: Theme.lacquer
                font { family: Theme.sans; pixelSize: 15; weight: Font.DemiBold }
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    // En grand : l'écart au record, ou le chrono
    Item {
        id: hero
        readonly property bool showsGap: !page.finished && page.hasRecord
        readonly property bool seconds: showsGap && Math.abs(page.gap) < 60
        y: 60
        width: parent.width
        height: 150

        Text {
            id: heroValue
            x: (hero.width - implicitWidth - (hero.seconds ? 10 + heroUnit.implicitWidth : 0)) / 2
            anchors { baseline: parent.top; baselineOffset: 142 }
            text: hero.showsGap ? Format.gap(page.seg.gapS) : Format.clock(page.seg.elapsedS)
            color: hero.showsGap ? page.gapColor : Theme.lacquer
            font {
                family: Theme.numbers; pixelSize: text.length > 5 ? 120 : 168; weight: Font.Bold; italic: true
                features: ({ "tnum": 1 })
            }
        }
        Text {
            id: heroUnit
            visible: hero.seconds
            x: heroValue.x + heroValue.implicitWidth + 10
            anchors.baseline: heroValue.baseline
            text: "s"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 22; weight: Font.DemiBold }
        }

        // Record battu : un reflet de laque, penché comme le logo, traverse le temps
        Item {
            anchors.fill: parent
            clip: true
            visible: sheenBand.travel > 0 && sheenBand.travel < 1

            Rectangle {
                id: sheenBand
                property real travel: 0
                x: -200 + travel * (hero.width + 300)
                y: -hero.height / 2
                width: 90
                height: 2 * hero.height
                rotation: -Math.atan(Theme.lean) * 180 / Math.PI
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Qt.rgba(1, 1, 1, 0) }
                    GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.18) }
                    GradientStop { position: 1; color: Qt.rgba(1, 1, 1, 0) }
                }
            }
        }
        SequentialAnimation {
            id: heroSheen
            PropertyAction { target: sheenBand; property: "travel"; value: 0 }
            PauseAnimation { duration: 300 }
            NumberAnimation { target: sheenBand; property: "travel"; to: 1; duration: 900; easing.type: Easing.InOutCubic }
        }
    }

    // En cours : ce qui reste du segment
    Item {
        x: 24
        y: 214
        width: parent.width - 48
        height: 40
        visible: !page.finished

        Text {
            id: remainingLabel
            anchors.verticalCenter: parent.verticalCenter
            text: "Restant"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
        SlantedBar {
            anchors {
                left: remainingLabel.right; right: remaining.left; verticalCenter: parent.verticalCenter
                leftMargin: 14; rightMargin: 14
            }
            height: 10
            progress: page.seg.progress ?? 0
        }
        Row {
            id: remaining
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            spacing: 5

            Text {
                id: remainingValue
                text: page.remainingM < 1000 ? Format.number(Math.round(page.remainingM / 10) * 10)
                                             : Format.number(page.seg.remainingKm, 1)
                color: Theme.lacquer
                font { family: Theme.numbers; pixelSize: 28; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
            }
            Text {
                anchors.baseline: remainingValue.baseline
                text: page.remainingM < 1000 ? "m" : "km"
                color: Theme.ash
                font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
            }
        }
    }

    // À l'arrivée : l'écart au record, et ce record
    Item {
        x: 24
        y: 214
        width: parent.width - 48
        height: 40
        visible: page.finished

        Row {
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            visible: page.hasRecord

            Text {
                id: resultGap
                text: Format.gap(page.seg.gapS) + (Math.abs(page.gap) < 60 ? " s" : "")
                color: page.gapColor
                font { family: Theme.numbers; pixelSize: 28; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
            }
            Text {
                anchors.baseline: resultGap.baseline
                text: "sur ton record"
                color: Theme.ash
                font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            visible: !page.hasRecord
            text: "Premier temps : il devient ta référence"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
        // L'ancien record (le haut de la page montre l'étiquette « Nouveau record »), ou la date du record gardé
        Text {
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            visible: page.hasRecord && (page.seg.newRecord === true || !!page.seg.prDate)
            text: page.seg.newRecord === true ? "Ancien record " + Format.clock(page.seg.prS)
                : "Record du " + Format.dayMonth(page.seg.prDate)
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
    }

    Panel {
        id: panel
        x: 16
        y: 262
        width: parent.width - 32
        height: parent.height - y - 8

        // En cours : profil et pente, chrono (ou moyenne sans record), vitesse, cardio, KOM
        Item {
            anchors.fill: parent
            visible: !page.finished

            Text {
                x: 22
                y: 14
                text: "Profil"
                color: Theme.ash
                font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
            }
            Row {
                anchors { right: parent.right; top: parent.top; rightMargin: 22 + panel.cutX; topMargin: 12 }
                spacing: 5

                Text {
                    id: gradeLabel
                    rightPadding: 3
                    text: "Pente"
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
                }
                Text {
                    anchors.baseline: gradeLabel.baseline
                    text: Format.number(page.values.gradePct)
                    color: Theme.lacquer
                    font { family: Theme.numbers; pixelSize: 24; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
                }
                Text {
                    anchors.baseline: gradeLabel.baseline
                    rightPadding: 5
                    text: "%"
                    color: Theme.ash
                    font { family: Theme.sans; pixelSize: 13; weight: Font.Medium }
                }
                GradeWedge {
                    anchors.bottom: gradeLabel.baseline
                    visible: page.values.gradePct !== null && page.values.gradePct !== undefined
                             && Math.round(page.values.gradePct) !== 0
                    grade: page.values.gradePct ?? 0
                }
            }
            SegmentProfile {
                x: 22
                y: 48
                width: parent.width - 44
                height: 100
                points: page.ride.segmentProfile
                doneKm: page.profileKm
            }
            Separator { y: 152 }
            Figure {
                x: 22
                y: 153
                label: page.hasRecord ? "Chrono" : "Moyenne"
                value: page.hasRecord ? Format.clock(page.seg.elapsedS) : Format.number(page.seg.avgSpeedKmh, 1)
                unit: page.hasRecord ? "" : "km/h"
            }
            Figure {
                x: 162
                y: 153
                label: "Vitesse"
                value: Format.number(page.values.speedKmh, 1)
                unit: "km/h"
            }
            Figure {
                id: cardio
                x: 300
                y: 153
                label: "Cardio"
                value: Format.number(page.values.heartRate)
                unit: "bpm"
            }
            ZoneGauge {
                x: cardio.x + cardio.labelWidth + 10
                y: 153 + 19
                segmentWidth: 11
                segmentHeight: 8
                zone: page.values.hrZone ?? 0
            }
            Separator { y: 249 }
            KomRow {
                y: 250
                seg: page.seg
            }
        }

        // Arrivée : moyenne et cardio, KOM, profil du segment fait
        Item {
            anchors.fill: parent
            visible: page.finished

            Figure {
                x: 22
                label: "Moyenne"
                value: Format.number(page.seg.avgSpeedKmh, 1)
                unit: "km/h"
            }
            Figure {
                x: 162
                label: "Cardio moyen"
                value: Format.number(page.seg.avgHeartRate)
                unit: "bpm"
            }
            Figure {
                x: 300
                label: "Cardio max"
                value: Format.number(page.seg.maxHeartRate)
                unit: "bpm"
            }
            Separator { y: 96 }
            KomRow {
                y: 97
                seg: page.seg
            }
            Separator { y: 149 }
            Text {
                x: 22
                y: 164
                text: "Profil"
                color: Theme.ash
                font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
            }
            SegmentProfile {
                x: 22
                y: 196
                width: parent.width - 44
                height: 94
                points: page.ride.segmentProfile
                doneKm: page.seg.lengthKm ?? 0
            }
        }
    }

    // Filet entre deux lignes de mesures
    component Separator: Rectangle {
        x: 20
        width: parent.width - 40
        height: 1
        color: Theme.hairline
    }

    // Une mesure : libellé en cendre, valeur en chiffres penchés, unité
    component Figure: Item {
        id: figure
        property string label
        property string value
        property string unit
        readonly property real labelWidth: figureLabel.implicitWidth
        height: 96

        Text {
            id: figureLabel
            y: 14
            text: figure.label
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
        Text {
            id: figureValue
            anchors { baseline: parent.top; baselineOffset: 76 }
            text: figure.value
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 40; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            x: figureValue.implicitWidth + 6
            anchors.baseline: figureValue.baseline
            text: figure.unit
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.Medium }
        }
    }

    // KOM (ou QOM) : son temps, et l'écart à son allure au même point
    component KomRow: Item {
        id: kom
        property var seg: ({})
        width: parent.width
        height: 52
        visible: seg.komS !== null && seg.komS !== undefined

        Text {
            id: komLabel
            x: 22
            y: 17
            text: kom.seg.komLabel ?? "KOM"
            color: Theme.ash
            font { family: Theme.sans; pixelSize: 15; weight: Font.DemiBold; letterSpacing: 0.5 }
        }
        Text {
            anchors { left: komLabel.right; leftMargin: 10; baseline: parent.top; baselineOffset: 38 }
            text: Format.clock(kom.seg.komS)
            color: Theme.lacquer
            font { family: Theme.numbers; pixelSize: 26; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
        Text {
            anchors { right: parent.right; rightMargin: 22; baseline: parent.top; baselineOffset: 38 }
            text: Format.gap(kom.seg.komGapS)
            color: Theme.ash
            font { family: Theme.numbers; pixelSize: 26; weight: Font.DemiBold; italic: true; features: ({ "tnum": 1 }) }
        }
    }
}
