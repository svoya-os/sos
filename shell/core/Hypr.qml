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

    Component.onCompleted: {
        refreshTimer.start();
        startupRules.start();
    }

    Timer {
        id: startupRules

        interval: 1500
        onTriggered: root.applyAllWorkspaceRules()
    }
}
