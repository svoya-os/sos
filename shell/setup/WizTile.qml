import QtQuick
import qs.core
import qs.components

// Icon tile (components.css .tile.lg): 32×32, radius 8, surface3 with a 1px
// lineStrong inset, 17px icon (stroke 1.7) in textDim. `accent` (selected cards): the icon
// and inset in `text` — neutral, like every selection (DESIGN §11).
Rectangle {
    id: root

    property string glyph: "box"
    property bool accent: false

    width: 32
    height: 32
    radius: 8
    color: Theme.surface3
    border.width: 1
    border.color: root.accent ? Theme.alpha(Theme.text, 0.45) : Theme.lineStrong
    antialiasing: true

    Icon {
        anchors.centerIn: parent
        glyph: root.glyph
        size: 17
        stroke: 1.7
        color: root.accent ? Theme.text : Theme.textDim
    }
}
