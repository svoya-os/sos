import QtQuick
import qs.core
import qs.components

// Fenced code / exact previews: Plex Mono 12 on surface, bordered, radius 10.
// Long content scrolls inside `maxHeight`.
Rectangle {
    id: root

    property string text: ""
    property string lang: ""
    property real maxHeight: 220

    implicitHeight: Math.min(root.maxHeight, code.implicitHeight + 24)
    radius: Theme.radiusBlock
    color: Theme.surface
    border.width: 1
    border.color: Theme.line
    clip: true

    Flickable {
        anchors.fill: parent
        anchors.margins: 12
        contentWidth: code.implicitWidth
        contentHeight: code.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        TextEdit {
            id: code

            text: root.text
            readOnly: true
            selectByMouse: true
            color: Theme.text
            selectionColor: Theme.accentSoft
            font.family: Theme.mono
            font.pixelSize: 12
            font.features: Theme.monoFeatures
            textFormat: TextEdit.PlainText
        }
    }

    MText {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 8
        visible: root.lang.length > 0
        text: root.lang
        size: 10.5
        color: Theme.textFaint
    }
}
