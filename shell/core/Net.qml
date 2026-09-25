pragma Singleton

// NetworkManager through nmcli: connectivity for the bar icon and the Wi-Fi list
// for the control center. `nmcli monitor` drives refreshes (event based); the
// Wi-Fi signal is re-read every 30 s. Without nmcli everything stays empty and
// the bar hides the network icon.

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    readonly property bool available: Sys.has["nmcli"] === true
    property bool wifiEnabled: false
    property bool hasWifiDevice: false
    property string kind: "none"       // "wifi" | "ethernet" | "none"
    property string ssid: ""
    property int strength: 0             // 0..100 for the active Wi-Fi
    property var networks: []          // [{ssid, signal, secure, active, known}]
    property var saved: []             // saved Wi-Fi connection names
    property string busySsid: ""       // network being connected right now
    property string lastError: ""

    readonly property string icon: {
        if (root.kind === "ethernet")
            return "svoya-ethernet";
        if (root.kind === "wifi")
            return root.strength >= 60 ? "svoya-wifi" : (root.strength >= 35 ? "wifi-high" : "wifi-low");
        return "wifi-off";
    }

    // nmcli -t escapes ':' and '\' inside values with a backslash.
    function splitTerse(line) {
        const out = [];
        let cur = "";
        for (let i = 0; i < line.length; i++) {
            const c = line[i];
            if (c === "\\" && i + 1 < line.length) {
                cur += line[i + 1];
                i++;
            } else if (c === ":") {
                out.push(cur);
                cur = "";
            } else {
                cur += c;
            }
        }
        out.push(cur);
        return out;
    }

    function refresh(rescan) {
        if (!root.available)
            return;
        const script = 'echo @radio; nmcli -t radio wifi; ' + 'echo @dev; nmcli -t -f TYPE,STATE,CONNECTION device status; ' + 'echo @saved; nmcli -t -f NAME,TYPE connection show; ' + 'echo @wifi; nmcli -t -f IN-USE,SIGNAL,SECURITY,SSID device wifi list --rescan "$1"';
        Sys.sh(script, [rescan ? "yes" : "no"], function (code, out) {
            root.parse(out);
        });
    }

    function parse(out) {
        let section = "";
        let wifiOn = false;
        let hasWifi = false;
        let kind = "none";
        let ssid = "";
        let sig = 0;
        const saved = [];
        const nets = {};
        const lines = out.split("\n");
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (line.length === 0)
                continue;
            if (line[0] === "@") {
                section = line.slice(1);
                continue;
            }
            const f = root.splitTerse(line);
            if (section === "radio") {
                wifiOn = line.trim() === "enabled";
            } else if (section === "dev") {
                const type = f[0], state = f[1] || "", conn = f[2] || "";
                if (type === "wifi")
                    hasWifi = true;
                if (state.indexOf("connected") === 0 && state.indexOf("disconnected") < 0) {
                    if (type === "ethernet" && kind !== "ethernet") {
                        kind = "ethernet";
                    } else if (type === "wifi" && kind === "none") {
                        kind = "wifi";
                        ssid = conn;
                    }
                }
            } else if (section === "saved") {
                if ((f[1] || "").indexOf("wireless") >= 0)
                    saved.push(f[0]);
            } else if (section === "wifi") {
                const name = f[3] || "";
                if (name.length === 0)
                    continue;
                const entry = {
                    ssid: name,
                    signal: Number(f[1]) || 0,
                    secure: (f[2] || "").length > 0 && f[2] !== "--",
                    active: f[0] === "*"
                };
                // keep the strongest entry per SSID (several access points)
                if (!nets[name] || entry.active || (!nets[name].active && entry.signal > nets[name].signal))
                    nets[name] = entry;
                if (entry.active)
                    sig = entry.signal;
            }
        }
        const list = Object.keys(nets).map(k => {
            const n = nets[k];
            n.known = saved.indexOf(n.ssid) >= 0;
            return n;
        });
        list.sort((a, b) => (b.active - a.active) || (b.known - a.known) || (b.signal - a.signal));
        root.wifiEnabled = wifiOn;
        root.hasWifiDevice = hasWifi;
        root.kind = kind;
        root.ssid = ssid;
        root.strength = kind === "wifi" ? sig : 0;
        root.saved = saved;
        root.networks = list;
    }

    function setWifi(on) {
        Sys.run(["nmcli", "radio", "wifi", on ? "on" : "off"], function () {
            root.refresh(false);
        });
    }

    // Password (if any) goes through stdin (`--ask`), never through argv.
    function connectTo(ssid, password) {
        root.busySsid = ssid;
        root.lastError = "";
        const done = function (code, out, err) {
            root.busySsid = "";
            if (code !== 0)
                root.lastError = (err || out || "").trim().split("\n").pop();
            root.refresh(false);
        };
        if (password && password.length > 0)
            Sys.run(["nmcli", "--ask", "device", "wifi", "connect", ssid], done, password + "\n");
        else if (root.saved.indexOf(ssid) >= 0)
            Sys.run(["nmcli", "connection", "up", "id", ssid], done);
        else
            Sys.run(["nmcli", "device", "wifi", "connect", ssid], done);
    }

    function disconnectFrom(ssid) {
        Sys.run(["nmcli", "connection", "down", "id", ssid], function () {
            root.refresh(false);
        });
    }

    onAvailableChanged: {
        if (root.available) {
            root.refresh(false);
            monitor.running = true;
        }
    }

    // Any NetworkManager change -> one debounced refresh.
    Process {
        id: monitor

        command: ["nmcli", "monitor"]
        stdout: SplitParser {
            onRead: debounce.restart()
        }
        onExited: restartTimer.start()
    }

    Timer {
        id: restartTimer

        interval: 5000
        onTriggered: {
            if (root.available)
                monitor.running = true;
        }
    }

    Timer {
        id: debounce

        interval: 400
        onTriggered: root.refresh(false)
    }

    Timer {
        interval: 30000
        repeat: true
        running: root.available && root.kind === "wifi"
        onTriggered: root.refresh(false)
    }
}
