import QtQuick
import qs.core

// Keyboard focus ring: 2px `text` outline at 70 %, 2px offset (DESIGN.md §9; never the accent, §11).
// Place inside the focusable item; shows only while `target` has active focus.
Rectangle {
    property Item target: parent
    property real radiusBase: 0

    anchors.fill: parent
    anchors.margins: -4
    radius: radiusBase > 0 ? radiusBase + 4 : 0
    color: "transparent"
    border.width: 2
    border.color: Theme.focusRing
    visible: target !== null && target.activeFocus
    antialiasing: true
}
