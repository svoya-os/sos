pragma Singleton

// Bluetooth through bluetoothctl: power state and connected device count.
// Refreshed on demand (control center open) and every 20 s while it is open.

import QtQuick
import Quickshell

Singleton {
    id: root

    readonly property bool tool: Sys.has["bluetoothctl"] === true
    property bool controller: false   // a controller exists
    property bool powered: false
    property var connectedNames: []
    property bool busy: false
    property bool watching: false     // set by the control center while visible

    function refresh() {
        if (!root.tool)
            return;
        Sys.sh('bluetoothctl show 2>/dev/null; echo @connected; bluetoothctl devices Connected 2>/dev/null', [], function (code, out) {
            const parts = out.split("@connected");
            const show = parts[0] || "";
            root.controller = show.indexOf("Controller ") >= 0;
            root.powered = /Powered:\s*yes/.test(show);
            const names = [];
            const lines = (parts[1] || "").split("\n");
            for (let i = 0; i < lines.length; i++) {
                const m = /^Device\s+\S+\s+(.+)$/.exec(lines[i].trim());
                if (m)
                    names.push(m[1]);
            }
            root.connectedNames = names;
        });
    }

    function setPowered(on) {
        if (!root.tool)
            return;
        root.busy = true;
        // rfkill may soft-block the radio; unblock before powering on.
        const script = on ? 'command -v rfkill >/dev/null 2>&1 && rfkill unblock bluetooth; bluetoothctl power on' : 'bluetoothctl power off';
        Sys.sh(script, [], function () {
            root.busy = false;
            root.refresh();
        });
    }

    onToolChanged: root.refresh()

    Timer {
        interval: 20000
        repeat: true
        running: root.watching && root.tool
        triggeredOnStart: true
        onTriggered: root.refresh()
    }
}
