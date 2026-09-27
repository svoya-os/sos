pragma Singleton

// Hyprland glue: focused screen, dispatch in either config syntax
// (hyprlang or Lua, Quickshell's Hyprland.usingLua), keyboard layout and the
// per-workspace tiling toggle (Super+T).

import QtQuick
import Quickshell
import Quickshell.Hyprland

Singleton {
    id: root

    readonly property bool present: (Quickshell.env("HYPRLAND_INSTANCE_SIGNATURE") || "").length > 0

    // The Quickshell screen that Hyprland currently focuses (falls back to the first).
    readonly property var focusedScreen: {
        const mon = Hyprland.focusedMonitor;
        const screens = Quickshell.screens;
        if (mon) {
            for (let i = 0; i < screens.length; i++) {
                if (screens[i].name === mon.name)
                    return screens[i];
            }
        }
        return screens.length > 0 ? screens[0] : null;
    }

    readonly property int activeWorkspaceId: Hyprland.focusedWorkspace ? Hyprland.focusedWorkspace.id : 1

    // ---- dispatch ---------------------------------------------------------------
    // `legacy` is hyprlang dispatcher syntax ("workspace 3"); `lua` the Lua form
    // ("hl.dsp.focus({ workspace = 3 })"). Pass both where they differ.
    function dispatch(legacy, lua) {
        if (!root.present)
            return;
        if (Hyprland.usingLua && lua)
            Hyprland.dispatch(lua);
        else
            Hyprland.dispatch(legacy);
    }

    function focusWorkspace(id) {
        root.dispatch("workspace " + id, "hl.dsp.focus({ workspace = " + id + " })");
    }

    function relativeWorkspace(delta) {
        const d = delta > 0 ? "e+1" : "e-1";
        root.dispatch("workspace " + d, "hl.dsp.focus({ workspace = \"" + d + "\" })");
    }

    // ---- keyboard layout -------------------------------------------------------
    property string layoutCode: ""      // "RU", "EN"… for the bar
    property int layoutCount: 1         // layouts to switch between (a wrong-password hint names the layout only when > 1)
    property string keyboardName: ""

    function refreshLayout() {
        if (!root.present)
            return;
        Sys.run(["hyprctl", "-j", "devices"], function (code, out) {
            if (code !== 0)
                return;
            try {
                const kbs = JSON.parse(out).keyboards || [];
                let kb = null;
                for (let i = 0; i < kbs.length; i++) {
                    if (kbs[i].main) {
                        kb = kbs[i];
                        break;
                    }
                }
                if (!kb && kbs.length > 0)
                    kb = kbs[kbs.length - 1];
                if (!kb)
                    return;
                root.keyboardName = kb.name;
                const layouts = (kb.layout || "").split(",");
                root.layoutCount = Math.max(1, layouts.filter(l => l.trim().length > 0).length);
                const idx = kb.active_layout_index !== undefined ? kb.active_layout_index : 0;
                root.layoutCode = root.shortLayout(layouts[idx] || "", kb.active_keymap || "");
            } catch (e) {}
        });
    }

    // "us" -> "EN" (the Latin layout reads as the language), "ru" -> "RU".
    function shortLayout(code, keymap) {
        const c = (code || "").trim().toLowerCase();
        if (c === "us" || c === "gb")
            return "EN";
        if (c.length > 0)
            return c.slice(0, 2).toUpperCase();
        const k = (keymap || "").toLowerCase();
        if (k.indexOf("russian") === 0)
            return "RU";
        if (k.indexOf("english") === 0)
            return "EN";
        return k.slice(0, 2).toUpperCase();
    }

    function nextLayout() {
        if (!root.present)
            return;
        Sys.run(["hyprctl", "switchxkblayout", root.keyboardName.length > 0 ? root.keyboardName : "all", "next"], function () {
            root.refreshLayout();
        });
    }

    Connections {
        target: root.present ? Hyprland : null

        function onRawEvent(event) {
            if (event.name === "activelayout") {
                // data: KEYBOARDNAME,LAYOUTNAME
                const parts = event.parse(2);
                if (parts.length === 2) {
                    const code = root.shortLayout("", parts[1]);
                    if (code.length > 0)
                        root.layoutCode = code;
                }
                refreshTimer.restart();
            } else if (event.name === "configreloaded") {
                refreshTimer.restart();
            }
        }
    }

    // Debounced authoritative refresh (the event only carries the keymap name).
    Timer {
        id: refreshTimer

        interval: 150
        onTriggered: root.refreshLayout()
    }

    // ---- tiling toggle (Super+T) ----------------------------------------------------
    // Presets: clean/classic float new windows by default, hacker tiles them.
    // Settings.tiledWorkspaces lists workspaces that differ from the preset default.
    // Each preset declares disabled named rules svoya-ws<N> (N = 1..10) that
    // flip the default for new windows on that workspace; we enable/disable them
    // with `hyprctl keyword` and convert the windows already there.
    readonly property bool presetTiles: Settings.layout === "hacker"

    function workspaceTiled(id) {
        const exceptions = Settings.tiledWorkspaces || [];
        const flipped = exceptions.indexOf(id) >= 0;
        return root.presetTiles ? !flipped : flipped;
    }

    function toggleTiling() {
        const id = root.activeWorkspaceId;
        if (id < 1)
            return;
        const list = (Settings.tiledWorkspaces || []).slice();
        const at = list.indexOf(id);
        if (at >= 0)
            list.splice(at, 1);
        else
            list.push(id);
        Settings.tiledWorkspaces = list;
        root.applyWorkspaceRule(id, at < 0);
        const tiled = root.workspaceTiled(id);
        root.convertWorkspace(id, tiled);
        Notifs.shellToast(tiled ? Strings.tilingOn : Strings.tilingOff, Strings.workspace + " " + id, "layout-grid");
    }

    function applyWorkspaceRule(id, enabled) {
        if (!root.present || id > 10)
            return;
        Sys.run(["hyprctl", "keyword", "windowrule[svoya-ws" + id + "]:enable", enabled ? "true" : "false"]);
    }

    // Re-apply every exception after Hyprland (re)loads its config.
    function applyAllWorkspaceRules() {
        const list = Settings.tiledWorkspaces || [];
        for (let i = 0; i < list.length; i++)
            root.applyWorkspaceRule(list[i], true);
    }

    function convertWorkspace(id, tiled) {
        Sys.run(["hyprctl", "-j", "clients"], function (code, out) {
            if (code !== 0)
                return;
            let clients = [];
            try {
                clients = JSON.parse(out);
            } catch (e) {
                return;
            }
            const batch = [];
            for (let i = 0; i < clients.length; i++) {
                const c = clients[i];
                if (!c.workspace || c.workspace.id !== id || c.pinned)
                    continue;
                if (tiled && c.floating)
                    batch.push("dispatch settiled address:" + c.address);
                else if (!tiled && !c.floating)
                    batch.push("dispatch setfloating address:" + c.address);
            }
            if (batch.length > 0)
                Sys.run(["hyprctl", "--batch", batch.join(" ; ")]);
        });
    }

    Connections {
        target: root.present ? Hyprland : null

        function onRawEvent(event) {
            if (event.name === "configreloaded")
                root.applyAllWorkspaceRules();
        }
    }

    // ---- show the desktop (Super+D, three fingers down) ------------------------------------------
    // Hyprland has no minimizing: the windows of this workspace go to a hidden special workspace
    // and come back to their desktops with the next Super+D.
    property var desktopHidden: []      // [{address, workspace}]
    property string desktopFocus: ""    // the window that had the keyboard: it gets it back

    function toggleDesktop() {
        if (!root.present)
            return;
        if (root.desktopHidden.length > 0) {
            const batch = root.desktopHidden.map(w => "dispatch movetoworkspacesilent " + w.workspace + ",address:" + w.address);
            if (root.desktopFocus.length > 0)
                batch.push("dispatch focuswindow address:" + root.desktopFocus);
            root.desktopHidden = [];
            root.desktopFocus = "";
            Sys.run(["hyprctl", "--batch", batch.join(" ; ")]);
            return;
        }
        const id = root.activeWorkspaceId;
        Sys.run(["hyprctl", "-j", "clients"], function (code, out) {
            if (code !== 0)
                return;
            let clients = [];
            try {
                clients = JSON.parse(out);
            } catch (e) {
                return;
            }
            // windows left hidden by a shell that restarted in between come back here
            const stranded = clients.filter(c => c.workspace && c.workspace.name === "special:svoya-desktop");
            if (stranded.length > 0) {
                Sys.run(["hyprctl", "--batch", stranded.map(c => "dispatch movetoworkspacesilent " + id + ",address:" + c.address).join(" ; ")]);
                return;
            }
            const here = clients.filter(c => c.workspace && c.workspace.id === id && !c.pinned && c.mapped !== false);
            const hidden = here.map(c => ({ address: c.address, workspace: id }));
            if (hidden.length === 0)
                return;
            const focused = here.find(c => c.focusHistoryID === 0);
            root.desktopFocus = focused ? String(focused.address) : "";
            root.desktopHidden = hidden;
            Sys.run(["hyprctl", "--batch", hidden.map(w => "dispatch movetoworkspacesilent special:svoya-desktop,address:" + w.address).join(" ; ")]);
        });
    }

    // ---- game mode (Win+G, Settings.focusMode "game") ---------------------------------------------
    // No blur, shadows, rounding, gaps or animations while a game runs, and a stray tap of the
    // Windows key does not open the launcher over it; the power profile goes to performance and
    // back; notifications are held (Notifs.dnd). Leaving it reloads the config.
    readonly property bool gaming: Settings.focusMode === "game"

    function toggleGameMode() {
        Settings.focusMode = root.gaming ? "" : "game";
        Notifs.shellToast(root.gaming ? Strings.gameModeOn : Strings.gameModeOff, root.gaming ? Strings.gameModeNote : "", "gamepad-2");
    }

    function applyGameMode(on) {
        if (!root.present)
            return;
        if (on) {
            Sys.run(["hyprctl", "--batch", ["keyword animations:enabled 0", "keyword decoration:blur:enabled 0", "keyword decoration:shadow:enabled 0", "keyword decoration:rounding 0", "keyword general:gaps_in 0", "keyword general:gaps_out 0", "keyword decoration:screen_shader [[EMPTY]]", "keyword unbind SUPER,SUPER_L", "keyword unbind SUPER,SUPER_R"].join(" ; ")]);
            // the profile it had goes into shell.json, so it comes back even after a restart
            Sys.sh('command -v powerprofilesctl >/dev/null || exit 0; p=$(powerprofilesctl get) && echo "$p" && powerprofilesctl set performance', [], function (code, out) {
                const before = (out || "").trim();
                if (code === 0 && before.length > 0 && before !== "performance" && !Settings.gamePowerBefore)
                    Settings.gamePowerBefore = before;
                Power.refresh();
            });
        } else {
            Sys.run(["hyprctl", "reload"]);     // the configured look back (configreloaded re-applies rules and the night light)
            if (Settings.gamePowerBefore) {
                Sys.sh('command -v powerprofilesctl >/dev/null && powerprofilesctl set "$1"', [Settings.gamePowerBefore], () => Power.refresh());
                Settings.gamePowerBefore = "";
            }
        }
    }

    // game mode is kept like the other focus modes: a new session (or a restarted shell) puts it
    // back on when shell.json is read (before that, focusMode is its default "")
    function syncGameMode() {
        if (root.gaming !== root.gameApplied) {
            root.gameApplied = root.gaming;
            root.applyGameMode(root.gaming);
        }
    }

    Connections {
        target: Settings

        function onFocusModeChanged() {
            root.syncGameMode();
        }
    }
    property bool gameApplied: false

    // ---- night light (Control Center): a warm screen in the evening -------------------------------
    // A Hyprland screen shader (hypr/shaders/night-light.frag). "auto" follows the evening: the
    // hours Jackson speaks calmer (`j voice evening 21:00-07:00`, reported in voiceSettings), else
    // shell.json's nightFrom–nightTo; a game turns it off while it runs.
    readonly property string nightShader: (Quickshell.env("SVOYA_HYPR_DIR") || "/usr/share/svoya/hypr") + "/shaders/night-light.frag"
    property bool nightApplied: false
    readonly property var nightHours: {
        const vs = Jackson.voiceSettings;
        const m = /^\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*$/.exec(vs && vs.evening ? String(vs.evening) : "");
        return m ? [m[1], m[2]] : [Settings.nightFrom, Settings.nightTo];
    }
    readonly property bool nightWanted: {
        const mode = Settings.nightLight;
        if (root.gaming || mode === "off")
            return false;
        return mode === "on" || root.inHours(clock.minutes, root.nightHours[0], root.nightHours[1]);
    }

    function minutesOf(hhmm, fallback) {
        const m = /^\s*(\d{1,2}):(\d{2})\s*$/.exec(String(hhmm));
        return m ? Math.min(23, Number(m[1])) * 60 + Math.min(59, Number(m[2])) : fallback;
    }

    function inHours(now, from, to) {
        const a = root.minutesOf(from, 20 * 60);
        const b = root.minutesOf(to, 7 * 60);
        return a < b ? (now >= a && now < b) : (now >= a || now < b);
    }

    function updateNightLight(force) {
        if (!root.present || (!force && root.nightWanted === root.nightApplied))
            return;
        root.nightApplied = root.nightWanted;
        Sys.run(["hyprctl", "keyword", "decoration:screen_shader", root.nightWanted ? root.nightShader : "[[EMPTY]]"]);
    }

    onNightWantedChanged: root.updateNightLight()

    QtObject {
        id: clock

        property int minutes: 0
    }

    Timer {
        interval: 30000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            const d = new Date();
            clock.minutes = d.getHours() * 60 + d.getMinutes();
        }
    }

    Connections {
        target: root.present ? Hyprland : null

        function onRawEvent(event) {
            if (event.name === "configreloaded" && root.nightApplied)
                root.updateNightLight(true);
        }
    }

    Component.onCompleted: {
        refreshTimer.start();
        startupRules.start();
        root.syncGameMode();
    }

    Timer {
        id: startupRules

        interval: 1500
        onTriggered: root.applyAllWorkspaceRules()
    }
}
