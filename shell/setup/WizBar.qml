import QtQuick
import qs.core

// Memory bar (desktop.css .vram): 6px track in surface3, radius 3, a fill in
// accent (warn when tight, bad when it does not fit) and a 1px textFaint cap
// marking the capacity at the right edge. `value` is 0..1 (clamped).
Item {
    id: root

    property real value: 0
    property color fill: Theme.textDim  // download progress passes the accent (a running job)
    property bool cap: true

    implicitHeight: 6

    Rectangle {
        anchors.fill: parent
        radius: 3
        color: Theme.surface3
        antialiasing: true
    }

    Rectangle {
        width: Math.max(root.value > 0 ? 6 : 0, root.width * Math.max(0, Math.min(1, root.value)))
        height: parent.height
        radius: 3
        color: root.fill
        antialiasing: true

        Behavior on width {
            NumberAnimation {
                duration: Theme.base
                easing.type: Theme.easing
            }
        }
    }

    Rectangle {
        visible: root.cap
        x: root.width
        y: -4
        width: 1
        height: root.height + 8
        color: Theme.textFaint
    }
}
