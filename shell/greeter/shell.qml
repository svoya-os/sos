//@ pragma AppId sos.greeter
//@ pragma Env QS_NO_RELOAD_POPUP=1

// SOS greeter (greetd): `quickshell -p /usr/share/svoya/shell/greeter`, the only
// client of the small Hyprland started by /usr/lib/svoya/greeter-session with
// /usr/share/svoya/hypr/greeter.conf (-> greeter/hyprland.conf). Runs as the
// unprivileged svoya-greeter user. Targets Quickshell 0.3.1
// (Quickshell.Services.Greetd); core/, components/ and assets/ are symlinks to
// the shell's own directories, so the greeter looks exactly like the lock screen.
//
// Flow: pick a user (tiles; Tab cycles) and a session (footer), type the
// password → Greetd.createSession(user) → answer PAM prompts → readyToLaunch →
// Greetd.launch(session Exec). Multi-step PAM (e.g. a one-time code) shows the
// prompt as the field's placeholder. The last user/session and each user's last
// login are remembered in the greeter's own state dir.
//
// Without greetd (a test run inside a session) the face still works and says so.

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Services.Greetd
import qs.core
import qs.components

ShellRoot {
    id: root

    settings.watchFiles: false

    // ---- data ---------------------------------------------------------------------------------
    property var users: []       // [{name, display, avatar}]
    property var sessions: []    // [{id, name, nameRu, exec, desktopNames, glyph}]
    property int userIndex: 0
    property int sessionIndex: 0

    // ---- authentication state -------------------------------------------------------------------
    property bool busy: false
    property string pending: ""      // password typed before greetd asked for it
    property bool awaiting: false    // greetd asked; the next submit answers
    property string prompt: ""       // PAM prompt text for multi-step logins
    property bool promptEcho: false
    property string message: ""
    property bool failed: false
    property bool a11yOpen: false

    // no users with a login shell in /etc/passwd: type the name first
    readonly property bool manualUser: root.users.length === 0
    property string manualName: ""
    readonly property bool askingName: root.manualUser && root.manualName.length === 0

    readonly property string userName: root.manualUser ? root.manualName : (root.users[root.userIndex] ? root.users[root.userIndex].name : "")

    function selectUser(i) {
        if (root.users.length === 0)
            return;
        const n = (i + root.users.length) % root.users.length;
        if (n === root.userIndex)
            return;
        root.userIndex = n;
        root.resetAuth("");
    }

    function resetAuth(msg) {
        if (Greetd.state !== GreetdState.Inactive)
            Greetd.cancelSession();
        root.busy = false;
        root.pending = "";
        root.awaiting = false;
        root.prompt = "";
        root.promptEcho = false;
        root.failed = false;
        root.message = msg;
        face.item?.clearField();
    }

    function submit(text) {
        if (root.askingName) {
            root.manualName = text.trim();
            face.item?.clearField();
            return;
        }
        if (!Greetd.available) {
            root.failed = true;
            root.message = Strings.greeterError + " (greetd)";
            return;
        }
        root.failed = false;
        root.message = "";
        root.busy = true;
        if (root.awaiting) {
            root.awaiting = false;
            Greetd.respond(text);
            return;
        }
        root.pending = text;
        if (Greetd.state !== GreetdState.Inactive) {
            // greetd answers the cancel with "success"; creating right away would let
            // that answer count as a finished login. Give it a moment first.
            Greetd.cancelSession();
            createLater.restart();
        } else {
            Greetd.createSession(root.userName);
        }
    }

    Timer {
        id: createLater

        interval: 250
        onTriggered: Greetd.createSession(root.userName)
    }

    function launch() {
        const s = root.sessions[root.sessionIndex];
        const exec = s ? s.exec : "/usr/bin/svoya-session";
        const env = ["XDG_SESSION_TYPE=wayland"];
        if (s) {
            env.push("XDG_SESSION_DESKTOP=" + s.id);
            if (s.desktopNames.length > 0)
                env.push("XDG_CURRENT_DESKTOP=" + s.desktopNames);
        }
        // remember before quitting (writes block, see memoryFile)
        const logins = Object.assign({}, memory.lastLogins);
        logins[root.userName] = new Date().toISOString();
        memory.lastLogins = logins;
        memory.lastUser = root.userName;
        memory.lastSession = s ? s.id : "";
        Greetd.launch([exec], env, true);
    }

    function lastLoginText(name, now) {
        const iso = memory.lastLogins[name];
        return iso ? Strings.lastLogin(new Date(iso), now) : "";
    }

    Connections {
        target: Greetd

        function onAuthMessage(message, error, responseRequired, echoResponse) {
            if (responseRequired) {
                if (root.pending.length > 0 && !echoResponse) {
                    const p = root.pending;
                    root.pending = "";
                    Greetd.respond(p);
                } else {
                    // another question (one-time code, new password…): ask in the field
                    root.pending = "";
                    root.awaiting = true;
                    root.busy = false;
                    root.prompt = message.trim().replace(/:$/, "");
                    root.promptEcho = echoResponse;
                    face.item?.clearField();
                }
            } else if (message.length > 0) {
                root.message = message.trim();
                root.failed = error;
            }
        }

        function onReadyToLaunch() {
            root.launch();
        }

        function onAuthFailure(message) {
            root.busy = false;
            root.pending = "";
            root.awaiting = false;
            root.prompt = "";
            root.promptEcho = false;
            root.failed = true;
            root.message = Strings.wrongPassword;
            face.item?.clearField();
        }

        function onError(error) {
            root.busy = false;
            root.pending = "";
            root.awaiting = false;
            root.failed = true;
            root.message = Strings.greeterError;
            console.warn("greetd:", error);
        }
    }

    // ---- remembered choices (the greeter user's state dir) ----------------------------------------
    FileView {
        id: memoryFile

        path: Quickshell.statePath("greeter.json")
        printErrors: false
        blockWrites: true          // the process exits right after launch()
        onAdapterUpdated: writeAdapter()
        onLoaded: root.applyMemory()
        onLoadFailed: root.applyMemory()

        JsonAdapter {
            id: memory

            property string lastUser: ""
            property string lastSession: ""
            property var lastLogins: ({})
        }
    }

    property bool usersLoaded: false
    property bool sessionsLoaded: false
    property bool memoryApplied: false

    function applyMemory() {
        if (!root.usersLoaded || !root.sessionsLoaded)
            return;
        root.memoryApplied = true;
        for (let i = 0; i < root.users.length; i++) {
            if (root.users[i].name === memory.lastUser)
                root.userIndex = i;
        }
        let si = 0;
        for (let j = 0; j < root.sessions.length; j++) {
            if (root.sessions[j].id === memory.lastSession)
                si = j;
        }
        root.sessionIndex = si;
    }

    // ---- users: /etc/passwd, uid 1000–59999 with a login shell -----------------------------------
    FileView {
        id: passwd

        path: "/etc/passwd"
        printErrors: false
        onLoaded: {
            const out = [];
            const lines = passwd.text().split("\n");
            for (let i = 0; i < lines.length; i++) {
                const f = lines[i].split(":");
                if (f.length < 7)
                    continue;
                const uid = Number(f[2]);
                if (!(uid >= 1000 && uid < 60000) || /(nologin|false)$/.test(f[6]))
                    continue;
                const gecos = (f[4] || "").split(",")[0].trim();
                out.push({
                    name: f[0],
                    display: gecos.length > 0 ? gecos : f[0],
                    avatar: "/var/lib/AccountsService/icons/" + f[0]
                });
            }
            root.users = out;
            root.usersLoaded = true;
            root.applyMemory();
        }
        onLoadFailed: {
            root.usersLoaded = true;
            root.applyMemory();
        }
    }

    // ---- sessions: /usr/share/wayland-sessions/*.desktop, SOS first ---------------------------------
    Process {
        id: sessionScan

        running: true
        command: ["sh", "-c", "for f in /usr/share/wayland-sessions/*.desktop; do [ -f \"$f\" ] || continue; printf '@@%s\\n' \"$(basename \"$f\" .desktop)\"; cat \"$f\"; printf '\\n'; done"]
        stdout: StdioCollector {
            id: sessionOut
        }
        onExited: {
            const blocks = sessionOut.text.split("@@");
            const out = [];
            for (let b = 0; b < blocks.length; b++) {
                const lines = blocks[b].split("\n");
                const id = lines[0].trim();
                if (id.length === 0)
                    continue;
                const e = { id: id, name: id, nameRu: "", exec: "", desktopNames: "", hidden: false };
                let inEntry = false;
                for (let i = 1; i < lines.length; i++) {
                    const l = lines[i].trim();
                    if (l.startsWith("[")) {
                        inEntry = l === "[Desktop Entry]";
                        continue;
                    }
                    if (!inEntry)
                        continue;
                    const eq = l.indexOf("=");
                    if (eq < 0)
                        continue;
                    const k = l.slice(0, eq).trim();
                    const v = l.slice(eq + 1).trim();
                    if (k === "Name")
                        e.name = v;
                    else if (k === "Name[ru]")
                        e.nameRu = v;
                    else if (k === "Exec")
                        e.exec = v.replace(/\s+%[fFuUdDnNickvm]/g, "");
                    else if (k === "DesktopNames")
                        e.desktopNames = v.replace(/;+$/, "").replace(/;/g, ":");
                    else if ((k === "NoDisplay" || k === "Hidden") && v === "true")
                        e.hidden = true;
                }
                if (!e.hidden && e.exec.length > 0) {
                    e.glyph = id === "sos" ? "svoya-windows" : "svoya-tiles";
                    out.push(e);
                }
            }
            out.sort((a, b) => (a.id === "sos" ? -1 : b.id === "sos" ? 1 : a.name.localeCompare(b.name)));
            root.sessions = out;
            root.sessionsLoaded = true;
            root.applyMemory();
        }
    }

    // ---- windows: the face on the focused screen, the wallpaper everywhere else ---------------------
    Variants {
        model: Quickshell.screens

        PanelWindow {
            id: win

            required property var modelData
            readonly property bool main: modelData === root.mainScreen

            screen: modelData
            anchors.top: true
            anchors.bottom: true
            anchors.left: true
            anchors.right: true
            exclusionMode: ExclusionMode.Ignore
            color: Theme.wall

            WlrLayershell.namespace: "svoya-greeter"
            WlrLayershell.layer: WlrLayer.Top
            WlrLayershell.keyboardFocus: win.main ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

            Wallpaper {
                anchors.fill: parent
                visible: !win.main
                colophon: true
                ambient: false
            }

            Loader {
                id: faceLoader

                anchors.fill: parent
                active: win.main
                focus: true
                sourceComponent: Face {
                    greeter: root
                    focus: true
                    Component.onCompleted: Qt.callLater(focusField)

                    Keys.onTabPressed: root.selectUser(root.userIndex + 1)
                    Keys.onBacktabPressed: root.selectUser(root.userIndex - 1)
                    Keys.onEscapePressed: {
                        if (root.a11yOpen)
                            root.a11yOpen = false;
                        else
                            root.resetAuth("");
                    }
                    Keys.onPressed: event => {
                        if (event.key === Qt.Key_A && (event.modifiers & Qt.MetaModifier) && (event.modifiers & Qt.AltModifier)) {
                            root.a11yOpen = !root.a11yOpen;
                            event.accepted = true;
                        }
                    }
                }
                onLoaded: face.item = faceLoader.item
            }
        }
    }

    // The face stays on the screen that was focused at start (the mouse moving to
    // another output must not move it and lose what was typed); if that output
    // goes away, the first one takes over.
    property var mainScreen: null

    function pickScreen() {
        const screens = Quickshell.screens;
        for (let i = 0; i < screens.length; i++) {
            if (screens[i] === root.mainScreen)
                return;
        }
        root.mainScreen = Hypr.focusedScreen ? Hypr.focusedScreen : (screens.length > 0 ? screens[0] : null);
    }

    Component.onCompleted: root.pickScreen()

    Connections {
        target: Quickshell

        function onScreensChanged() {
            root.pickScreen();
        }
    }

    // the Face that has the keyboard (on the focused screen)
    QtObject {
        id: face

        property var item: null
    }
}
