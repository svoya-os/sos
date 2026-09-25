import QtQuick
import qs.core

// Jackson's face: a pixel-art mascot (ICQ/QIP/MSN-era avatar) when sprites are
// installed, otherwise the oscilloscope trace.
//
// Sprites: shell/assets/jackson/<avatar>/<state>.png, one horizontal strip per
// state with square frames (frame size = image height):
//   idle (blinks), listening, thinking, talking, happy, error
// <avatar> comes from the service (`avatar`: auto | imp | cat | none); "auto"
// uses the first set that exists (imp, then cat). Pixel art is scaled with
// nearest-neighbour filtering; `size` should be a multiple of the frame size.
Item {
    id: root

    property real size: 22                 // sprite box (square)
    property bool mini: false              // bar/toast size: mini scope fallback
    property string mode: Jackson.mode     // override for previews
    property bool live: true
    property real scopeWidth: root.mini ? 22 : 92
    property real scopeHeight: root.mini ? 10 : 22

    readonly property var candidates: {
        const a = Jackson.avatar;
        if (a === "none")
            return [];
        if (a === "auto" || a.length === 0)
            return ["imp", "cat"];
        return [a];
    }
    property int candidate: 0
    readonly property string avatarName: root.candidate < root.candidates.length ? root.candidates[root.candidate] : ""
    readonly property bool hasSprite: root.avatarName.length > 0 && probe.status === Image.Ready

    // mood -> sprite state
    property real now: Date.now()
    readonly property string spriteState: {
        const m = root.mode;
        const mood = Jackson.mood;
        if (Jackson.happyUntil > root.now)
            return "happy";
        if (m === "error" || mood === "sorry")
            return "error";
        if (m === "listening")
            return "listening";
        if (m === "speaking" || mood === "talking")
            return "talking";
        if (m === "thinking" || m === "working" || mood === "busy" || mood === "thinking" || mood === "asking")
            return "thinking";
        return "idle";
    }

    function spriteUrl(name, state) {
        return name.length > 0 ? Theme.asset("jackson/" + name + "/" + state + ".png") : "";
    }

    function warmUp() {
        if (scope.visible)
            scope.warmUp();
    }

    // Probe only once shown: every notification card carries a hidden avatar, and each
    // probe of a missing set logs "Cannot open …" (no sprites ship yet).
    property bool probed: false

    implicitWidth: root.hasSprite ? root.size : root.scopeWidth
    implicitHeight: root.hasSprite ? root.size : root.scopeHeight

    onCandidatesChanged: root.candidate = 0
    onVisibleChanged: if (visible) root.probed = true
    Component.onCompleted: if (visible) root.probed = true

    // Existence probe for the chosen set (idle.png must exist).
    Image {
        id: probe

        visible: false
        asynchronous: true
        source: root.probed ? root.spriteUrl(root.avatarName, "idle") : ""
        onStatusChanged: {
            if (status === Image.Error && root.candidate < root.candidates.length)
                root.candidate += 1;
        }
    }

    // The strip is shown through a square viewport; frames are offsets.
    Item {
        id: viewport

        property int frame: 0

        anchors.centerIn: parent
        width: root.size
        height: root.size
        clip: true
        visible: root.hasSprite

        Image {
            id: strip

            readonly property real frameSize: strip.sourceSize.height > 0 ? strip.sourceSize.height : 1
            readonly property int frames: Math.max(1, Math.round(strip.sourceSize.width / strip.frameSize))

            x: -viewport.frame * root.size
            width: root.size * strip.frames
            height: root.size
            source: root.hasSprite ? root.spriteUrl(root.avatarName, root.spriteState) : ""
            smooth: false
            mipmap: false
            onSourceChanged: viewport.frame = 0
        }
    }

    // Frame clock, 8 fps. Idle holds the open-eyes frame 2.5-5 s, then blinks.
    Timer {
        id: frameTimer

        running: root.hasSprite && root.visible && root.live && !Theme.reduceMotion && strip.frames > 1
        repeat: true
        interval: 125
        onTriggered: {
            root.now = Date.now();
            if (root.spriteState === "idle") {
                if (viewport.frame === 0 && frameTimer.interval > 125) {
                    frameTimer.interval = 125;
                    viewport.frame = 1;
                } else if (viewport.frame + 1 < strip.frames) {
                    viewport.frame += 1;
                } else {
                    viewport.frame = 0;
                    frameTimer.interval = 2500 + Math.floor(Math.random() * 2500);
                }
            } else {
                frameTimer.interval = 125;
                viewport.frame = (viewport.frame + 1) % strip.frames;
            }
        }
    }

    // Keeps `now` fresh for the happy beat even without sprite frames.
    Timer {
        running: Jackson.happyUntil > root.now
        interval: 200
        repeat: true
        onTriggered: root.now = Date.now()
    }

    Oscilloscope {
        id: scope

        anchors.centerIn: parent
        width: root.scopeWidth
        height: root.scopeHeight
        visible: !root.hasSprite
        mode: root.mode === "off" || root.mode === "offline" ? "idle" : root.mode
        level: Jackson.listening ? micLevel : 0
        live: root.live
        opacity: root.mode === "offline" || root.mode === "off" ? 0.5 : 1
        amp: root.mini ? 4 : 9.5
        freq: root.mini ? 1.6 : 3.2
        seed: root.mini ? 0.2 : 0.7
        breathe: !root.mini

        property real micLevel: 0
    }
}
