import QtQuick
import Quickshell
import Quickshell.Io
import qs.core

// Lock screen face (DESIGN §12, design/mockups/greeter.html — the same «Линия» as the greeter):
// the boot line through the middle, your name and «Заблокировано» on the left, the password typed
// onto the line, Jackson (your own look) standing on it, the time and the burst on the right.
// While a job runs, Jackson says how far it got. Bottom left: accessibility.
Item {
    id: root

    property string userName: Sys.user
    property string displayName: root.userName
    property string avatar: ""            // kept for the Lock API (the line shows Jackson instead)
    property bool busy: false
    property string message: ""           // PAM prompt, info or error
    property bool error: false
    property bool inputEnabled: true

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

    Wallpaper {
        anchors.fill: parent
        colophon: false
        showSignal: false
    }

    MouseArea {
        anchors.fill: parent
        onClicked: line.focusField()
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
    readonly property var job: Status.job

    LoginLine {
        id: line

        anchors.fill: parent
        s: root.s
        lineY: root.lineY
        inputX: root.leftX
        burstX: root.rightX
        jacksonX: Math.round(root.width * 632 / 1440)
        busy: root.busy
        error: root.error
        inputEnabled: root.inputEnabled
        say: {
            if (root.busy)
                return Strings.jChecking;
            if (root.error && line.ghost > 0)
                return Strings.jWrong(line.capsOn, Hypr.layoutCode);
            if (root.job !== null && line.length === 0)
                return Strings.whileAway + " " + (root.job.label || "") + (root.job.progress !== undefined ? " " + Math.round(root.job.progress * 100) + "%" : "");
            return Strings.jLocked;
        }
        sayMeta: {
            if (root.busy)
                return Strings.jSecond;
            if (root.error && line.ghost > 0)
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
        radius: 12
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
