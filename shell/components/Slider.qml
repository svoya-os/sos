import QtQuick
import qs.core

// Horizontal slider: 4px track (surface3), `textDim` fill (a level, not a signal: DESIGN §11), 12px knob.
// Arrow keys step by 5%; drag or click to set. Emits moved(value) (0..1).
Item {
    id: root

    property real value: 0
    signal moved(real value)

    implicitWidth: 200
    implicitHeight: 18
    activeFocusOnTab: true

    function set(v) {
        root.moved(Math.max(0, Math.min(1, v)));
    }

    Keys.onLeftPressed: root.set(root.value - 0.05)
    Keys.onRightPressed: root.set(root.value + 0.05)

    Rectangle {
        id: track

        anchors.verticalCenter: parent.verticalCenter
        width: parent.width
        height: 4
        radius: 2
        color: Theme.surface3

        Rectangle {
            width: Math.max(0, Math.min(1, root.value)) * parent.width
            height: parent.height
            radius: 2
            color: Theme.textDim
        }
    }

    Rectangle {
        x: Math.max(0, Math.min(1, root.value)) * (root.width - width)
        anchors.verticalCenter: parent.verticalCenter
        width: 12
        height: 12
        radius: 6
        color: Theme.text
        border.width: 1
        border.color: Theme.lineStrong
        antialiasing: true
    }

    MouseArea {
        anchors.fill: parent
        anchors.margins: -4
        cursorShape: Qt.PointingHandCursor
        onPressed: mouse => root.set((mouse.x - 4) / root.width)
        onPositionChanged: mouse => {
            if (pressed)
                root.set((mouse.x - 4) / root.width);
        }
        onWheel: wheel => root.set(root.value + (wheel.angleDelta.y > 0 ? 0.05 : -0.05))
    }

    FocusRing {
        radiusBase: 4
    }
}
