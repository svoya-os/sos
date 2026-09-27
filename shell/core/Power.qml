pragma Singleton

import QtQuick
import Quickshell

// Power mode, as Windows' «Режим питания»: power-profiles-daemon's power-saver · balanced ·
// performance (the ones this computer offers). The Control Center shows it; game mode switches
// to performance and back (Hypr.qml).
Singleton {
    id: root

    property var profiles: []           // offered here, in this order: power-saver, balanced, performance
    property string current: ""
    readonly property bool available: Sys.has["powerprofilesctl"] === true && root.profiles.length > 1

    function refresh() {
        if (Sys.has["powerprofilesctl"] !== true)
            return;
        Sys.run(["powerprofilesctl", "list"], function (code, out) {
            if (code !== 0)
                return;
            const found = [];
            let now = "";
            const lines = String(out || "").split("\n");
            for (let i = 0; i < lines.length; i++) {
                const m = /^\s*(\*)?\s*([a-z][a-z-]*):\s*$/.exec(lines[i]);
                if (!m)
                    continue;
                found.push(m[2]);
                if (m[1])
                    now = m[2];
            }
            root.profiles = ["power-saver", "balanced", "performance"].filter(p => found.indexOf(p) >= 0);
            root.current = now;
        });
    }

    function set(profile) {
        root.current = profile;
        Sys.run(["powerprofilesctl", "set", profile], function () {
            root.refresh();
        });
    }
}
