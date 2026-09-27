import QtQuick

// Départ : un panneau carbone part de la carte choisie, s'agrandit jusqu'à la page de sortie (sous la barre d'état,
// jusqu'à `landingY`), puis s'efface sur elle
Panel {
    id: launch
    property real landingY: 0
    property bool growing: false
    visible: false

    function run(from) {
        x = from.x
        y = from.y
        width = from.width
        height = from.height
        cut = 22
        opacity = 1
        visible = true
        growing = true
        takeOff.restart()
    }

    SequentialAnimation {
        id: takeOff
        ParallelAnimation {
            NumberAnimation { target: launch; property: "x"; to: 0; duration: 450; easing.type: Easing.OutCubic }
            NumberAnimation { target: launch; property: "y"; to: launch.landingY; duration: 450; easing.type: Easing.OutCubic }
            NumberAnimation { target: launch; property: "width"; to: launch.parent.width; duration: 450; easing.type: Easing.OutCubic }
            NumberAnimation { target: launch; property: "height"; to: launch.parent.height - launch.landingY; duration: 450; easing.type: Easing.OutCubic }
            NumberAnimation { target: launch; property: "cut"; to: 0; duration: 450; easing.type: Easing.OutCubic }
        }
        ScriptAction { script: launch.growing = false }
        NumberAnimation { target: launch; property: "opacity"; to: 0; duration: 250 }
        ScriptAction { script: launch.visible = false }
    }
}
