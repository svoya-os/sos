import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Widgets
import qs.core
import qs.components

// Classic preset: open windows as quiet buttons (app icon + title) between the
// left and right groups of the bottom bar. Click focuses, middle click closes.
Row {
    id: root

    property var screen: null
    property real maxWidth: 800

    readonly property var windows: ToplevelManager.toplevels.values
    readonly property real itemWidth: root.windows.length > 0 ? Math.min(180, (root.maxWidth - (root.windows.length - 1) * 4) / root.windows.length) : 0

    spacing: 4

    Repeater {
        model: root.windows

        Rectangle {
            id: task

            required property var modelData
            readonly property var entry: modelData && modelData.appId ? DesktopEntries.heuristicLookup(modelData.appId) : null

            width: root.itemWidth
            height: 22
            radius: Theme.radiusSmall
            color: modelData && modelData.activated ? Theme.surface3 : (hover.containsMouse ? Theme.surface2 : "transparent")

            Row {
                anchors.left: parent.left
                anchors.leftMargin: 6
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6

                IconImage {
                    anchors.verticalCenter: parent.verticalCenter
                    implicitSize: 14
                    source: task.entry && task.entry.icon ? Quickshell.iconPath(task.entry.icon, true) : ""
                    visible: source.toString().length > 0
                }

                SText {
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 20
                    text: task.modelData ? (task.modelData.title || (task.entry ? task.entry.name : task.modelData.appId)) : ""
                    size: 12
                    color: task.modelData && task.modelData.activated ? Theme.text : Theme.textDim
                    elide: Text.ElideRight
                }
            }

            MouseArea {
                id: hover

                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                cursorShape: Qt.PointingHandCursor
                onClicked: mouse => {
                    if (mouse.button === Qt.MiddleButton)
                        task.modelData.close();
                    else
                        task.modelData.activate();
                }
            }
        }
    }
}
