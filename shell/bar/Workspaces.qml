import QtQuick
import Quickshell.Hyprland
import qs.core
import qs.components

// Workspaces 1…N (N = max(4, highest used), ≤ 10) as 19×19 squares, radius 5:
// active = `text` fill + `surface` number (neutral, DESIGN §5/§11), occupied = textDim,
// empty = textFaint.
Row {
    id: root

    property var screen: null
    readonly property var monitor: root.screen ? Hyprland.monitorFor(root.screen) : null
    readonly property int activeId: root.monitor && root.monitor.activeWorkspace ? root.monitor.activeWorkspace.id : Hypr.activeWorkspaceId

    // id -> window count for normal workspaces
    readonly property var occupancy: {
        const map = {};
        const list = Hyprland.workspaces.values;
        for (let i = 0; i < list.length; i++) {
            const ws = list[i];
            if (ws && ws.id > 0)
                map[ws.id] = ws.toplevels.values.length;
        }
        return map;
    }
    readonly property int count: {
        let n = 4;
        for (const id in root.occupancy)
            n = Math.max(n, Number(id));
        return Math.min(10, Math.max(n, root.activeId));
    }

    spacing: 3

    Repeater {
        model: root.count

        Rectangle {
            required property int index

            readonly property int wsId: index + 1
            readonly property bool active: wsId === root.activeId
            readonly property bool occupied: (root.occupancy[wsId] || 0) > 0

            width: 19
            height: 19
            radius: 5
            color: active ? Theme.selected : (cell.containsMouse ? Theme.surface3 : "transparent")

            Behavior on color {
                ColorAnimation {
                    duration: Theme.fast
                }
            }

            MText {
                anchors.centerIn: parent
                text: wsId
                size: 10.5
                font.weight: Font.Medium
                color: active ? Theme.surface : (occupied ? Theme.textDim : Theme.textFaint)
            }

            MouseArea {
                id: cell

                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: Hypr.focusWorkspace(wsId)
            }
        }
    }

    WheelHandler {
        onWheel: event => Hypr.relativeWorkspace(event.angleDelta.y < 0 ? 1 : -1)
    }
}
