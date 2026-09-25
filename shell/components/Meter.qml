import QtQuick
import qs.core

// Thin progress meter (bar job: 34×4, radius 2, surface3 track).
Rectangle {
    id: root

    property real value: 0            // 0..1
    property color fill: Theme.accent

    implicitWidth: 34
    implicitHeight: 4
    radius: height / 2
    color: Theme.surface3
    clip: true

    Rectangle {
        width: parent.width * Math.max(0, Math.min(1, root.value))
        height: parent.height
        radius: parent.radius
        color: root.fill

        Behavior on width {
            NumberAnimation {
                duration: Theme.slow
                easing.type: Theme.easing
            }
        }
    }
}
