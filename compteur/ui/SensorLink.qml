import QtQuick
import QtQuick.Shapes

// Une case de Batterie et GPS : libellé, état en dessous, chevron à droite
Item {
    id: link
    required property var view  // la page Réglages : ligne choisie, et ouverture de l'écran
    property int row
    property string label
    property string hint

    Rectangle {
        anchors.fill: parent
        color: Theme.carbonRaised
        visible: linkTap.pressed
    }
    FocusMark { visible: view.keyboard && view.focusRow === link.row }
    RowLabel {
        id: linkLabel
        y: 16
        text: link.label
    }
    RowHint {
        anchors.top: linkLabel.bottom
        width: link.width - 60
        elide: Text.ElideRight
        text: link.hint
    }
    Shape {
        x: link.width - 22 - width
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
        id: linkTap
        onTapped: {
            view.keyboard = false
            view.focusRow = link.row
            view.open(link.row)
        }
    }
}
