import QtQuick
import Quickshell
import Quickshell.Io
import qs.core
import qs.components

// Greeter face (DESIGN §12, design/mockups/greeter.html — «Линия» + Jackson, chosen 25.09).
// The boot line continues through the middle of the screen (LoginLine): who you are on the left,
// the password typed onto the line as dots, Jackson standing on it in the middle, the time and
// the ··· ——— ··· burst on the right. Top: the mark and the status corner; bottom: sessions and
// accessibility (left), language and power (right). Composition on a 1440×900 canvas, scaled.
// All logic lives in shell.qml; this file lays it out and forwards input.
Item {
    id: root

    required property var greeter      // the ShellRoot in shell.qml (state + actions)

    readonly property var users: root.greeter.users
    readonly property var sessions: root.greeter.sessions
    readonly property var user: root.users.length > 0 ? root.users[root.greeter.userIndex] : null
    readonly property string shownName: root.greeter.manualUser ? root.greeter.manualName : (root.user ? root.user.display : "")

    // composition (the mockup is 1440×900)
    readonly property real s: Math.max(0.75, Math.min(1.8, Math.min(width / 1440, height / 900)))
    readonly property real lineY: Math.round(height / 2) + 0.5
    readonly property real leftX: Math.round(width * 200 / 1440)
    readonly property real rightX: Math.round(width * 1000 / 1440)

    function focusField() {
        line.focusField();
    }

    function clearField() {
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
        ambient: false
        showSignal: false
    }

    // a click anywhere gives the keyboard back to the line
    MouseArea {
        anchors.fill: parent
        onClicked: line.focusField()
    }

    // ---- top: the mark and the version (left), status (right) -------------------------------------
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
        showSsid: true
    }

    // ---- who (left, above the line) --------------------------------------------------------------------
    MText {
        x: root.leftX
        y: root.lineY - 116 * root.s
        text: Strings.loginEyebrow + (root.host.length > 0 ? "  ·  " + root.host : "")
        size: 10.5 * root.s
        caps: true
        tracking: 0.26
        color: Theme.textFaint
    }

    Row {
        x: root.leftX
        y: root.lineY - 96 * root.s
        height: 52 * root.s
        spacing: 14 * root.s

        SText {
            anchors.bottom: parent.bottom
            text: root.greeter.askingName ? Strings.userNameWord : root.shownName
            size: 46 * root.s
            font.weight: Font.Light
            color: root.greeter.askingName ? Theme.textDim : Theme.text
        }

        // more than one user: Tab (or a click) goes to the next one
        Rectangle {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10 * root.s
            visible: root.users.length > 1
            width: tabRow.implicitWidth + 16 * root.s
            height: 22 * root.s
            radius: 6 * root.s
            color: tabMouse.containsMouse ? Theme.surface2 : "transparent"
            border.width: 1
            border.color: Theme.line

            Row {
                id: tabRow

                x: 8 * root.s
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6 * root.s

                Icon {
                    anchors.verticalCenter: parent.verticalCenter
                    glyph: "chevron-down"
                    size: 12 * root.s
                    stroke: 1.8
                    color: Theme.textFaint
                }
                MText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Tab · " + Strings.moreUsers(root.users.length - 1)
                    size: 11 * root.s
                    color: Theme.textFaint
                }
            }

            MouseArea {
                id: tabMouse

                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.greeter.selectUser(root.greeter.userIndex + 1);
                    line.focusField();
                }
            }
        }
    }

    // ---- the line: password, Jackson, burst ---------------------------------------------------------------
    LoginLine {
        id: line

        anchors.fill: parent
        s: root.s
        lineY: root.lineY
        inputX: root.leftX
        burstX: root.rightX
        jacksonX: Math.round(root.width * 632 / 1440)
        masked: !root.greeter.askingName && !root.greeter.promptEcho
        busy: root.greeter.busy
        error: root.greeter.failed
        welcome: root.greeter.welcome
        say: {
            if (root.greeter.welcome)
                return Strings.jWelcome;
            if (root.greeter.busy)
                return Strings.jChecking;
            if (root.greeter.failed && line.ghost > 0)
                return Strings.jWrong(line.capsOn, Hypr.layoutCode);
            if (root.greeter.askingName)
                return Strings.jWho;
            if (root.greeter.prompt.length > 0)
                return root.greeter.prompt;
            return Strings.jHello(root.shownName);
        }
        sayMeta: {
            if (root.greeter.welcome)
                return Strings.jLoadingDesk;
            if (root.greeter.busy)
                return Strings.jSecond;
            if (root.greeter.failed && line.ghost > 0)
                return Strings.jAgain;
            if (root.greeter.prompt.length > 0)
                return Strings.jOneMoreStep;
            return line.length > 0 ? Strings.jListening : Strings.jWaiting;
        }
        onSubmit: text => root.greeter.submit(text)
    }

    // ---- under the line, left: what to do, then what happened -------------------------------------------
    Column {
        x: root.leftX
        y: root.lineY + 22 * root.s
        spacing: 12 * root.s

        MText {
            textFormat: Text.StyledText
            text: {
                const dim = "<font color=\"" + Theme.textDim + "\">Enter</font>";
                if (root.greeter.askingName)
                    return Strings.userNameWord + "  ·  " + dim + " — " + Strings.toNext;
                if (root.greeter.prompt.length > 0)
                    return root.greeter.prompt + "  ·  " + dim + " — " + Strings.toNext;
                return (line.length > 0 ? Strings.passwordWord : Strings.typePassword) + "  ·  " + dim + " — " + Strings.toLogin;
            }
            size: 11 * root.s
            color: Theme.textFaint
        }

        MText {
            textFormat: Text.StyledText
            text: {
                if (root.greeter.message.length > 0)
                    return "<font color=\"" + (root.greeter.failed ? Theme.bad : Theme.textDim) + "\">" + Fmt.escape(root.greeter.message) + "</font>";
                const parts = [];
                const last = root.user ? root.greeter.lastLoginText(root.user.name, clock.date) : "";
                if (last.length > 0)
                    parts.push(last);
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

    // ---- when (right) ------------------------------------------------------------------------------------------
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

    // ---- footer ---------------------------------------------------------------------------------------------------
    component FootButton: Item {
        id: fb

        property string text: ""
        property string glyph: ""
        property bool selected: false
        property bool confirm: false          // power: the first click arms, the second (within 3 s) runs
        property bool armed: false

        signal activated

        implicitWidth: fbRow.implicitWidth
        implicitHeight: 24 * root.s

        Row {
            id: fbRow

            anchors.verticalCenter: parent.verticalCenter
            spacing: 7 * root.s

            Icon {
                anchors.verticalCenter: parent.verticalCenter
                visible: fb.glyph.length > 0
                glyph: fb.glyph
                size: 13 * root.s
                stroke: 1.7
                color: fbLabel.color
            }
            MText {
                id: fbLabel

                anchors.verticalCenter: parent.verticalCenter
                text: fb.armed ? Strings.pressAgain(fb.text) : fb.text
                size: 11 * root.s
                color: fb.armed ? Theme.warn : fb.selected || fbMouse.containsMouse ? Theme.text : Theme.textFaint
            }
        }

        MouseArea {
            id: fbMouse

            anchors.fill: parent
            anchors.margins: -6
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                if (!fb.confirm) {
                    fb.activated();
                } else if (fb.armed) {
                    fb.armed = false;
                    fb.activated();
                } else {
                    fb.armed = true;
                    disarm.restart();
                }
                line.focusField();
            }
        }

        Timer {
            id: disarm

            interval: 3000
            onTriggered: fb.armed = false
        }
    }

    Row {
        id: footLeft

        x: root.leftX
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 34 * root.s
        spacing: 22 * root.s

        Row {
            spacing: 14 * root.s
            visible: root.sessions.length > 1

            MText {
                anchors.verticalCenter: parent.verticalCenter
                text: Strings.sessionLabel.toLowerCase()
                size: 11 * root.s
                color: Theme.textFaint
            }

            Repeater {
                model: root.sessions

                FootButton {
                    required property var modelData
                    required property int index

                    text: Strings.ru && modelData.nameRu.length > 0 ? modelData.nameRu : modelData.name
                    selected: index === root.greeter.sessionIndex
                    onActivated: root.greeter.sessionIndex = index
                }
            }
        }

        FootButton {
            id: a11yButton

            glyph: "svoya-accessibility"
            text: Strings.a11yShort
            selected: root.greeter.a11yOpen
            onActivated: root.greeter.a11yOpen = !root.greeter.a11yOpen
        }
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: root.leftX
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 34 * root.s
        spacing: 22 * root.s

        Row {
            spacing: 8 * root.s

            FootButton {
                text: "RU"
                selected: Strings.ru
                onActivated: Strings.langOverride = "ru"
            }
            MText {
                anchors.verticalCenter: parent.verticalCenter
                text: "·"
                size: 11 * root.s
                color: Theme.textFaint
            }
            FootButton {
                text: "EN"
                selected: !Strings.ru
                onActivated: Strings.langOverride = "en"
            }
        }

        FootButton {
            glyph: "moon"
            text: Strings.suspend.toLowerCase()
            onActivated: Quickshell.execDetached(["systemctl", "suspend"])
        }
        FootButton {
            glyph: "svoya-restart"
            text: Strings.reboot.toLowerCase()
            confirm: true
            onActivated: Quickshell.execDetached(["systemctl", "reboot"])
        }
        FootButton {
            glyph: "power"
            text: Strings.poweroff.toLowerCase()
            confirm: true
            onActivated: Quickshell.execDetached(["systemctl", "poweroff"])
        }
    }

    // ---- accessibility popover (Super+Alt+A or the footer button) ---------------------------------------------
    Rectangle {
        id: a11yPop

        visible: root.greeter.a11yOpen
        x: root.leftX
        anchors.bottom: footLeft.top
        anchors.bottomMargin: 14 * root.s
        width: 300
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
