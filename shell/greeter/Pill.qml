import QtQuick
import qs.core
import qs.components

// Mono option pill of the greeter footer (greeter.html .opt): 26px high,
// 10px side padding, radius 7, Plex Mono 11.5; the selected one sits on
// surface2 with a 1px lineStrong inset and text color, others in textDim.
// Optional 13px icon (stroke 1.8) 7px before the label.
Item {
    id: root

    property string text: ""
    property string glyph: ""
    property bool selected: false

    signal picked

    implicitWidth: row.implicitWidth + 20
    implicitHeight: 26
    activeFocusOnTab: false

    Rectangle {
        anchors.fill: parent
        radius: 7
        visible: root.selected || mouse.containsMouse
        color: root.selected ? Theme.surface2 : Theme.alpha(Theme.surface2, 0.6)
        border.width: root.selected ? 1 : 0
        border.color: Theme.lineStrong
        antialiasing: true
    }

    Row {
        id: row

        x: 10
        anchors.verticalCenter: parent.verticalCenter
        spacing: 7

        Icon {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.glyph.length > 0
            glyph: root.glyph.length > 0 ? root.glyph : "info"
            size: 13
            stroke: 1.8
            color: root.selected ? Theme.text : Theme.textDim
        }

        MText {
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            size: 11.5
            color: root.selected ? Theme.text : Theme.textDim
        }
    }

    MouseArea {
        id: mouse

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.picked()
    }
}
