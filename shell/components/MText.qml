import QtQuick
import qs.core

// Plex Mono text for system facts (bar, metadata, keycaps). `caps` renders the
// mono uppercase label style (+0.14em tracking).
Text {
    id: root

    property real size: Theme.fsMeta
    property bool caps: false
    property real tracking: root.caps ? 0.14 : 0

    color: Theme.textDim
    font.family: Theme.mono
    font.pixelSize: root.size
    font.features: Theme.monoFeatures
    font.letterSpacing: root.tracking * root.size
    font.capitalization: root.caps ? Font.AllUppercase : Font.MixedCase
    textFormat: Text.PlainText
    verticalAlignment: Text.AlignVCenter
}
