import QtQuick
import Quickshell
import Quickshell.Widgets
import qs.core

// Launcher-style row (DESIGN.md §5): 40px, 20px icon, name (Plex Sans 13.5),
// secondary (mono 11, textFaint), right-aligned keycap on the selected row.
// Icon: `glyph` (registry line icon) or `iconName` (app icon from the theme).
Rectangle {
    id: root

    property string glyph: ""
    property string iconName: ""
    property string title: ""
    property string secondary: ""
    property string hint: ""        // keycap text shown when selected
    property bool selected: false

    signal activated
    signal hovered

    implicitHeight: 40
    radius: 9
    color: root.selected ? Theme.surface3 : "transparent"

    Item {
        id: iconBox

        anchors.left: parent.left
        anchors.leftMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        width: 20
        height: 20

        IconImage {
            id: appIcon

            anchors.fill: parent
            visible: root.iconName.length > 0 && status === Image.Ready
            source: root.iconName.length > 0 ? Quickshell.iconPath(root.iconName, true) : ""
            asynchronous: true
        }

        Icon {
            anchors.centerIn: parent
            visible: root.iconName.length === 0 || appIcon.status !== Image.Ready
            glyph: root.glyph.length > 0 ? root.glyph : "app-window"
            size: 20
            stroke: 1.5
            color: root.selected ? Theme.text : Theme.textDim
        }
    }

    Row {
        anchors.left: iconBox.right
        anchors.leftMargin: 12
        anchors.right: keys.left
        anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        spacing: 10

        SText {
            id: titleText

            anchors.verticalCenter: parent.verticalCenter
            text: root.title
            size: 13.5
            color: Theme.text
            elide: Text.ElideRight
            width: Math.min(implicitWidth, parent.width * 0.62)
        }

        MText {
            anchors.verticalCenter: parent.verticalCenter
            text: root.secondary
            size: 11
            color: Theme.textFaint
            elide: Text.ElideRight
            width: Math.max(0, Math.min(implicitWidth, parent.width - titleText.width - 10))
        }
    }

    Keycap {
        id: keys

        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        text: root.hint
        visible: root.selected && root.hint.length > 0
        width: visible ? implicitWidth : 0
    }

    MouseArea {
        id: area

        // The row under the pointer is selected only when the pointer really moves: a list that opens
        // or re-filters under a resting cursor keeps its top hit (the VM bot's cursor sat over
        // «Document Viewer», and Enter would have opened that instead of the first result).
        property point last: Qt.point(-1, -1)

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onPositionChanged: mouse => {
            const p = area.mapToItem(null, mouse.x, mouse.y);
            if (area.last.x >= 0 && (Math.abs(p.x - area.last.x) > 0.5 || Math.abs(p.y - area.last.y) > 0.5))
                root.hovered();
            area.last = p;
        }
        onExited: area.last = Qt.point(-1, -1)
        onClicked: root.activated()
    }
}
