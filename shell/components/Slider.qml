import QtQuick
import qs.core

// Horizontal slider: 4px track (surface3), `textDim` fill (a level, not a signal: DESIGN §11), 12px knob.
// Arrow keys step by 5%; drag or click to set. Emits moved(value) (0..1).
// With symbol widgets it is a mono bar «[=====|-----]» in the same box.
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

    FontMetrics {
        id: fm

        font.family: Theme.mono
        font.pixelSize: 12
    }

    Row {
        id: bar

        readonly property int cells: Math.max(4, Math.floor(root.width / Math.max(1, fm.averageCharacterWidth)) - 3)
        readonly property int k: Math.round(Math.max(0, Math.min(1, root.value)) * bar.cells)

        anchors.verticalCenter: parent.verticalCenter
        visible: Theme.symbolWidgets

        MText {
            text: "["
            size: 12
            color: Theme.textFaint
        }
        MText {
            text: "=".repeat(bar.k)
            size: 12
            color: Theme.textDim
        }
        MText {
            text: "|"
            size: 12
            font.weight: Font.Medium
            color: Theme.text
        }
        MText {
            text: "-".repeat(bar.cells - bar.k)
            size: 12
            color: Theme.textFaint
        }
        MText {
            text: "]"
            size: 12
            color: Theme.textFaint
        }
    }

    Rectangle {
        id: track

        visible: !Theme.symbolWidgets
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width
        height: 4
        radius: Theme.r(2)
        color: Theme.surface3

        Rectangle {
            width: Math.max(0, Math.min(1, root.value)) * parent.width
            height: parent.height
            radius: Theme.r(2)
            color: Theme.textDim
        }
    }

    Rectangle {
        visible: !Theme.symbolWidgets
        x: Math.max(0, Math.min(1, root.value)) * (root.width - width)
        anchors.verticalCenter: parent.verticalCenter
        width: 12
        height: 12
        radius: Theme.r(6)
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
