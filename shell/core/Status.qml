pragma Singleton

// System status from `sos status --json` (docs/ARCHITECTURE.md §4.2).
//
// The CLI can stream: `sos status --json --watch 2` prints one JSON object per
// line every 2 s, so a single long-lived process replaces a fork every 2 s.
// If streaming is unavailable (the stream exits right away) we fall back to
// polling `sos status --json`. Without the CLI we retry every 30 s silently.
// Every field is optional; consumers get null/empty values and hide segments.

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    property bool available: false      // the CLI answered with JSON at least once
    property var raw: ({})

    readonly property var gpus: Array.isArray(root.raw.gpu) ? root.raw.gpu : []
    // The bar shows the discrete GPU when there is one, else the first.
    readonly property var gpu: {
        const list = root.gpus;
        for (let i = 0; i < list.length; i++) {
            if (!list[i].integrated)
                return list[i];
        }
        return list.length > 0 ? list[0] : null;
    }
    readonly property var jobs: Array.isArray(root.raw.jobs) ? root.raw.jobs : []
    readonly property var job: root.jobs.length > 0 ? root.jobs[0] : null
    readonly property var ai: root.raw.ai && typeof root.raw.ai === "object" ? root.raw.ai : null
    readonly property var updates: root.raw.updates && typeof root.raw.updates === "object" ? root.raw.updates : null
    readonly property var snapshots: root.raw.snapshots && typeof root.raw.snapshots === "object" ? root.raw.snapshots : null

    // The one AI switch ([ai] enabled in svoya.toml). Missing = enabled.
    readonly property bool aiEnabled: !(root.ai && root.ai.enabled === false)
    readonly property bool aiLocal: !(root.ai && root.ai.local === false)
    readonly property bool cloudActive: !!(root.ai && root.ai.cloudActiveSince)
    // Today's totals from Jackson's spend ledger; the shell's own counters otherwise.
    readonly property real costToday: root.ai && root.ai.todayCostEur !== undefined ? Number(root.ai.todayCostEur) : ShellState.costToday
    readonly property int cloudRequestsToday: root.ai && root.ai.todayCloudRequests !== undefined ? Number(root.ai.todayCloudRequests) : ShellState.cloudRequestsToday

    // `sos` is the command; `svoya` is its alias on older images.
    readonly property string resolveCli: 'c=$(command -v sos || command -v svoya) || exit 127; '

    // Paused while the session is locked: nothing to show, no work to do.
    property bool paused: false
    onPausedChanged: {
        if (root.paused) {
            retry.stop();
            stream.running = false;
            poll.running = false;
        } else {
            root.refresh();
        }
    }

    property bool streaming: true       // false after the stream failed fast
    property real streamStarted: 0

    function accept(text) {
        try {
            const parsed = JSON.parse(text);
            if (parsed && typeof parsed === "object") {
                root.raw = parsed;
                root.available = true;
            }
        } catch (e) {
            // partial or non-JSON line: ignore
        }
    }

    function refresh() {
        if (root.paused)
            return;
        if (root.streaming) {
            if (!stream.running)
                root.startStream();
        } else if (!poll.running) {
            poll.running = true;
        }
    }

    function startStream() {
        root.streamStarted = Date.now();
        stream.running = true;
    }

    Process {
        id: stream

        command: ["sh", "-c", root.resolveCli + 'exec "$c" status --json --watch 2']
        stdout: SplitParser {
            onRead: data => root.accept(data)
        }
        onExited: function (exitCode, exitStatus) {
            if (exitCode === 127) {
                root.available = false;
                retry.interval = 30000;
            } else if (Date.now() - root.streamStarted < 3000) {
                // no --watch support: poll instead
                root.streaming = false;
                retry.interval = 2000;
            } else {
                retry.interval = 2000; // stream died: restart it
            }
            retry.restart();
        }
    }

    Process {
        id: poll

        command: ["sh", "-c", root.resolveCli + 'exec "$c" status --json']
        stdout: StdioCollector {
            id: pollOut
        }
        onExited: function (exitCode, exitStatus) {
            if (exitCode === 127) {
                root.available = false;
                retry.interval = 30000;
            } else {
                if (exitCode === 0)
                    root.accept(pollOut.text);
                retry.interval = 2000;
            }
            retry.restart();
        }
    }

    Timer {
        id: retry

        interval: 2000
        onTriggered: root.refresh()
    }

    Component.onCompleted: root.refresh()
}
