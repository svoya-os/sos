import QtQuick
import Quickshell
import Quickshell.Io
import qs.core

// Lock screen face (DESIGN §12, design/mockups/greeter.html — the same «Линия» as the greeter):
// the boot line through the middle, your name and «Заблокировано» on the left, the password typed
// onto the line, Jackson (your own look) standing on it, the time and the burst on the right.
// While a job runs, Jackson says how far it got. Bottom left: accessibility.
// After Settings.lockSaverSeconds without input the screensaver takes over (SOS ASCII, every theme):
// the face fades, Jackson turns into his eye, the eye looks around and follows the pointer, and
// every few minutes it looks closer (the short film). A key, a click or a decisive move of the mouse
// (half the screen within about a second) brings the face back; a slow one only gets looked at.
Item {
    id: root

    property string userName: Sys.user
    property string displayName: root.userName
    property string avatar: ""            // kept for the Lock API (the line shows Jackson instead)
    property bool busy: false
    property string message: ""           // PAM prompt, info or error
    property bool error: false
    property bool inputEnabled: true
    // which of Jackson's lock lines this time (Strings.jLocked): drawn once per lock, not per minute
    readonly property int pick: Math.floor(Math.random() * 1000)

    signal submit(string password)

    readonly property real s: Math.max(0.75, Math.min(1.8, Math.min(width / 1440, height / 900)))
    readonly property real lineY: Math.round(height / 2) + 0.5
    readonly property real leftX: Math.round(width * 200 / 1440)
    readonly property real rightX: Math.round(width * 1000 / 1440)

    function focusField() {
        line.focusField();
    }

    function clear() {
        line.clear();
    }

    SystemClock {
        id: clock

        precision: SystemClock.Minutes
    }

    FileView {
        id: hostnameFile

        path: "/etc/hostname"
        printErrors: false
    }
    readonly property string host: hostnameFile.text().trim()

    readonly property var job: Status.job

    // ---- the screensaver -----------------------------------------------------------------------------------------
    property bool saving: false
    property bool night: false

    onSavingChanged: {
        wakeMove.travel = 0;
        wakeMove.last = Qt.point(-1, -1);
    }
    readonly property bool saverOn: Settings.lockSaverSeconds > 0

    function poke() {
        root.saving = false;
        if (root.saverOn)
            idle.restart();
    }

    Timer {
        id: idle

        interval: Math.max(5, Settings.lockSaverSeconds) * 1000
        running: root.saverOn && root.visible
        onTriggered: {
            if (root.busy || line.length > 0)
                return;
            const h = new Date().getHours();
            root.night = h >= 22 || h < 6;     // once per screensaver: a change would replay the morph
            root.saving = true;
        }
    }
    // the film loops for ten minutes at most; then one still frame (the screen goes dark soon anyway)
    Timer {
        id: saverLimit

        interval: 10 * 60 * 1000
        running: root.saving
    }
    onBusyChanged: root.poke()
    onErrorChanged: root.poke()
    onMessageChanged: root.poke()
    Connections {
        target: line
        function onLengthChanged() {
            root.poke();
        }
    }
    Keys.onPressed: event => {
        root.poke();
        event.accepted = false;
    }

    Wallpaper {
        anchors.fill: parent
        colophon: false
        showSignal: false
    }

    MouseArea {
        anchors.fill: parent
        onClicked: {
            root.poke();
            line.focusField();
        }
    }

    // ---- the face: everything that fades out for the screensaver ----------------------------------------------------------
    Item {
        id: face

        anchors.fill: parent
        opacity: root.saving ? 0 : 1
        Behavior on opacity {
            NumberAnimation {
                duration: root.saving ? 700 : 160
                easing.type: Easing.OutCubic
            }
        }

        MText {
            x: root.leftX
            y: 30 * root.s
            text: Strings.morse + "   " + Strings.osName + " " + Sys.osVersion
            size: 11 * root.s
            color: Theme.textFaint
        }

        CornerStatus {
            anchors.top: parent.top
            anchors.topMargin: 28 * root.s
            anchors.right: parent.right
            anchors.rightMargin: root.leftX
            showLayout: true
        }

        // ---- who ----------------------------------------------------------------------------------------------
        MText {
            x: root.leftX
            y: root.lineY - 116 * root.s
            text: Strings.lockedEyebrow + (root.host.length > 0 ? "  ·  " + root.host : "")
            size: 10.5 * root.s
            caps: true
            tracking: 0.26
            color: Theme.textFaint
        }

        SText {
            x: root.leftX
            y: root.lineY - 96 * root.s
            height: 52 * root.s
            verticalAlignment: Text.AlignBottom
            text: root.displayName
            size: 46 * root.s
            font.weight: Font.Light
        }

        // ---- the line -----------------------------------------------------------------------------------------------
        LoginLine {
            id: line

            anchors.fill: parent
            s: root.s
            lineY: root.lineY
            inputX: root.leftX
            burstX: root.rightX
            jacksonX: Math.round(root.width * 632 / 1440)
            // under the screensaver nothing on the face moves: a blinking caret alone would make the
            // whole screen draw at the display's rate, saver included
            paused: root.saving
            busy: root.busy
            error: root.error
            inputEnabled: root.inputEnabled
            say: {
                if (root.busy)
                    return Strings.jChecking;
                if (root.error && (line.ghost > 0 || line.length === 0))
                    return Strings.jWrong(line.capsOn, Hypr.layoutCount > 1 ? Hypr.layoutCode : "");
                if (root.job !== null && line.length === 0)
                    return Strings.whileAway + " " + (root.job.label || "") + (root.job.progress !== undefined ? " " + Math.round(root.job.progress * 100) + "%" : "");
                return Strings.jLocked(root.pick);
            }
            sayMeta: {
                if (root.busy)
                    return Strings.jSecond;
                if (root.error && (line.ghost > 0 || line.length === 0))
                    return Strings.jAgain;
                if (root.job !== null && line.length === 0)
                    return root.job.etaSec ? Strings.left(root.job.etaSec) : Strings.jWorking;
                return line.length > 0 ? Strings.jListening : Strings.jLockedMeta;
            }
            onSubmit: text => root.submit(text)
        }

        Column {
            x: root.leftX
            y: root.lineY + 22 * root.s
            spacing: 12 * root.s

            MText {
                textFormat: Text.StyledText
                text: (line.length > 0 ? Strings.passwordWord : Strings.typePassword) + "  ·  <font color=\"" + Theme.textDim + "\">Enter</font> — " + Strings.toUnlock
                size: 11 * root.s
                color: Theme.textFaint
            }

            MText {
                textFormat: Text.StyledText
                text: {
                    if (root.message.length > 0)
                        return "<font color=\"" + (root.error ? Theme.bad : Theme.textDim) + "\">" + Fmt.escapeHtml(root.message) + "</font>";
                    const parts = [];
                    if (Hypr.layoutCode.length > 0)
                        parts.push(Strings.layoutWord + " " + Hypr.layoutCode);
                    if (line.capsOn)
                        parts.push("<font color=\"" + Theme.warn + "\">" + Strings.capsLockOn + "</font>");
                    return parts.join("  ·  ");
                }
                size: 11 * root.s
                color: Theme.textFaint
            }
        }

        // ---- when ---------------------------------------------------------------------------------------------------------
        MText {
            x: root.rightX
            y: root.lineY - 116 * root.s
            text: Strings.nowEyebrow
            size: 10.5 * root.s
            caps: true
            tracking: 0.26
            color: Theme.textFaint
        }

        SText {
            x: root.rightX
            y: root.lineY - 96 * root.s
            height: 52 * root.s
            verticalAlignment: Text.AlignBottom
            text: Fmt.clock(clock.date)
            size: 46 * root.s
            font.weight: Font.Light
            font.features: ({ "tnum": 1 })
        }

        Column {
            x: root.rightX
            y: root.lineY + 22 * root.s
            spacing: 12 * root.s

            MText {
                text: Strings.lockDate(clock.date)
                size: 11.5 * root.s
                color: Theme.textDim
            }
            MText {
                text: Strings.osName + " " + Sys.osVersion + " · " + Strings.codename
                size: 11 * root.s
                color: Theme.textFaint
            }
        }

        // ---- accessibility: a small popover with the three switches that matter here -------------------------------------
        TextButton {
            id: a11y

            x: root.leftX - 10
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 28 * root.s
            glyph: "svoya-accessibility"
            text: Strings.a11yShort
            selected: a11yPop.visible
            onClicked: a11yPop.visible = !a11yPop.visible
        }

        Rectangle {
            id: a11yPop

            visible: false
            anchors.left: a11y.left
            anchors.bottom: a11y.top
            anchors.bottomMargin: 12
            width: 272
            height: a11yCol.implicitHeight + 24
            radius: Theme.r(12)
            color: Theme.surface2
            border.width: 1
            border.color: Theme.lineStrong

            Column {
                id: a11yCol

                x: 14
                y: 12
                width: parent.width - 28
                spacing: 10

                Repeater {
                    model: [
                        { label: Strings.wizLargeText, key: "largeText" },
                        { label: Strings.wizHighContrast, key: "highContrast" },
                        { label: Strings.wizReduceMotion, key: "reduceMotion" }
                    ]

                    Item {
                        required property var modelData

                        width: a11yCol.width
                        height: 22

                        SText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.label
                            size: 13
                        }

                        Toggle {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            checked: Settings[modelData.key]
                            onToggled: value => Settings[modelData.key] = value
                        }
                    }
                }
            }
        }

    }

    // the screensaver: a dark room in every theme, the phosphor color of a dark theme (Paper's ink
    // would vanish on black), the alive pink and grey noise
    Rectangle {
        anchors.fill: parent
        color: "#0a0a0a"
        visible: opacity > 0
        opacity: root.saving ? 1 : 0
        Behavior on opacity {
            NumberAnimation {
                duration: root.saving ? 900 : 160
            }
        }

        Loader {
            anchors.fill: parent
            active: root.saving
            sourceComponent: AsciiView {
                scene: Theme.reduceMotion ? "eye" : "saver"
                running: !Theme.reduceMotion && saverLimit.running
                from: Qt.rect(line.jacksonX, root.lineY - line.jSize, line.jSize, line.jSize)
                night: root.night
                fg: Theme.isDark ? Theme.accent : "#3cffd0"
                noise: "#5a5a5a"
                alive: "#ff2e88"
            }
        }

        // a slow move is looked at; a decisive one wakes the face, as a key does
        HoverHandler {
            id: wakeMove

            property point last: Qt.point(-1, -1)
            property real travel: 0

            enabled: root.saving
            onPointChanged: {
                const p = point.position;
                if (wakeMove.last.x >= 0)
                    wakeMove.travel += Math.hypot(p.x - wakeMove.last.x, p.y - wakeMove.last.y);
                wakeMove.last = p;
                if (wakeMove.travel > root.width * 0.5)
                    root.poke();
            }
        }
        Timer {
            // the travel fades: only movement within about a second adds up
            running: root.saving
            interval: 200
            repeat: true
            onTriggered: wakeMove.travel *= 0.75
        }

        // a click wakes the face; it never reaches the faded buttons underneath
        MouseArea {
            anchors.fill: parent
            enabled: root.saving
            onClicked: {
                root.poke();
                line.focusField();
            }
        }

        MText {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 26 * root.s
            text: Fmt.clock(clock.date) + "  ·  " + Strings.lockDate(clock.date)
            size: 11 * root.s
            color: "#5a5a5a"
        }
    }
}
