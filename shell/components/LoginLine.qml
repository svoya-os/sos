import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import qs.core

// The login line (DESIGN §12, design/mockups/greeter.html; chosen 25.09): the boot scope never
// switches off. Plymouth ends on a lit line across the middle of the screen; the greeter and the
// lock screen draw the same line and type the password onto it:
//
//   ─────── ● ● ● ● ● ● ● ●|  ·········  [Jackson]  ·········  ⌐¬⌐¬⌐ ⌐¬⌐¬⌐ ⌐¬⌐¬⌐ ───────
//           inputX (one dot per character, the accent caret)   burstX (··· ——— ··· in `text`)
//
// Jackson stands on the line (his own look, or the system one on the greeter) and reacts:
// idle → listening while typing → thinking while PAM checks (the dots run into him) → error
// (the dots jitter red and fall off) → happy on success (the trace sweeps to the burst).
// The accent is only the caret. Reduce motion: no sweeps, no jitter, no bubble slide.
//
// The TextInput is invisible and only holds the text and the focus; it covers the input part of
// the line so a click there focuses it. `masked: false` shows the text itself (user-name prompt).
Item {
    id: root

    // ---- geometry (px; the owner scales them) ------------------------------------------------------
    property real s: 1
    property real lineY: Math.round(root.height / 2) + 0.5
    property real inputX: Math.round(root.width * 200 / 1440)
    property real burstX: Math.round(root.width * 1000 / 1440)
    property real jacksonX: Math.round(root.width * 632 / 1440)

    // ---- input ---------------------------------------------------------------------------------------
    property alias text: input.text
    property bool masked: true
    property bool busy: false            // PAM is checking
    property bool error: false           // the last attempt failed (shake, then the dots fall off)
    property bool welcome: false         // success: sweep to the burst, Jackson grins
    property bool inputEnabled: true
    property bool capsOn: false          // guessed from the typed letters (Wayland has no query)
    readonly property bool focused: input.activeFocus
    readonly property int length: input.length

    // ---- Jackson -------------------------------------------------------------------------------------
    property bool showJackson: true
    property var look: Avatar.look
    property string say: ""
    property string sayMeta: ""

    signal submit(string text)

    function focusField() {
        input.forceActiveFocus();
    }

    function clear() {
        input.text = "";
    }

    function send() {
        if (input.text.length > 0 && !root.busy && !root.welcome)
            root.submit(input.text);
    }

    readonly property string phase: root.welcome ? "welcome" : root.busy ? "checking" : root.error && root.ghost > 0 ? "error" : input.length > 0 ? "typing" : "idle"
    readonly property bool motion: !Theme.reduceMotion

    // ---- geometry of the parts --------------------------------------------------------------------------
    readonly property real u: 7 * root.s              // Morse unit (the burst)
    readonly property real ph: 12 * root.s            // pulse height
    readonly property real jSize: 32 * Math.max(2, Math.round(3 * root.s))   // integer sprite scale
    readonly property real room: root.jacksonX - 44 * root.s - root.inputX   // space for the dots
    readonly property int shownDots: Math.min(input.length, 64)
    readonly property real step: Math.min(16 * root.s, root.shownDots > 1 ? root.room / root.shownDots : 16 * root.s)
    readonly property real dotR: 3.4 * root.s
    readonly property real caretX: root.masked ? root.inputX + (root.shownDots > 0 ? 6 * root.s + (root.shownDots - 1) * root.step + 14 * root.s : 0) : root.inputX + plain.implicitWidth + (plain.text.length > 0 ? 6 * root.s : 0)

    readonly property var burst: {
        const letters = ["...", "---", "..."];
        const u = root.u, h = root.ph;
        let x = 0;
        let d = "M 0 " + h;
        for (let li = 0; li < letters.length; li++) {
            for (let si = 0; si < letters[li].length; si++) {
                const w = (letters[li][si] === "." ? 1 : 3) * u;
                d += " L " + x + " 0 L " + (x + w) + " 0 L " + (x + w) + " " + h;
                x += w;
                if (si < letters[li].length - 1) {
                    d += " L " + (x + u) + " " + h;
                    x += u;
                }
            }
            if (li < letters.length - 1) {
                d += " L " + (x + 3 * u) + " " + h;
                x += 3 * u;
            }
        }
        return { path: d, width: x };
    }
    readonly property real burstEnd: root.burstX + root.burst.width

    // ---- animation state ----------------------------------------------------------------------------------
    property int lastLength: 0           // dots at the moment of the failed attempt
    property int ghost: 0                // red dots still falling off after an error
    property real flow: 0                // 0 → 1: the dots run into Jackson (checking)
    property real sweep: 0               // 0 → 1: the trace lights up to the burst (welcome)
    property real ghostFade: 1

    onLengthChanged: {
        if (input.length > 0)
            root.lastLength = input.length;
    }
    onErrorChanged: {
        if (root.error) {
            root.ghost = Math.max(1, Math.min(root.lastLength, 64));
            root.ghostFade = 1;
            ghostAnim.restart();
        }
    }
    onBusyChanged: {
        flowAnim.stop();
        if (root.busy && root.motion) {
            root.flow = 0;
            flowAnim.start();
        } else {
            root.flow = root.busy ? 1 : 0;
        }
    }
    onWelcomeChanged: {
        sweepAnim.stop();
        if (root.welcome && root.motion) {
            root.sweep = 0;
            sweepAnim.start();
        } else {
            root.sweep = root.welcome ? 1 : 0;
        }
    }

    NumberAnimation {
        id: flowAnim

        target: root
        property: "flow"
        from: 0
        to: 1
        duration: 520
        easing.type: Easing.InOutCubic
    }
    NumberAnimation {
        id: sweepAnim

        target: root
        property: "sweep"
        from: 0
        to: 1
        duration: 420
        easing.type: Easing.OutCubic
    }
    SequentialAnimation {
        id: ghostAnim

        PauseAnimation {
            duration: root.motion ? 900 : 1600
        }
        NumberAnimation {
            target: root
            property: "ghostFade"
            to: 0
            duration: root.motion ? 380 : 0
        }
        ScriptAction {
            script: root.ghost = 0
        }
    }

    // ---- the line ----------------------------------------------------------------------------------------------
    // base: the whole width, faint (text .14, fading at both ends)
    Rectangle {
        x: 0
        y: root.lineY - 0.5
        width: root.width
        height: 1
        gradient: Gradient {
            orientation: Gradient.Horizontal

            GradientStop {
                position: 0
                color: Theme.alpha(Theme.text, 0)
            }
            GradientStop {
                position: 0.08
                color: Theme.alpha(Theme.text, 0.14)
            }
            GradientStop {
                position: 0.92
                color: Theme.alpha(Theme.text, 0.14)
            }
            GradientStop {
                position: 1
                color: Theme.alpha(Theme.text, 0)
            }
        }
    }

    // the lit trace from the left up to the caret (typing), to Jackson (checking), to the burst (welcome)
    Rectangle {
        id: trail

        readonly property real from: root.inputX - 150 * root.s
        readonly property real to: {
            const typed = root.caretX;
            if (root.phase === "welcome")
                return typed + (root.burstEnd + 140 * root.s - typed) * root.sweep;
            if (root.phase === "checking")
                return typed + (root.jacksonX - typed) * root.flow;
            return typed;
        }
        readonly property color tint: root.phase === "error" ? Theme.bad : Theme.text

        visible: root.length > 0 || root.phase === "welcome" || root.phase === "error" || root.focused
        x: from
        y: root.lineY - 0.7 * root.s
        width: Math.max(0, to - from)
        height: 1.4 * root.s
        gradient: Gradient {
            orientation: Gradient.Horizontal

            GradientStop {
                position: 0
                color: Theme.alpha(trail.tint, 0)
            }
            GradientStop {
                position: 1
                color: Theme.alpha(trail.tint, root.phase === "welcome" ? 0.9 : root.length > 0 ? 0.75 : 0.35)
            }
        }
    }

    // burst lead-in/out: brighter around the ··· ——— ···
    Rectangle {
        x: root.burstX - 140 * root.s
        y: root.lineY - 0.6 * root.s
        width: root.burst.width + 280 * root.s
        height: 1.2 * root.s
        gradient: Gradient {
            orientation: Gradient.Horizontal

            GradientStop {
                position: 0
                color: Theme.alpha(Theme.text, 0)
            }
            GradientStop {
                position: 0.2
                color: Theme.alpha(Theme.text, 0.55)
            }
            GradientStop {
                position: 0.8
                color: Theme.alpha(Theme.text, 0.55)
            }
            GradientStop {
                position: 1
                color: Theme.alpha(Theme.text, 0)
            }
        }
    }

    // the burst: square-wave «СОС», the same geometry as Plymouth and the wallpaper
    Item {
        x: root.burstX
        y: root.lineY - root.ph
        width: root.burst.width
        height: root.ph + 1
        opacity: 0.92
        layer.enabled: Theme.glow
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: Theme.alpha(Theme.text, root.phase === "welcome" ? 0.7 : 0.35)
            shadowBlur: 0.3
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 0
        }

        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                strokeColor: Theme.text
                strokeWidth: 1.6 * root.s
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin

                PathSvg {
                    path: root.burst.path
                }
            }
        }
    }

    // ---- the password: one dot per character, threaded on the line ---------------------------------------------
    Item {
        id: beads

        anchors.fill: parent
        visible: root.masked
        layer.enabled: Theme.glow && root.shownDots + root.ghost > 0
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: Theme.alpha(root.phase === "error" ? Theme.bad : Theme.text, 0.5)
            shadowBlur: 0.35
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 0
        }

        // what is typed
        Repeater {
            model: root.phase === "error" || root.phase === "welcome" ? 0 : root.shownDots

            Rectangle {
                required property int index

                readonly property real rest: root.inputX + 6 * root.s + index * root.step
                readonly property real target: root.jacksonX - 40 * root.s - (root.shownDots - 1 - index) * 11 * root.s

                x: rest + (target - rest) * root.flow - root.dotR
                y: root.lineY - root.dotR
                width: 2 * root.dotR
                height: 2 * root.dotR
                radius: root.dotR
                color: Theme.text
                opacity: root.phase === "checking" ? 1 - root.flow * (0.65 - 0.5 * index / Math.max(1, root.shownDots)) : 1
                antialiasing: true
                scale: 1

                // a new dot rises from the line
                Component.onCompleted: {
                    if (root.motion && index === root.shownDots - 1)
                        riseAnim.start();
                }
                NumberAnimation on scale {
                    id: riseAnim

                    running: false
                    from: 0.2
                    to: 1
                    duration: 110
                    easing.type: Easing.OutBack
                }
            }
        }

        // after a failed attempt: the same number of dots, red, jittering, then falling off
        Repeater {
            model: root.ghost

            Rectangle {
                required property int index

                readonly property var jitter: [3, -2, 4, -3, 2, -4, 3, -1]

                x: root.inputX + 6 * root.s + index * Math.min(16 * root.s, root.room / Math.max(1, root.ghost)) - root.dotR
                y: root.lineY - root.dotR + (root.motion ? jitter[index % 8] * root.s : 0) + (1 - root.ghostFade) * 18 * root.s
                width: 2 * root.dotR
                height: 2 * root.dotR
                radius: root.dotR
                color: Theme.bad
                opacity: root.ghostFade
                antialiasing: true
            }
        }
    }

    // user-name prompt: the text itself sits on the line
    MText {
        id: plain

        visible: !root.masked
        x: root.inputX
        y: root.lineY - height - 5 * root.s
        text: input.text
        size: 20 * root.s
        color: Theme.text
    }

    // the caret: the only accent on the screen (§12)
    Rectangle {
        id: caret

        visible: root.focused && (root.phase === "idle" || root.phase === "typing")
        x: root.caretX
        y: root.lineY - 13 * root.s
        width: 2 * root.s
        height: 26 * root.s
        radius: 1
        color: Theme.accent
        layer.enabled: Theme.glow
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: Theme.alpha(Theme.accent, 0.7)
            shadowBlur: 0.5
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 0
        }

        SequentialAnimation on opacity {
            running: caret.visible && root.motion && root.length === 0
            loops: Animation.Infinite
            alwaysRunToEnd: true

            NumberAnimation {
                to: 0.15
                duration: 520
                easing.type: Easing.InOutSine
            }
            NumberAnimation {
                to: 1
                duration: 520
                easing.type: Easing.InOutSine
            }
        }
    }

    TextInput {
        id: input

        x: root.inputX - 20 * root.s
        y: root.lineY - 22 * root.s
        width: Math.max(80, root.jacksonX - root.inputX - 20 * root.s)
        height: 44 * root.s
        opacity: 0
        focus: true
        enabled: root.inputEnabled
        readOnly: root.busy || root.welcome
        echoMode: root.masked ? TextInput.Password : TextInput.Normal
        passwordMaskDelay: 0
        font.pixelSize: 14
        maximumLength: 256
        Keys.onReturnPressed: root.send()
        Keys.onEnterPressed: root.send()
        Keys.onPressed: event => {
            const t = event.text;
            if (t && t.length === 1 && t.toLowerCase() !== t.toUpperCase()) {
                const upper = t === t.toUpperCase();
                const shift = (event.modifiers & Qt.ShiftModifier) !== 0;
                root.capsOn = upper !== shift;
            } else if (event.key === Qt.Key_CapsLock) {
                root.capsOn = !root.capsOn;
            }
        }
    }

    // ---- Jackson on the line ----------------------------------------------------------------------------------
    Rectangle {
        // his shadow on the trace
        visible: root.showJackson && jackson.hasSprite
        x: root.jacksonX + root.jSize / 2 - 44 * root.s
        y: root.lineY - 3 * root.s
        width: 88 * root.s
        height: 7 * root.s
        radius: height / 2
        color: "#000000"
        opacity: Theme.isDark ? 0.5 : 0.18
        layer.enabled: true
        layer.effect: MultiEffect {
            blurEnabled: true
            blur: 0.6
            blurMax: 12
        }
    }

    JacksonAvatar {
        id: jackson

        visible: root.showJackson
        x: root.jacksonX
        y: root.lineY - root.jSize
        size: root.jSize
        backing: false
        menu: false
        look: root.look
        forceAnim: ({
                idle: root.focused ? "listening" : "idle",
                typing: "listening",
                checking: "thinking",
                error: "error",
                welcome: "happy"
            })[root.phase]
    }

    // what he says: one short line in a bubble above-right of him
    Rectangle {
        id: bubble

        readonly property string line: root.say

        visible: root.showJackson && root.say.length > 0
        x: root.jacksonX + root.jSize * 0.83
        y: root.lineY - root.jSize - height + 4 * root.s + bubbleShift
        width: bubbleRow.implicitWidth + 24 * root.s
        height: 32 * root.s
        color: Theme.surface2
        border.width: 1
        border.color: Theme.lineStrong
        radius: 12 * root.s
        bottomLeftRadius: 3 * root.s
        antialiasing: true

        property real bubbleShift: 0

        onLineChanged: {
            if (root.motion)
                bubbleIn.restart();
        }

        ParallelAnimation {
            id: bubbleIn

            NumberAnimation {
                target: bubble
                property: "bubbleShift"
                from: 6 * root.s
                to: 0
                duration: 180
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: bubble
                property: "opacity"
                from: 0
                to: 1
                duration: 180
            }
        }

        Row {
            id: bubbleRow

            x: 12 * root.s
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8 * root.s

            SText {
                anchors.verticalCenter: parent.verticalCenter
                text: root.say
                size: 13.5 * root.s
            }
            MText {
                anchors.verticalCenter: parent.verticalCenter
                visible: root.sayMeta.length > 0
                text: root.sayMeta
                size: 10.5 * root.s
                color: Theme.textFaint
            }
        }
    }
}
