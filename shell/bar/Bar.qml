import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.core
import qs.components

// The 30px bar (DESIGN.md §5; design/mockups/desktop.html), one per screen.
// Left: Morse mark · workspaces · window title. Right: job · GPU · network,
// volume, battery · layout · Jackson mini-scope · clock. Segments without
// data hide. The Classic preset moves the bar to the bottom and adds tasks.
PanelWindow {
    id: bar

    property var modelData
    readonly property bool bottomBar: Settings.layout === "classic"

    screen: bar.modelData
    anchors.top: !bar.bottomBar
    anchors.bottom: bar.bottomBar
    anchors.left: true
    anchors.right: true
    implicitHeight: Theme.barHeight
    exclusiveZone: Theme.barHeight
    color: Theme.bar

    WlrLayershell.namespace: "svoya-bar"
    WlrLayershell.layer: WlrLayer.Top

    // 1px hairline between the bar and the desktop
    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        y: bar.bottomBar ? 0 : parent.height - 1
        height: 1
        color: Theme.line
    }

    // content box: 29px (the 30px bar minus its hairline), padding 0 14 0 12
    Item {
        id: content

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 12
        anchors.rightMargin: 14
        y: bar.bottomBar ? 1 : 0
        height: Theme.barHeight - 1

        Row {
            id: left

            anchors.verticalCenter: parent.verticalCenter
            spacing: 16

            MarkButton {
                anchors.verticalCenter: parent.verticalCenter
                screen: bar.screen
            }

            Workspaces {
                anchors.verticalCenter: parent.verticalCenter
                screen: bar.screen
            }

            WindowTitle {
                anchors.verticalCenter: parent.verticalCenter
                screen: bar.screen
                visible: !bar.bottomBar && here && appName.length > 0
                width: Math.max(0, Math.min(implicitWidth, content.width - right.width - 32 - x))
            }
        }

        Taskbar {
            anchors.verticalCenter: parent.verticalCenter
            x: left.x + left.width + 16
            visible: bar.bottomBar
            screen: bar.screen
            maxWidth: Math.max(0, right.x - x - 16)
        }

        Row {
            id: right

            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: 16

            JobSegment {
                anchors.verticalCenter: parent.verticalCenter
            }

            GpuSegment {
                anchors.verticalCenter: parent.verticalCenter
            }

            StatusIcons {
                anchors.verticalCenter: parent.verticalCenter
                screen: bar.screen
            }

            LayoutIndicator {
                anchors.verticalCenter: parent.verticalCenter
            }

            JacksonChip {
                anchors.verticalCenter: parent.verticalCenter
            }

            Clock {
                anchors.verticalCenter: parent.verticalCenter
                screen: bar.screen
            }
        }
    }
}
