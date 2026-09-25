import QtQuick
import qs.core

// Departure Mono: only for tiny labels, boot and POST screens, and only at
// multiples of 11 px (DESIGN.md §2). Sizes are snapped to 11/22/33.
Text {
    id: root

    property int step: 1 // 1 -> 11px, 2 -> 22px, 3 -> 33px

    color: Theme.text
    font.family: Theme.pixel
    font.pixelSize: 11 * Math.max(1, Math.min(3, root.step))
    font.hintingPreference: Font.PreferFullHinting
    textFormat: Text.PlainText
    renderType: Text.NativeRendering
}
