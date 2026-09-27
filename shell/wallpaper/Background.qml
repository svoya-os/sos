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
    // The desktop itself can hold the keyboard, as on Windows: a click on it, or Super+D hiding
    // every window, leaves no window typing blind (Hyprland refocuses what is under the pointer,
    // and a background layer that takes no keyboard would keep the hidden window focused).
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand

    Wallpaper {
        anchors.fill: parent
    }

    IdleInhibitor {
        window: bg
        enabled: bg.primary && Settings.focusMode === "presentation"
    }
}
