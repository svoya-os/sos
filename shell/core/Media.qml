pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Services.Mpris

// What is playing (MPRIS: a browser tab, Spotify, a player): the player the control center shows,
// and quiet while you talk to Jackson. Players that play pause when the microphone opens and go on
// a moment after the conversation is over (shell.json "voicePausesMedia": false turns that off),
// so music neither drowns out what you say nor talks over his answer.
Singleton {
    id: root

    readonly property var players: Mpris.players.values.filter(p => p && p.canControl)
    // the one playing, else the last one with a track
    readonly property var player: root.players.find(p => p.isPlaying) || root.players.find(p => (p.trackTitle || "").length > 0) || null

    readonly property bool talking: Jackson.mode === "listening" || Jackson.mode === "speaking"
    property var paused: []             // the players this paused, to go on with

    onTalkingChanged: {
        if (root.talking) {
            resume.stop();
            if (!Settings.voicePausesMedia)
                return;
            const now = root.players.filter(p => p.isPlaying && p.canPause && root.paused.indexOf(p) < 0);
            now.forEach(p => p.pause());
            root.paused = root.paused.concat(now);
        } else if (root.paused.length > 0) {
            resume.restart();           // after the answer he may listen again: wait for that
        }
    }

    Timer {
        id: resume

        interval: 1800
        onTriggered: {
            if (root.talking)
                return;
            const alive = Mpris.players.values;
            root.paused.filter(p => alive.indexOf(p) >= 0 && !p.isPlaying && p.canPlay).forEach(p => p.play());
            root.paused = [];
        }
    }
}
