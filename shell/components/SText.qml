import QtQuick
import qs.core

// Plex Sans text with the mockup's OpenType features ("ss02", "zero").
// `size` is in px; `scaled` applies the large-text accessibility factor.
Text {
    id: root

    property real size: Theme.fsUi
    property bool scaled: false

    color: Theme.text
    font.family: Theme.sans
    font.pixelSize: root.scaled ? root.size * Theme.textScale : root.size
    font.features: Theme.sansFeatures
    font.letterSpacing: root.size >= 20 ? -0.005 * root.size : 0
    textFormat: Text.PlainText
    verticalAlignment: Text.AlignVCenter
}
