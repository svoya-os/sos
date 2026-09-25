import QtQuick
import qs.core
import qs.components

// Icon tile (components.css .tile.lg): 32×32, radius 8, surface3 with a 1px
// lineStrong inset, 17px icon (stroke 1.7) in textDim. `accent`: accentSoft
// fill, accent icon and a 35% accent inset (selected profile cards).
Rectangle {
    id: root

    property string glyph: "box"
    property bool accent: false

    width: 32
    height: 32
    radius: 8
    color: root.accent ? Theme.accentSoft : Theme.surface3
    border.width: 1
    border.color: root.accent ? Theme.alpha(Theme.accent, 0.35) : Theme.lineStrong
    antialiasing: true

    Icon {
        anchors.centerIn: parent
        glyph: root.glyph
        size: 17
        stroke: 1.7
        color: root.accent ? Theme.accent : Theme.textDim
    }
}
