pragma Singleton

// Default audio sink/source through Quickshell.Services.Pipewire. Any volume or
// mute change (keys, apps, wpctl) raises the OSD unless the control center,
// which already shows the slider, is open.

import QtQuick
import Quickshell
import Quickshell.Services.Pipewire

Singleton {
    id: root

    readonly property var sink: Pipewire.defaultAudioSink
    readonly property var source: Pipewire.defaultAudioSource
    readonly property bool ready: !!(root.sink && root.sink.audio)
    readonly property real volume: root.ready ? root.sink.audio.volume : 0
    readonly property bool muted: root.ready ? root.sink.audio.muted : false
    readonly property string icon: root.muted || root.volume <= 0.001 ? "svoya-volume-mute" : (root.volume < 0.4 ? "svoya-volume-low" : "svoya-volume")

    // Volume/mute only become valid once the nodes are bound.
    PwObjectTracker {
        objects: [root.sink, root.source]
    }

    function setVolume(v) {
        if (!root.ready)
            return;
        root.sink.audio.muted = false;
        root.sink.audio.volume = Math.max(0, Math.min(1, v));
    }

    function toggleMute() {
        if (root.ready)
            root.sink.audio.muted = !root.sink.audio.muted;
    }

    // Ignore the burst of initial values while Pipewire syncs.
    property bool settled: false

    Timer {
        interval: 2500
        running: true
        onTriggered: root.settled = true
    }

    onVolumeChanged: root.announce()
    onMutedChanged: root.announce()

    function announce() {
        if (root.settled && Ui.modal !== "cc")
            Ui.showOsd("volume", root.volume, root.muted);
    }
}
