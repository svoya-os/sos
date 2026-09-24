pragma Singleton

// System status from `svoya status --json` (docs/ARCHITECTURE.md §4.2), polled
// every 2 s. Every field is optional; consumers get null/empty values and hide
// their segment. If the `svoya` command is missing the poll backs off to 30 s
// (the CLI may be installed later) and never spams the log.

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    property bool available: false      // the command exists and returned JSON
    property var raw: ({})

    readonly property var gpus: Array.isArray(root.raw.gpu) ? root.raw.gpu : []
    readonly property var gpu: root.gpus.length > 0 ? root.gpus[0] : null
    readonly property var jobs: Array.isArray(root.raw.jobs) ? root.raw.jobs : []
    readonly property var job: root.jobs.length > 0 ? root.jobs[0] : null
    readonly property var ai: root.raw.ai && typeof root.raw.ai === "object" ? root.raw.ai : null
    readonly property var updates: root.raw.updates && typeof root.raw.updates === "object" ? root.raw.updates : null
    readonly property var snapshots: root.raw.snapshots && typeof root.raw.snapshots === "object" ? root.raw.snapshots : null

    // AI switch. Missing field = enabled (contract gap: ai.enabled is proposed).
    readonly property bool aiEnabled: !(root.ai && root.ai.enabled === false)
    readonly property bool aiLocal: !(root.ai && root.ai.local === false)
    readonly property bool cloudActive: !!(root.ai && root.ai.cloudActiveSince)
    // Daily totals if the CLI reports them (proposed keys), else the shell's own counters.
    readonly property real costToday: root.ai && root.ai.todayCostEur !== undefined ? Number(root.ai.todayCostEur) : ShellState.costToday
    readonly property int cloudRequestsToday: root.ai && root.ai.todayCloudRequests !== undefined ? Number(root.ai.todayCloudRequests) : ShellState.cloudRequestsToday

    // Polling can be paused (e.g. while the session is locked).
    property bool paused: false
    property int missingInterval: 30000

    function refresh() {
        if (!proc.running)
            proc.running = true;
    }

    Process {
        id: proc

        // `exit 127` when the CLI is absent: no "failed to start" warnings.
        command: ["sh", "-c", "command -v svoya >/dev/null 2>&1 || exit 127; exec svoya status --json"]
        stdout: StdioCollector {
            id: out
        }
        onExited: function (exitCode, exitStatus) {
            if (exitCode === 127) {
                root.available = false;
                timer.interval = root.missingInterval;
                return;
            }
            timer.interval = 2000;
            if (exitCode !== 0)
                return; // keep the last good snapshot
            try {
                const parsed = JSON.parse(out.text);
                if (parsed && typeof parsed === "object") {
                    root.raw = parsed;
                    root.available = true;
                }
            } catch (e) {
                // partial or non-JSON output: ignore this tick
            }
        }
    }

    Timer {
        id: timer

        interval: 2000
        repeat: true
        running: !root.paused
        triggeredOnStart: true
        onTriggered: root.refresh()
    }
}
