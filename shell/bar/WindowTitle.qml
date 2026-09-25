import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.core
import qs.components

// Active window: app name (text) / detail (textDim), Plex Sans 12.5.
// "kitty: ~/ai/projects/tts-finetune" reads as «Терминал / tts-finetune».
Item {
    id: root

    property var screen: null
    readonly property var toplevel: ToplevelManager.activeToplevel
    readonly property bool here: {
        const t = root.toplevel;
        if (!t || !root.screen)
            return false;
        const screens = t.screens;
        if (!screens || screens.length === 0)
            return Hypr.focusedScreen === root.screen;
        for (let i = 0; i < screens.length; i++) {
            if (screens[i] && screens[i].name === root.screen.name)
                return true;
        }
        return false;
    }
    readonly property var entry: root.toplevel && root.toplevel.appId ? DesktopEntries.heuristicLookup(root.toplevel.appId) : null
    readonly property string appName: {
        const e = root.entry;
        if (e) {
            const cats = e.categories || [];
            if (cats.indexOf("TerminalEmulator") >= 0)
                return Strings.terminal;
            if (cats.indexOf("FileManager") >= 0)
                return Strings.files;
            return e.name;
        }
        const id = root.toplevel ? root.toplevel.appId || "" : "";
        const last = id.split(".").pop();
        return last.length > 0 ? last[0].toUpperCase() + last.slice(1) : "";
    }
    readonly property string detail: {
        let t = root.toplevel ? (root.toplevel.title || "").trim() : "";
        if (t.length === 0 || t === root.appName)
            return "";
        const names = [root.appName, root.entry ? root.entry.name : "", root.toplevel ? root.toplevel.appId : ""];
        for (let i = 0; i < names.length; i++) {
            const n = names[i];
            if (!n)
                continue;
            for (const sep of [" — ", " – ", " - ", ": "]) {
                if (t.endsWith(sep + n))
                    t = t.slice(0, t.length - sep.length - n.length);
                if (t.startsWith(n + sep))
                    t = t.slice(n.length + sep.length);
            }
        }
        // shell-style titles: "user@host: ~/a/b" -> "b"
        const colon = t.lastIndexOf(": ");
        if (colon >= 0 && /[~\/]/.test(t.slice(colon + 2, colon + 3)))
            t = t.slice(colon + 2);
        if (t.startsWith("~/") || t.startsWith("/")) {
            const parts = t.split("/").filter(p => p.length > 0);
            t = parts.length > 0 ? parts[parts.length - 1] : t;
        }
        return t === root.appName ? "" : t;
    }

    implicitHeight: 18
    implicitWidth: row.implicitWidth
    visible: root.here && root.appName.length > 0
    clip: true

    Row {
        id: row

        anchors.verticalCenter: parent.verticalCenter
        spacing: 0

        SText {
            id: app

            text: root.appName
            size: Theme.fsWindowTitle
            color: Theme.text
        }

        SText {
            visible: root.detail.length > 0
            leftPadding: 6
            rightPadding: 6
            text: "/"
            size: Theme.fsWindowTitle
            color: Theme.textFaint
        }

        SText {
            visible: root.detail.length > 0
            width: Math.max(0, Math.min(implicitWidth, root.width - app.width - 20))
            text: root.detail
            size: Theme.fsWindowTitle
            color: Theme.textDim
            elide: Text.ElideMiddle
        }
    }
}
