import QtQuick
import qs.core
import qs.components

// Tag pill (components.css .tag): 20px, 8px padding, Plex Mono 11 textDim on
// surface3. kind "line": transparent with a 1px lineStrong inset; "ok"/"warn":
// colored text on a 13% tint.
Rectangle {
    id: root

    property string text: ""
    property string kind: ""

    readonly property color tint: root.kind === "ok" ? Theme.ok : (root.kind === "warn" ? Theme.warn : Theme.textDim)

    implicitWidth: label.implicitWidth + 16
    implicitHeight: 20
    radius: 10
    color: root.kind === "line" ? "transparent" : (root.kind === "ok" || root.kind === "warn" ? Theme.alpha(root.tint, 0.13) : Theme.surface3)
    border.width: root.kind === "line" ? 1 : 0
    border.color: Theme.lineStrong
    antialiasing: true

    MText {
        id: label

        anchors.centerIn: parent
        text: root.text
        size: 11
        color: root.tint
    }
}
