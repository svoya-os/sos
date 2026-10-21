import QtQuick
import qs.core

// Quiet mono text button (components.css .tbtn): optional 15px icon, 8px gap,
// Plex Mono 11/16 +0.02em in textDim; `selected` or hover -> text color.
// Enter/Space activate it when it has keyboard focus. With symbol widgets a «>» marks the one
// under the pointer, selected or focused, as in a terminal menu (its place is kept, nothing moves).
Item {
    id: root

    property string glyph: ""
    property string text: ""
    property bool selected: false
    property color color: root.selected || mouse.containsMouse || root.activeFocus ? Theme.text : Theme.textDim

    signal clicked

    implicitWidth: row.implicitWidth
    implicitHeight: 16
    activeFocusOnTab: true

    Keys.onReturnPressed: root.clicked()
    Keys.onSpacePressed: root.clicked()

    Row {
        id: row

        anchors.verticalCenter: parent.verticalCenter
        spacing: 8

        MText {
            anchors.verticalCenter: parent.verticalCenter
            visible: Theme.symbolWidgets
            height: 16
            text: root.selected || mouse.containsMouse || root.activeFocus ? ">" : " "
            size: 11
            color: Theme.accent
        }

        Icon {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.glyph.length > 0
            glyph: root.glyph.length > 0 ? root.glyph : "info"
            size: 15
            stroke: 1.6
            color: root.color
        }

        MText {
            anchors.verticalCenter: parent.verticalCenter
            height: 16
            text: root.text
            size: 11
            font.letterSpacing: 0.22
            color: root.color
        }
    }

    FocusRing {
        target: root
    }

    MouseArea {
        id: mouse

        anchors.fill: parent
        anchors.margins: -4
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
