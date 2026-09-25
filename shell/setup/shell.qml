//@ pragma AppId sos.setup
//@ pragma Env QS_NO_RELOAD_POPUP=1

// SOS first-run wizard: `quickshell -p /usr/share/svoya/shell/setup`, started
// by `sos session-start` while ~/.config/svoya/first-run-done is missing, and
// by the shell for Super+Alt+A (SVOYA_SETUP_ONLY=accessibility: that step only).
// Targets Quickshell 0.3.1; core/, components/ and assets/ are the shell's own
// (symlinks), so every change is live: Settings (shell.json) and the theme
// (theme.json) are shared with the running shell.
//
// Seven skippable steps (DESIGN.md §5, design/mockups/setup-*.html):
//   1 accessibility · 2 language & keyboard · 3 look · 4 windows ·
//   5 profile + apps (Obsidian pre-checked) · 6 AI (one suggested local model
//   with a fit bar and «Установить», optional cloud keys) · 7 privacy, first
//   snapshot, keys.
// Choices apply at once (reversible: settings, `sos theme apply`); the model
// downloads while you continue (`sos models pull <id> --yes --json`). Module
// installs need administrator rights, so they start after the wizard hides
// (the polkit prompt must not be covered): `sos modules add --profile … notes
// --yes`, reported with a notification. Cloud keys go to the keyring through
// `secret-tool store` (stdin), never to a file.

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.core
import qs.components

ShellRoot {
    id: root

    settings.watchFiles: false

    // ---- mode and navigation ------------------------------------------------------------------
    property bool single: (Quickshell.env("SVOYA_SETUP_ONLY") || "") === "accessibility"
    property bool open: true
    property var targetScreen: null      // chosen when the wizard opens; not following the mouse
    property int step: 0
    readonly property int count: 7
    readonly property bool last: root.single || root.step === root.count - 1

    function next() {
        if (root.last)
            root.finish();
        else
            root.step += 1;
    }

    function back() {
        if (root.step > 0 && !root.single)
            root.step -= 1;
    }

    function goTo(i) {
        root.step = Math.max(0, Math.min(root.count - 1, i));
    }

    // ---- choices --------------------------------------------------------------------------------
    property string profile: "newcomer"
    property bool offline: false
    property bool obsidian: true

    readonly property string themeChoice: Theme.autoMode ? "auto" : Theme.themeId

    function applyTheme(id) {
        Sys.sos(["theme", "apply", id, "--quiet"]);
    }

    function setKeyboard(layouts, option) {
        Settings.kbLayouts = layouts;
        Settings.kbSwitch = option;
        Settings.kbCustom = true;
    }

    // ---- data from the sos command ------------------------------------------------------------------
    property bool sosMissing: false
    property var suggest: null         // sos models suggest --json
    property var profiles: []          // sos modules profiles --json [--offline]
    property var catalog: ({})         // module id -> row of sos modules list --json
    property var doctor: null          // sos doctor --gpu --json
    property var keys: ({})            // provider -> true when the keyring has a key

    readonly property var providers: [
        { id: "anthropic", name: "Anthropic", sub: "Claude" },
        { id: "gemini", name: "Google", sub: "Gemini" },
        { id: "mistral", name: "Mistral", sub: root.tr("серверы в ЕС", "EU-hosted") },
        { id: "deepseek", name: "DeepSeek", sub: root.tr("серверы в Китае", "hosted in China") }
    ]

    function tr(ru, en) {
        return Strings.t(ru, en);
    }

    function json(text) {
        try {
            return JSON.parse(text);
        } catch (e) {
            return null;
        }
    }

    function loadProfiles() {
        Sys.sos(["modules", "profiles", "--json"].concat(root.offline ? ["--offline"] : []), function (code, out) {
            if (code === 127)
                root.sosMissing = true;
            const j = code === 0 ? root.json(out) : null;
            root.profiles = j && Array.isArray(j.profiles) ? j.profiles : [];
        });
    }

    property bool loaded: false

    function loadAll() {
        root.loaded = true;
        Sys.sos(["models", "suggest", "--json"], function (code, out) {
            if (code === 127)
                root.sosMissing = true;
            root.suggest = code === 0 ? root.json(out) : null;
        });
        root.loadProfiles();
        Sys.sos(["modules", "list", "--json"], function (code, out) {
            const j = code === 0 ? root.json(out) : null;
            const map = {};
            if (j && Array.isArray(j.modules)) {
                for (let i = 0; i < j.modules.length; i++)
                    map[j.modules[i].id] = j.modules[i];
            }
            root.catalog = map;
        });
        Sys.sos(["doctor", "--gpu", "--json"], function (code, out) {
            root.doctor = root.json(out);
        });
        root.checkKeys();
    }

    function checkKeys() {
        if (!Sys.has["secret-tool"])
            return;
        for (let i = 0; i < root.providers.length; i++) {
            const id = root.providers[i].id;
            // the secret never reaches this process: the shell discards it
            Sys.sh('secret-tool lookup service svoya provider "$1" >/dev/null 2>&1', [id], function (code) {
                const k = Object.assign({}, root.keys);
                k[id] = code === 0;
                root.keys = k;
            });
        }
    }

    // callback(ok) after `secret-tool store` read the key from stdin
    function storeKey(provider, key, callback) {
        const label = "SOS: " + provider;
        Sys.run(["secret-tool", "store", "--label=" + label, "service", "svoya", "provider", provider], function (code) {
            if (code === 0) {
                const k = Object.assign({}, root.keys);
                k[provider] = true;
                root.keys = k;
            }
            if (callback)
                callback(code === 0);
        }, key.trim());
    }

    onOfflineChanged: root.loadProfiles()

    // ---- the suggested model: download with progress ---------------------------------------------------
    property string pullState: "idle"     // idle | running | done | error
    property real pullBytes: 0            // finished files + the current one
    property real pullTotal: 0
    property real pullFileBase: 0         // bytes of files already finished
    property string pullError: ""
    readonly property real pullFraction: root.pullTotal > 0 ? Math.min(1, root.pullBytes / root.pullTotal) : 0

    function pullModel() {
        const d = root.suggest ? root.suggest["default"] : null;
        if (!d || root.pullState === "running")
            return;
        root.pullState = "running";
        root.pullError = "";
        root.pullBytes = 0;
        root.pullFileBase = 0;
        root.pullTotal = Number(d.sizeBytes) || 0;
        pull.command = ["sh", "-c", 'c=$(command -v sos || command -v svoya) || exit 127; exec "$c" models pull "$1" --yes --json', "sh", d.id];
        pull.running = true;
    }

    function cancelPull() {
        if (pull.running)
            pull.signal(15);
    }

    function onPullEvent(line) {
        const e = root.json(line);
        if (!e || !e.event)
            return;
        if (e.event === "plan") {
            if (e.totalBytes)
                root.pullTotal = Number(e.totalBytes);
        } else if (e.event === "progress") {
            root.pullBytes = root.pullFileBase + (Number(e.bytes) || 0);
        } else if (e.event === "file-done") {
            // the current file is complete: its size moves into the base
            root.pullFileBase = root.pullBytes;
        } else if (e.event === "done") {
            if (e.ok)
                root.pullState = "done";
        } else if (e.event === "error") {
            root.pullError = e.message || "";
        }
    }

    Process {
        id: pull

        stdout: SplitParser {
            onRead: data => root.onPullEvent(data)
        }
        onExited: function (code, status) {
            if (root.pullState !== "done") {
                root.pullState = "error";
                if (root.pullError.length === 0)
                    root.pullError = code === 127 ? Strings.wzNoSuggest : "exit " + code;
            }
            if (!root.open)
                root.notify(root.pullState === "done" ? Strings.wzModelDone : Strings.wzModelFailed, root.pullState === "done" ? (root.suggest && root.suggest["default"] ? root.suggest["default"].name : "") : root.pullError);
            root.maybeQuit();
        }
    }

    // ---- first snapshot --------------------------------------------------------------------------------
    property string snapState: "idle"     // idle | running | done | error
    property string snapInfo: ""

    function snapshot() {
        if (root.snapState === "running")
            return;
        root.snapState = "running";
        Sys.sos(["snapshot", "create", "--description", "first run", "--json"], function (code, out) {
            const j = root.json(out);
            if (code === 0 && j && j.number !== undefined && j.number !== null) {
                root.snapState = "done";
                root.snapInfo = "#" + j.number;
            } else {
                root.snapState = "error";
                root.snapInfo = j && j.error ? j.error : "";
            }
        });
    }

    // ---- finishing ------------------------------------------------------------------------------------
    property bool installing: false

    readonly property var queuedModules: {
        const out = [];
        const p = root.profiles.find(x => x.id === root.profile);
        if (p && Array.isArray(p.modules)) {
            for (let i = 0; i < p.modules.length; i++) {
                const m = root.catalog[p.modules[i]];
                if (!m || !m.installed)
                    out.push(p.modules[i]);
            }
        }
        if (root.obsidian && !(root.catalog["notes"] && root.catalog["notes"].installed) && out.indexOf("notes") < 0)
            out.push("notes");
        return out;
    }

    function markDone() {
        doneFile.setText("");
    }

    function skipAll() {
        if (!root.single)
            root.markDone();
        root.hide();
    }

    function finish() {
        if (root.single) {
            root.hide();
            return;
        }
        root.markDone();
        root.open = false;
        root.applyJacksonRoute();
        root.startInstall();
        root.maybeQuit();
    }

    // The profile decides where Jackson answers by default (local | auto | cloud); reversible with
    // `jackson undo`. Offline profiles always resolve to "local" (sos modules profiles --offline).
    function applyJacksonRoute() {
        const p = root.profiles.find(x => x.id === root.profile);
        const route = p && p.jacksonRoute;
        if (route !== "local" && route !== "auto" && route !== "cloud")
            return;
        Sys.sh('c=$(command -v jackson || command -v j) || exit 0; exec "$c" route set default "$1"', [route], function (code) {
            if (code !== 0)
                console.warn("setup: could not set Jackson route", route, "exit", code);
        });
    }

    function hide() {
        root.open = false;
        root.maybeQuit();
    }

    function maybeQuit() {
        if (!root.open && !root.installing && root.pullState !== "running")
            Qt.quit();
    }

    function startInstall() {
        const mods = root.queuedModules;
        if (mods.length === 0 || root.sosMissing)
            return;
        root.installing = true;
        root.notify(Strings.wzInstallStarted, mods.map(id => root.moduleName(id)).join(", "));
        installer.command = ["sh", "-c", 'c=$(command -v sos || command -v svoya) || exit 127; exec "$c" modules add "$@" --yes', "sh"].concat(mods).concat(root.offline ? ["--offline"] : []);
        installer.running = true;
    }

    function moduleName(id) {
        const m = root.catalog[id];
        if (m && m.name)
            return Strings.ru ? (m.name.ru || m.name.en || id) : (m.name.en || id);
        return id === "notes" ? "Obsidian" : id;
    }

    function notify(title, body) {
        if (Sys.has["notify-send"])
            Sys.run(["notify-send", "--app-name=SOS", title, body || ""]);
    }

    Process {
        id: installer

        stdout: StdioCollector {
            id: installOut
        }
        stderr: StdioCollector {
            id: installErr
        }
        onExited: function (code, status) {
            root.installing = false;
            if (code === 0)
                root.notify(Strings.wzInstallDone, Strings.wzUndoHint);
            else
                root.notify(Strings.wzInstallFailed, (installErr.text.trim().split("\n").pop() || "") + " · sos modules add " + root.queuedModules.join(" "));
            root.maybeQuit();
        }
    }

    FileView {
        id: doneFile

        path: Settings.configDir + "/first-run-done"
        printErrors: false
        blockWrites: true
    }

    // ---- IPC: the shell's Super+Alt+A reaches a running wizard here ---------------------------------------
    IpcHandler {
        target: "setup"

        function open(step: string): void {
            if (step === "accessibility") {
                if (!root.open)
                    root.single = true;
                root.step = 0;
            } else {
                root.single = false;
                if (!root.loaded)
                    root.loadAll();
            }
            if (!root.open)
                root.targetScreen = Hypr.focusedScreen;
            root.open = true;
        }
        function close(): void {
            root.hide();
        }
    }

    Component.onCompleted: {
        root.targetScreen = Hypr.focusedScreen;
        if (!root.single)
            root.loadAll();
    }

    // ---- the window --------------------------------------------------------------------------------------
    PanelWindow {
        id: win

        visible: root.open
        screen: root.targetScreen
        anchors.top: true
        anchors.bottom: true
        anchors.left: true
        anchors.right: true
        exclusionMode: ExclusionMode.Ignore
        color: Theme.wall

        WlrLayershell.namespace: "svoya-setup"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: root.open ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

        Wallpaper {
            anchors.fill: parent
            showSignal: false
            colophon: false
        }

        // The layout is drawn for 1440×900 and scaled down on smaller screens.
        readonly property real fit: Math.min(1, win.width / 1180, win.height / 880)

        Wizard {
            id: wizardView

            wizard: root
            width: win.width / win.fit
            height: win.height / win.fit
            scale: win.fit
            transformOrigin: Item.TopLeft
            focus: true
        }
    }
}
