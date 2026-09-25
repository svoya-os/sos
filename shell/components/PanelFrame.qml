import QtQuick
import QtQuick.Effects
import qs.core

// Floating panel shell (Jackson, launcher, control center…): matte surface2,
// 1px lineStrong border, radius 16, a thin edge light on the top edge (inset 88px:
// neutral `text` at 16 %; `live` panels — Jackson — get the accent at 55 %, DESIGN §11)
// and one soft, large shadow. Opens with opacity 0->1, scale 0.985->1, y -6->0 in 180 ms; closes
// in 120 ms (DESIGN.md §4). Children go into the panel body.
Item {
    id: root

    property bool shown: false
    property real radius: Theme.radiusLarge
    property color fill: Theme.surface2
    property color edge: Theme.lineStrong
    property bool highlight: true
    property bool live: false           // Jackson's panel: the edge light is the live signal
    property bool softShadow: false
    default property alias content: body.data

    readonly property bool animating: fade.running

    opacity: root.shown ? 1 : 0
    scale: root.shown ? 1 : 0.985
    visible: opacity > 0.001
    transform: Translate {
        y: root.shown ? 0 : -6

        Behavior on y {
            NumberAnimation {
                duration: root.shown ? Theme.base : Theme.fast
                easing.type: Theme.easing
            }
        }
    }

    Behavior on opacity {
        NumberAnimation {
            id: fade

            duration: root.shown ? Theme.base : Theme.fast
            easing.type: Theme.easing
        }
    }
    Behavior on scale {
        NumberAnimation {
            duration: root.shown ? Theme.base : Theme.fast
            easing.type: Theme.easing
        }
    }

    // --shadow: 0 40px 90px -30px (big) + 0 2px 6px (contact); soft: 0 28px 60px -24px
    RectangularShadow {
        anchors.fill: bg
        radius: root.radius
        offset: Qt.vector2d(0, root.softShadow ? 28 : 40)
        blur: root.softShadow ? 60 : 90
        spread: root.softShadow ? -24 : -30
        color: Theme.shadow
    }

    RectangularShadow {
        anchors.fill: bg
        visible: !root.softShadow
        radius: root.radius
        offset: Qt.vector2d(0, 2)
        blur: 6
        spread: 0
        color: Theme.alpha(Theme.shadow, Theme.shadow.a * 0.45)
    }

    Rectangle {
        id: bg

        anchors.fill: parent
        radius: root.radius
        color: root.fill
        border.width: 1
        border.color: root.edge
        antialiasing: true

        // swallow clicks so the overlay's click-outside catcher does not fire
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onWheel: wheel => wheel.accepted = true
        }
    }

    Item {
        id: body

        anchors.fill: parent
    }

    // thin edge light on the top edge
    Rectangle {
        id: edgeLight

        readonly property color tint: root.live ? Theme.accent : Theme.text

        visible: root.highlight
        x: 88
        y: 0
        width: Math.max(0, parent.width - 176)
        height: 1
        opacity: root.live ? 0.55 : 0.16
        gradient: Gradient {
            orientation: Gradient.Horizontal

            GradientStop {
                position: 0
                color: Theme.alpha(edgeLight.tint, 0)
            }
            GradientStop {
                position: 0.5
                color: edgeLight.tint
            }
            GradientStop {
                position: 1
                color: Theme.alpha(edgeLight.tint, 0)
            }
        }
    }
}
