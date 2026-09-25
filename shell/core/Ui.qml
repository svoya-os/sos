pragma Singleton

// Which overlay is open, on which screen, plus OSD requests. Only one modal
// surface is open at a time (Overlay.qml hosts them all in one layer window).
//
// modal: "" | jackson | launcher | cc | sos | session | clipboard | cheatsheet | about | shot | customizer

import QtQuick
import Quickshell

Singleton {
    id: root

    property string modal: ""
    property var screen: null            // ShellScreen the overlay opens on
    property string launcherMode: "all"  // all | settings | modules | actions
    property string launcherQuery: ""
    property string shotPath: ""         // screenshot waiting for an action
    property string ccPage: "main"       // the control center page to open: main | look
    property bool locked: false          // set by the lock screen

    readonly property bool open: root.modal.length > 0

    function show(name, screen) {
        if (root.locked)
            return;
        root.screen = screen ? screen : Hypr.focusedScreen;
        root.modal = name;
    }

    function hide() {
        root.modal = "";
    }

    function toggle(name, screen) {
        if (root.modal === name)
            root.hide();
        else
            root.show(name, screen);
    }

    function openLauncher(mode, query) {
        root.launcherMode = mode || "all";
        root.launcherQuery = query || "";
        root.show("launcher");
    }

    // ---- OSD ----------------------------------------------------------------------
    signal osdRequested(string kind, real value, bool muted)

    function showOsd(kind, value, muted) {
        if (!root.locked)
            root.osdRequested(kind, value, muted);
    }
}
