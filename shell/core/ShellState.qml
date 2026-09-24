pragma Singleton

// Volatile shell state: ~/.local/state/svoya/shell.json.
// Holds today's AI counters accumulated from Jackson `done` events. They are a
// fallback: when `svoya status --json` reports daily totals (ai.todayCostEur,
// ai.todayCloudRequests), those win because they also count turns started from
// the terminal (`jackson ...`).

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    readonly property string path: {
        const state = Quickshell.env("XDG_STATE_HOME");
        return (state && state.length > 0 ? state : Quickshell.env("HOME") + "/.local/state") + "/svoya/shell.json";
    }

    readonly property string today: Qt.formatDate(clock.date, "yyyy-MM-dd")
    readonly property real costToday: adapter.aiDate === root.today ? adapter.aiCostEur : 0
    readonly property int cloudRequestsToday: adapter.aiDate === root.today ? adapter.aiCloudRequests : 0
    readonly property int turnsToday: adapter.aiDate === root.today ? adapter.aiTurns : 0

    // Record one finished Jackson turn.
    function recordTurn(costEur, leftMachine) {
        if (adapter.aiDate !== root.today) {
            adapter.aiDate = root.today;
            adapter.aiCostEur = 0;
            adapter.aiCloudRequests = 0;
            adapter.aiTurns = 0;
        }
        adapter.aiTurns += 1;
        adapter.aiCostEur += Math.max(0, Number(costEur) || 0);
        if (leftMachine)
            adapter.aiCloudRequests += 1;
    }

    SystemClock {
        id: clock
        precision: SystemClock.Hours
    }

    FileView {
        id: file

        path: root.path
        printErrors: false
        onAdapterUpdated: writeAdapter()

        JsonAdapter {
            id: adapter

            property string aiDate: ""
            property real aiCostEur: 0
            property int aiCloudRequests: 0
            property int aiTurns: 0
        }
    }
}
