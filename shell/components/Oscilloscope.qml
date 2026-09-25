import QtQuick
import qs.core

// Jackson's oscilloscope trace (DESIGN.md §4).
//
//   idle      flat line breathing (opacity 0.35 <-> 0.6 at 0.2 Hz)
//   listening live mic level (`level`, 0..1)
//   thinking  slow travelling sine
//   working   Lissajous-like figure
//   speaking  the waveform follows the TTS envelope (`level`, synthesized if 0)
//   error     collapses to a dot
//
// CRT warm-up (warmUp()): a centered dot stretches to a line (160 ms), then the
// waveform fades in (100 ms). Frames are only requested while something moves:
// no animation runs when idle and not breathing, or with reduce motion.
Canvas {
    id: root

    property string mode: "idle"
    property real level: 0
    property color color: Theme.accent
    property color errorColor: Theme.bad
    property bool glow: Theme.glow
    property bool breathe: true      // idle breathing (only while visible)
    property bool live: true         // false: draw a static frame only

    // waveform shape (mockup defaults for the 92x22 panel scope)
    property real amp: 9.5
    property real freq: 3.2
    property real seed: 0.7

    // animated internals
    property real phase: 0
    property real warm: 1            // 0 = dot, 1 = full width line
    property real waveAlpha: 1
    property real collapse: 0        // error: 1 = collapsed to a dot
    property real breath: 0.5
    property real smoothLevel: 0

    readonly property bool moving: root.live && root.visible && !Theme.reduceMotion
                                   && (root.mode === "listening" || root.mode === "thinking"
                                       || root.mode === "working" || root.mode === "speaking")

    function warmUp() {
        if (Theme.reduceMotion) {
            root.warm = 1;
            root.waveAlpha = 1;
            root.requestPaint();
            return;
        }
        warmAnim.restart();
    }

    renderStrategy: Canvas.Cooperative
    antialiasing: true

    onModeChanged: {
        collapseAnim.stop();
        if (root.mode === "error" && !Theme.reduceMotion)
            collapseAnim.restart();
        else
            root.collapse = root.mode === "error" ? 1 : 0;
        root.requestPaint();
    }
    onColorChanged: root.requestPaint()
    onWidthChanged: root.requestPaint()
    onHeightChanged: root.requestPaint()
    onWarmChanged: root.requestPaint()
    onWaveAlphaChanged: root.requestPaint()
    onCollapseChanged: root.requestPaint()
    onBreathChanged: root.requestPaint()
    onVisibleChanged: root.requestPaint()

    // One frame per vsync only while the trace moves.
    FrameAnimation {
        running: root.moving
        onTriggered: {
            const speed = root.mode === "thinking" ? 1.1 : (root.mode === "working" ? 0.9 : 2.4);
            root.phase += frameTime * speed;
            const target = root.mode === "listening" || root.mode === "speaking" ? root.level : 0;
            root.smoothLevel += (target - root.smoothLevel) * Math.min(1, frameTime * 12);
            root.requestPaint();
        }
    }

    SequentialAnimation {
        id: warmAnim

        ScriptAction {
            script: {
                root.warm = 0;
                root.waveAlpha = 0;
            }
        }
        NumberAnimation {
            target: root
            property: "warm"
            from: 0
            to: 1
            duration: 160
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: root
            property: "waveAlpha"
            from: 0
            to: 1
            duration: 100
        }
    }

    NumberAnimation {
        id: collapseAnim

        target: root
        property: "collapse"
        from: 0
        to: 1
        duration: Theme.base
        easing.type: Easing.OutCubic
    }

    // 0.2 Hz breathing: 2.5 s each way. Runs only while idle and visible.
    SequentialAnimation {
        running: root.breathe && root.live && root.visible && root.mode === "idle" && !Theme.reduceMotion
        loops: Animation.Infinite

        NumberAnimation {
            target: root
            property: "breath"
            from: 0.35
            to: 0.6
            duration: 2500
            easing.type: Easing.InOutSine
        }
        NumberAnimation {
            target: root
            property: "breath"
            from: 0.6
            to: 0.35
            duration: 2500
            easing.type: Easing.InOutSine
        }
    }

    // The mockup's waveform: three sines under a sin(pi t)^1.6 envelope.
    function sample(t, seedShift, gain) {
        const env = Math.pow(Math.sin(Math.PI * t), 1.6);
        const s = root.seed + seedShift;
        const v = Math.sin(t * root.freq * 2 * Math.PI + s) * 0.62 + Math.sin(t * root.freq * 5.3 * Math.PI + s * 2) * 0.28 + Math.sin(t * root.freq * 11.7 * Math.PI) * 0.1;
        return v * env * gain;
    }

    onPaint: {
        const ctx = getContext("2d");
        const w = width, h = height, mid = h / 2;
        ctx.reset();
        if (w <= 0 || h <= 0)
            return;
        const isError = root.mode === "error";
        const c = isError ? root.errorColor : root.color;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";

        // CRT warm-up / error collapse: a centered dot that stretches to a line.
        const span = root.warm * (1 - root.collapse);
        if (span < 0.04) {
            ctx.fillStyle = c;
            ctx.beginPath();
            ctx.arc(w / 2, mid, 1.3, 0, Math.PI * 2);
            ctx.fill();
            return;
        }
        const x0 = w / 2 - span * w / 2, x1 = w / 2 + span * w / 2;

        // baseline (accent at 0.25)
        ctx.globalAlpha = 0.25;
        ctx.strokeStyle = c;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x0, mid);
        ctx.lineTo(x1, mid);
        ctx.stroke();

        if (root.glow) {
            ctx.shadowColor = Theme.alpha(c, 0.45);
            ctx.shadowBlur = 6;
        }
        ctx.strokeStyle = c;
        ctx.lineWidth = 1.5;
        ctx.beginPath();

        const m = root.mode;
        if (m === "idle" || isError || root.waveAlpha <= 0) {
            ctx.globalAlpha = isError ? 0.9 : (root.live && root.breathe ? root.breath : 0.6);
            ctx.moveTo(x0, mid);
            ctx.lineTo(x1, mid);
        } else if (m === "working") {
            // Lissajous-like figure (3:2) slowly rotating its phase
            ctx.globalAlpha = root.waveAlpha;
            const ax = (x1 - x0) / 2 - 2, ay = mid - 2, cx = w / 2;
            const steps = 90;
            for (let i = 0; i <= steps; i++) {
                const t = i / steps * Math.PI * 2;
                const x = cx + ax * Math.sin(3 * t + root.phase);
                const y = mid + ay * Math.sin(2 * t);
                if (i === 0)
                    ctx.moveTo(x, y);
                else
                    ctx.lineTo(x, y);
            }
        } else {
            ctx.globalAlpha = root.waveAlpha;
            let gain = root.amp;
            let shift = 0;
            if (m === "thinking") {
                gain = root.amp * 0.55;
            } else if (m === "listening") {
                gain = root.amp * Math.min(1, 0.12 + root.smoothLevel * 1.6);
                shift = root.phase;
            } else if (m === "speaking") {
                const env = root.smoothLevel > 0.01 ? root.smoothLevel : 0.55 + 0.45 * Math.sin(root.phase * 1.7) * Math.sin(root.phase * 0.63);
                gain = root.amp * Math.min(1, env);
                shift = root.phase;
            }
            const steps = Math.max(24, Math.round(x1 - x0));
            for (let i = 0; i <= steps; i++) {
                const t = i / steps;
                const x = x0 + t * (x1 - x0);
                let v;
                if (m === "thinking") {
                    // slow travelling sine under the same envelope
                    const env = Math.pow(Math.sin(Math.PI * t), 1.6);
                    v = Math.sin(t * 2 * Math.PI * 1.5 - root.phase * 2) * env * gain;
                } else {
                    v = root.sample(t, shift, gain);
                }
                if (i === 0)
                    ctx.moveTo(x, mid - v);
                else
                    ctx.lineTo(x, mid - v);
            }
        }
        ctx.stroke();
    }
}
