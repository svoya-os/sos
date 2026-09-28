import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.core
import qs.components

// Wallpaper layer, one per screen (background layer, under everything,
// ignoring exclusive zones). Static content: Qt only redraws on changes.
// The first screen's window also carries the idle inhibitor used by the
// «Презентация» focus mode.
PanelWindow {
    id: bg

    property var modelData
    property bool primary: false

    screen: bg.modelData
    anchors.top: true
    anchors.bottom: true
    anchors.left: true
    anchors.right: true
    exclusionMode: ExclusionMode.Ignore
    color: Theme.wall

    WlrLayershell.namespace: "svoya-wallpaper"
    WlrLayershell.layer: WlrLayer.Background
    // The desktop holds the keyboard only while Super+D shows it: Hyprland then refocuses what is
    // under the pointer, and a background layer that takes no keyboard would leave the hidden window
    // typing blind. Never otherwise: while a layer that takes the keyboard holds it, Hyprland gives a
    // new window no focus, and moving the pointer over such a layer hands it the keyboard even with
    // click to focus (a terminal opened with Super+Enter would not get what you type).
    WlrLayershell.keyboardFocus: Hypr.desktopShown ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None

    Wallpaper {
        anchors.fill: parent
    }

    IdleInhibitor {
        window: bg
        enabled: bg.primary && Settings.focusMode === "presentation"
    }
}
