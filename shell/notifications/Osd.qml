import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.core
import qs.components

// On-screen display for volume and brightness: a small matte pill at the
// bottom center (icon · label · meter · value), 1.2 s after the last change.
// Never focusable, click-through.
PanelWindow {
    id: win

    property string kind: "volume"
    property real value: 0
    property bool muted: false
    property bool showing: false

    screen: Hypr.focusedScreen
    visible: win.showing || pill.opacity > 0
    anchors.bottom: true
    margins.bottom: Settings.layout === "classic" ? Theme.barHeight + 56 : 64
    exclusionMode: ExclusionMode.Ignore
    implicitWidth: 280
    implicitHeight: 48
    color: "transparent"
    mask: Region {}

    WlrLayershell.namespace: "svoya-osd"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

    Connections {
        target: Ui

        function onOsdRequested(kind, value, muted) {
            win.kind = kind;
            win.value = value;
            win.muted = muted;
            win.showing = true;
            hide.restart();
        }
    }

    Timer {
        id: hide

        interval: 1200
        onTriggered: win.showing = false
    }

    Rectangle {
        id: pill

        anchors.fill: parent
        radius: 12
        color: Theme.surface2
        border.width: 1
        border.color: Theme.lineStrong
        opacity: win.showing ? 1 : 0

        Behavior on opacity {
            NumberAnimation {
                duration: win.showing ? Theme.fast : Theme.base
                easing.type: Theme.easing
            }
        }

        Row {
            anchors.centerIn: parent
            spacing: 12

            Icon {
                anchors.verticalCenter: parent.verticalCenter
                glyph: win.kind === "brightness" ? "sun" : (win.muted || win.value <= 0.001 ? "svoya-volume-mute" : "svoya-volume")
                size: 16
                color: Theme.text
            }

            MText {
                anchors.verticalCenter: parent.verticalCenter
                width: 76
                text: win.kind === "brightness" ? Strings.osdBrightness : (win.muted ? Strings.osdMuted : Strings.osdVolume)
                size: 11
                color: Theme.textDim
            }

            Meter {
                anchors.verticalCenter: parent.verticalCenter
                width: 96
                height: 4
                value: win.muted ? 0 : win.value
                fill: Theme.text
            }

            MText {
                anchors.verticalCenter: parent.verticalCenter
                width: 34
                horizontalAlignment: Text.AlignRight
                text: Math.round((win.muted ? 0 : win.value) * 100) + "%"
                size: 11
                color: Theme.text
            }
        }
    }
}
