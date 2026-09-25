import QtQuick
import QtQuick.Shapes
import qs.core
import qs.components

// Choice card of the first-run wizard (setup.css .card): radius 14, surface
// (surface2 on light themes), 1px line border. Selected: a 2px `text` edge (1px border +
// 1px ring) — neutral, never the accent (DESIGN §11). `dashed` draws the modifier card's
// dashed lineStrong border. Children go into the card's area; the whole
// card is clickable and keyboard-focusable (Enter/Space = pick).
Item {
    id: root

    property bool selected: false
    property bool dashed: false
    property bool clickable: true
    readonly property real radius: 14
    default property alias content: inner.data

    signal picked

    activeFocusOnTab: root.clickable
    Keys.onReturnPressed: root.picked()
    Keys.onSpacePressed: root.picked()

    Rectangle {
        anchors.fill: parent
        anchors.margins: -1
        radius: root.radius + 1
        visible: root.selected
        color: Theme.selected
        antialiasing: true
    }

    Rectangle {
        anchors.fill: parent
        radius: root.radius
        color: Theme.isDark ? Theme.surface : Theme.surface2
        border.width: root.dashed ? 0 : 1
        border.color: root.selected ? Theme.selected : Theme.line
        antialiasing: true
    }

    Shape {
        anchors.fill: parent
        visible: root.dashed
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: Theme.lineStrong
            strokeWidth: 1
            strokeStyle: ShapePath.DashLine
            dashPattern: [4, 3]
            fillColor: "transparent"

            PathRectangle {
                x: 0.5
                y: 0.5
                width: root.width - 1
                height: root.height - 1
                radius: root.radius
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.clickable
        cursorShape: root.clickable ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: root.picked()
    }

    Item {
        id: inner

        anchors.fill: parent
    }

    FocusRing {
        radiusBase: root.radius
    }
}
