pragma Singleton

// Backlight through brightnessctl (`-m`: "device,class,current,percent,max").
// Hidden everywhere when there is no backlight device (desktops).

import QtQuick
import Quickshell

Singleton {
    id: root

    readonly property bool tool: Sys.has["brightnessctl"] === true
    property bool available: false
    property real value: 0            // 0..1

    function refresh(showOsd) {
        if (!root.tool)
            return;
        Sys.run(["brightnessctl", "-m", "-c", "backlight"], function (code, out) {
            const line = out.split("\n")[0] || "";
            const f = line.split(",");
            if (code !== 0 || f.length < 5) {
                root.available = false;
                return;
            }
            const cur = Number(f[2]), max = Number(f[4]);
            root.available = max > 0;
            if (max > 0)
                root.value = cur / max;
            if (showOsd && root.available)
                Ui.showOsd("brightness", root.value, false);
        });
    }

    // Debounced so dragging the slider does not spawn a process per pixel.
    property real pending: -1

    function set(v) {
        root.value = Math.max(0.01, Math.min(1, v));
        root.pending = root.value;
        debounce.restart();
    }

    Timer {
        id: debounce

        interval: 60
        onTriggered: {
            if (root.pending < 0)
                return;
            Sys.run(["brightnessctl", "-q", "-c", "backlight", "set", Math.round(root.pending * 100) + "%"]);
            root.pending = -1;
        }
    }

    onToolChanged: root.refresh(false)
}
