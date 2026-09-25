import QtQuick
import qs.core

// Battery glyph from the mockup: outline + nub (stroke) with a filled level
// (the inner rect is x 4.5, y 9.5, 5 high, up to 13 wide in the 24 grid).
Item {
    id: root

    property real level: 1          // 0..1
    property bool charging: false
    property color color: Theme.textDim
    property real size: 15

    implicitWidth: root.size
    implicitHeight: root.size

    Icon {
        anchors.fill: parent
        glyph: root.charging ? "battery-charging" : "svoya-battery"
        size: root.size
        color: root.level < 0.1 && !root.charging ? Theme.bad : root.color
    }

    Rectangle {
        visible: !root.charging
        x: 4.5 * root.size / 24
        y: 9.5 * root.size / 24
        height: 5 * root.size / 24
        width: Math.max(0.6, 13 * root.size / 24 * Math.max(0, Math.min(1, root.level)))
        radius: 0.8 * root.size / 24
        color: root.level < 0.1 ? Theme.bad : root.color
        antialiasing: true
    }
}
