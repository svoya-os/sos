pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Hyprland

// Alt+Tab as on Windows. hyprland.conf hands the shell Alt+Tab and the Alt key itself as global
// shortcuts (svoya:alttab, svoya:alt; Alt still reaches the apps): the first Tab picks the window
// used before this one, each next Tab the one before that, and letting go of Alt goes there. A
// quick Alt+Tab switches without showing anything; held a moment longer, the overview
// (panels/Overview.qml) shows the choice with live pictures. Esc there cancels.
Singleton {
    id: root

    property bool active: false        // Alt is still held after an Alt+Tab
    property int index: 0              // the chosen one of `windows`
    property var windows: []           // toplevels, most recently used first (fixed for one switch)
    property var focusOrder: []        // window addresses "0x…", most recently focused first

    function addressOf(t) {
        const a = String(t && t.address ? t.address : "");
        return a.indexOf("0x") === 0 ? a : "0x" + a;
    }

    // the windows of the numbered desktops (not the ones Super+D hid), most recently used first
    function recent() {
        const all = Hyprland.toplevels.values.filter(t => t && t.workspace && t.workspace.id > 0);
        const rank = t => {
            const i = root.focusOrder.indexOf(root.addressOf(t));
            return i >= 0 ? i : (t.activated ? -1 : 100000);
        };
        return all.slice().sort((a, b) => rank(a) - rank(b));
    }

    // Tab with Alt held
    function tab() {
        if (!root.active) {
            const list = root.recent();
            if (list.length < 2)
                return;
            root.windows = list;
            root.index = 1;
            root.active = true;
            reveal.restart();
            return;
        }
        if (root.windows.length > 0)
            root.index = (root.index + 1) % root.windows.length;
        if (Ui.modal !== "overview") {
            reveal.stop();
            Ui.show("overview");
        }
    }

    function step(d) {
        const n = root.windows.length;
        if (root.active && n > 0)
            root.index = (root.index + d + n) % n;
    }

    // Alt let go (or Enter, or a click in the overview): go to the chosen window
    function commit(i) {
        if (!root.active)
            return;
        if (i !== undefined && i >= 0)
            root.index = i;
        root.active = false;
        reveal.stop();
        if (Ui.modal === "overview")
            Ui.hide();
        root.bring(root.windows[root.index]);
    }

    function cancel() {
        root.active = false;
        reveal.stop();
        if (Ui.modal === "overview")
            Ui.hide();
    }

    function bring(t) {
        if (!t)
            return;
        if (t.wayland) {
            t.wayland.activate();       // Hyprland focuses it, raises a floating one, goes to its desktop
            return;
        }
        const a = root.addressOf(t);
        Hypr.dispatch("focuswindow address:" + a, "hl.dsp.focus({ window = \"address:" + a + "\" })");
    }

    function remember(data) {
        const a = String(data || "").trim();
        if (a.length === 0 || a === ",")
            return;
        const x = a.indexOf("0x") === 0 ? a : "0x" + a;
        root.focusOrder = [x].concat(root.focusOrder.filter(y => y !== x)).slice(0, 100);
    }

    Timer {
        id: reveal

        interval: 170
        onTriggered: {
            if (root.active)
                Ui.show("overview");
        }
    }

    Connections {
        target: Hypr.present ? Hyprland : null

        function onRawEvent(event) {
            if (event.name === "activewindowv2")
                root.remember(event.data);
            else if (event.name === "closewindow") {
                const x = String(event.data || "").indexOf("0x") === 0 ? String(event.data) : "0x" + String(event.data || "");
                root.focusOrder = root.focusOrder.filter(y => y !== x);
            }
        }
    }
}
