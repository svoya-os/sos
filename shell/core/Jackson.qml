pragma Singleton

// Client for jacksond: $XDG_RUNTIME_DIR/svoya/jackson.sock, JSON Lines
// (docs/ARCHITECTURE.md §4.3).
//
// client -> daemon: hello, ask, approve, cancel, status, undo
// daemon -> client: welcome, route, token, tool, approval, done, error, state
//
// Jackson is a character in the UI (never "daemon" in user-facing text). The
// service sends `persona`, `avatar` ("auto" | "imp" | "cat" | "none") and
// `mood` with welcome/status/state events; JacksonAvatar.qml renders them.
//
// Reconnects with exponential backoff (0.5 s … 30 s). Quickshell's Socket cannot
// redial after a failed attempt, so every attempt uses a fresh Socket from a
// Loader. The socket file is probed first so a missing daemon costs one tiny
// `test -S` every 30 s and no log noise. When the AI switch is off
// (Status.aiEnabled == false) nothing connects at all.

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    readonly property string clientVersion: "0.1.0"
    readonly property string socketPath: Sys.runtimeDir + "/jackson.sock"

    readonly property bool enabled: Status.aiEnabled
    property bool connected: false
    property bool welcomed: false
    property string daemonVersion: ""
    property var models: []
    property var capabilities: []
    readonly property bool voice: root.capabilities.indexOf("voice") >= 0

    // Character: persona {id, name, humor}, mascot and mood from the service.
    property var persona: null
    property string avatar: "auto"
    property string mood: "calm"      // calm listening thinking busy talking asking sorry
    property string displayName: ""   // «Джексон» / "Jackson" from welcome
    // The name lives in ~/.config/svoya/avatar.json (Avatar); the daemon reads the same file.
    readonly property string name: Avatar.name.length > 0 ? Avatar.name : (root.displayName.length > 0 ? root.displayName : Strings.jackson)
    property real happyUntil: 0       // a short "happy" beat after an answer (avatar)

    // Routes: the default (welcome/status) and the current turn's route.
    property var defaultRoute: null
    property var route: null
    readonly property var shownRoute: root.route ? root.route : root.defaultRoute

    // Scope state (drives Oscilloscope.qml): idle listening thinking working speaking error offline off
    property string daemonState: "idle"
    property bool listening: false // local push-to-talk while the daemon supports voice
    readonly property string mode: {
        if (!root.enabled)
            return "off";
        if (!root.connected)
            return "offline";
        if (root.error && !root.busy)
            return "error";
        if (root.listening)
            return "listening";
        return root.daemonState;
    }
    readonly property bool active: root.mode !== "idle" && root.mode !== "offline" && root.mode !== "off"
    // The live signal (DESIGN §5, §11): the Morse mark and the bar scope light up only now.
    readonly property bool signalLive: root.mode === "listening" || root.mode === "thinking" || root.mode === "working" || root.mode === "speaking"

    // Persona and humor go through Jackson's own CLI (`j persona set <id>`, `j persona humor 0-2`),
    // which validates them and tells the daemon; the next welcome/state event reports them back.
    readonly property var personas: ["kent", "sysop", "dispatcher", "pirate"]
    readonly property string personaId: root.persona && typeof root.persona.id === "string" ? root.persona.id : "kent"
    readonly property int humor: root.persona && root.persona.humor !== undefined ? Number(root.persona.humor) : 1

    // Both change how Jackson sounds on the login screen too («кент» or plain): the exported copy follows.
    function setPersona(id) {
        root.persona = Object.assign({}, root.persona || {}, { id: id });
        Sys.sh('c=$(command -v jackson || command -v j) || exit 127; exec "$c" persona set "$1"', [id], root.syncLoginVoice);
    }

    function setHumor(level) {
        root.persona = Object.assign({}, root.persona || {}, { humor: level });
        Sys.sh('c=$(command -v jackson || command -v j) || exit 127; exec "$c" persona humor "$1"', [String(level)], root.syncLoginVoice);
    }

    function syncLoginVoice(code) {
        if (code === 0)
            Theme.queueSystemSync();
    }

    // Current turn (the panel shows one turn at a time, like a command palette).
    property string turnId: ""
    property string question: ""
    property string answer: ""
    property var tools: []          // [{callId, name, args, tier, state, summary}]
    property var approvals: []      // pending [{callId, name, preview, tier}]
    property var decisions: ({})    // callId -> "once" | "always-project" | "deny"
    property var result: null       // the `done` event
    property var error: null        // {message, retryable, code}: code "no_local_model" on a fresh system
    property var progress: null     // {done, total}: how far a local model has read the request (minutes on a CPU)
    property bool busy: false
    property var suggestions: []    // optional done.suggestions: [{id, label, primary, prompt}]
    property string screenshot: ""  // path attached to the next ask
    property string lastText: ""
    property var lastContext: null

    signal turnFinished(var info)

    // ---- requests -------------------------------------------------------------------
    function newId() {
        return "t" + Date.now().toString(36) + Math.floor(Math.random() * 46656).toString(36);
    }

    function send(obj) {
        if (!root.link || !root.connected)
            return false;
        root.link.write(JSON.stringify(obj) + "\n");
        root.link.flush();
        return true;
    }

    // Start a turn. `refines` (optional) is the id of the turn being refined; the
    // daemon may use it (extension field, ignored by older daemons).
    function ask(text, refines) {
        const t = (text || "").trim();
        if (t.length === 0)
            return false;
        const id = root.newId();
        const msg = { type: "ask", id: id, text: t, route: "auto" };
        const context = {};
        if (root.screenshot.length > 0)
            context.screenshot = root.screenshot;
        if (Object.keys(context).length > 0)
            msg.context = context;
        if (refines)
            msg.refines = refines;
        root.resetTurn();
        root.turnId = id;
        root.question = t;
        root.lastText = t;
        root.lastContext = msg.context || null;
        root.busy = true;
        root.daemonState = "thinking";
        root.screenshot = "";
        if (!root.send(msg)) {
            root.busy = false;
            root.daemonState = "idle";
            root.error = { message: Strings.jacksonOfflineBody, retryable: true };
            return false;
        }
        return true;
    }

    function retry() {
        if (root.lastText.length > 0) {
            if (root.lastContext && root.lastContext.screenshot)
                root.screenshot = root.lastContext.screenshot;
            root.ask(root.lastText);
        }
    }

    function approve(callId, decision) {
        const d = Object.assign({}, root.decisions);
        d[callId] = decision;
        root.decisions = d;
        root.approvals = root.approvals.filter(a => a.callId !== callId);
        root.send({ type: "approve", id: root.turnId, callId: callId, decision: decision });
    }

    function cancel() {
        if (!root.busy)
            return;
        root.send({ type: "cancel", id: root.turnId });
        root.busy = false;
        root.approvals = [];
        root.daemonState = "idle";
        root.answer = root.answer.length > 0 ? root.answer : Strings.turnCancelled;
    }

    function undo(actionId) {
        const msg = { type: "undo" };
        if (actionId)
            msg.actionId = actionId;
        return root.send(msg);
    }

    function requestStatus() {
        root.send({ type: "status" });
    }

    // Push-to-talk (extension, only when the daemon advertises "voice").
    function listen(on) {
        if (!root.voice) {
            root.listening = false;
            return;
        }
        if (on === root.listening)
            return;
        root.listening = on;
        if (on) {
            root.resetTurn();
            root.turnId = root.newId();
            root.busy = true;
        }
        root.send({ type: "listen", id: root.turnId, action: on ? "start" : "stop" });
    }

    function resetTurn() {
        root.turnId = "";
        root.question = "";
        root.answer = "";
        root.tools = [];
        root.approvals = [];
        root.decisions = ({});
        root.result = null;
        root.error = null;
        root.progress = null;
        root.route = null;
        root.suggestions = [];
    }

    // ---- events ----------------------------------------------------------------------
    function normalizeRoute(r) {
        if (!r)
            return null;
        if (typeof r === "string")
            return { model: "", provider: "", local: r !== "cloud", mode: r };
        return {
            model: r.model || "",
            provider: r.provider || "",
            label: r.label || "",
            local: r.local !== false,
            mode: r.mode || "",
            reason: r.reason || ""
        };
    }

    function firstLocalModel() {
        for (let i = 0; i < root.models.length; i++) {
            const m = root.models[i];
            if (m && m.local && m.available !== false && m.model)
                return root.normalizeRoute({ model: m.model, provider: m.provider, label: m.label, local: true });
        }
        return null;
    }

    function applyCharacter(msg) {
        if (msg.persona !== undefined && msg.persona !== null)
            root.persona = typeof msg.persona === "string" ? Object.assign({}, root.persona || {}, { id: msg.persona }) : msg.persona;
        if (typeof msg.avatar === "string" && msg.avatar.length > 0)
            root.avatar = msg.avatar;
        if (typeof msg.mood === "string" && msg.mood.length > 0)
            root.mood = msg.mood;
        if (typeof msg.name === "string" && msg.name.length > 0)
            root.displayName = msg.name;
    }

    function handleLine(line) {
        if (!line || line.length === 0)
            return;
        let msg;
        try {
            msg = JSON.parse(line);
        } catch (e) {
            console.warn("svoya: jackson: bad line:", line.slice(0, 120));
            return;
        }
        if (!msg || typeof msg.type !== "string")
            return;
        // Turn-scoped events for another turn (e.g. from the CLI) are ignored.
        const foreign = msg.id !== undefined && msg.id !== null && root.turnId.length > 0 && msg.id !== root.turnId;

        switch (msg.type) {
        case "welcome":
            root.welcomed = true;
            root.daemonVersion = msg.version || "";
            root.models = Array.isArray(msg.models) ? msg.models : [];
            root.capabilities = Array.isArray(msg.capabilities) ? msg.capabilities : [];
            root.defaultRoute = root.normalizeRoute(msg.route) || root.firstLocalModel();
            root.applyCharacter(msg);
            break;
        case "status":
            if (msg.route)
                root.defaultRoute = root.normalizeRoute(msg.route);
            if (Array.isArray(msg.models))
                root.models = msg.models;
            if (typeof msg.state === "string")
                root.daemonState = msg.state;
            root.applyCharacter(msg);
            break;
        case "state":
            {
                // State events are aggregated over every client (the CLI `j` too),
                // so the scope honestly shows Jackson working for someone else.
                const s = msg.state || msg.value;
                if (typeof s === "string")
                    root.daemonState = s;
                if (s === "idle" && !foreign)
                    root.listening = false;
                root.applyCharacter(msg);
            }
            break;
        case "route":
            if (!foreign)
                root.route = root.normalizeRoute(msg);
            break;
        case "progress":
            if (!foreign && Number(msg.total) > 0)
                root.progress = { done: Number(msg.done) || 0, total: Number(msg.total) };
            break;
        case "token":
            if (!foreign && typeof msg.text === "string") {
                root.answer += msg.text;
                root.progress = null;
            }
            break;
        case "tool":
            if (!foreign) {
                const list = root.tools.slice();
                let found = false;
                for (let i = 0; i < list.length; i++) {
                    if (list[i].callId === msg.callId) {
                        list[i] = Object.assign({}, list[i], msg);
                        found = true;
                    }
                }
                if (!found)
                    list.push(msg);
                root.tools = list;
            }
            break;
        case "approval":
            if (!foreign)
                root.approvals = root.approvals.filter(a => a.callId !== msg.callId).concat([msg]);
            break;
        case "done":
            if (!foreign) {
                root.result = msg;
                root.busy = false;
                root.progress = null;
                root.listening = false;
                root.approvals = [];
                root.suggestions = Array.isArray(msg.suggestions) ? msg.suggestions : [];
                if (root.daemonState !== "speaking")
                    root.daemonState = "idle";
                ShellState.recordTurn(msg.costEur, msg.leftMachine === true);
                root.happyUntil = Date.now() + 1600;
                root.turnFinished(msg);
            }
            break;
        case "error":
            if (!foreign) {
                root.error = { message: msg.message || "", retryable: msg.retryable === true, code: msg.code || "" };
                root.busy = false;
                root.progress = null;
                root.listening = false;
                root.daemonState = "idle";
            }
            break;
        default:
            break;
        }
    }

    // ---- connection ----------------------------------------------------------------------
    property var link: null
    property int attempt: 0

    function linkUp(sock) {
        root.link = sock;
        root.connected = true;
        root.attempt = 0;
        root.send({ type: "hello", client: "sos-shell", version: root.clientVersion, lang: Strings.lang });
        root.requestStatus();
    }

    function linkDown() {
        const wasBusy = root.busy;
        root.link = null;
        root.connected = false;
        root.welcomed = false;
        root.busy = false;
        root.listening = false;
        root.daemonState = "idle";
        if (wasBusy)
            root.error = { message: Strings.jacksonOfflineBody, retryable: true };
        Qt.callLater(root.dropSocket);
        root.scheduleReconnect();
    }

    function dropSocket() {
        if (!root.connected)
            loader.active = false;
    }

    function scheduleReconnect() {
        if (!root.enabled)
            return;
        const delay = Math.min(30000, 500 * Math.pow(2, Math.min(root.attempt, 6)));
        root.attempt += 1;
        retryTimer.interval = delay;
        retryTimer.restart();
    }

    function tryConnect() {
        if (!root.enabled || root.connected)
            return;
        Sys.run(["test", "-S", root.socketPath], function (code) {
            if (code === 0 && root.enabled && !root.connected) {
                loader.active = false;
                loader.active = true;
            } else {
                root.scheduleReconnect();
            }
        });
    }

    onEnabledChanged: {
        if (root.enabled) {
            root.attempt = 0;
            root.tryConnect();
        } else {
            retryTimer.stop();
            root.link = null;
            root.connected = false;
            loader.active = false;
        }
    }

    Component.onCompleted: startTimer.start()

    // Give Status one poll first so a disabled AI never gets dialed.
    Timer {
        id: startTimer

        interval: 600
        onTriggered: root.tryConnect()
    }

    Timer {
        id: retryTimer

        onTriggered: root.tryConnect()
    }

    Loader {
        id: loader

        active: false
        // Dial only after the object exists: a unix connect can complete
        // synchronously and the handlers below reference the socket directly.
        onLoaded: loader.item.connected = true

        sourceComponent: Socket {
            id: sock

            path: root.socketPath
            parser: SplitParser {
                onRead: data => root.handleLine(data)
            }
            onConnectedChanged: {
                if (sock.connected)
                    root.linkUp(sock);
                else if (root.link === sock)
                    root.linkDown();
            }
            // A failed dial only emits error(), never a state change.
            onError: function (err) {
                if (!sock.connected) {
                    Qt.callLater(root.dropSocket);
                    root.scheduleReconnect();
                }
            }
        }
    }
}
