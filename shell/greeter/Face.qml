import QtQuick
import Quickshell
import Quickshell.Io
import qs.core
import qs.components

// Greeter face (DESIGN.md §5, design/mockups/greeter.html): host line top-left,
// Wi-Fi/battery top-right, the hero column at 180/900 of the height (clock,
// user tiles, password field, key hints), and the footer: sessions (left), the
// Morse mark (center), language and power (right). All logic lives in
// shell.qml; this file only lays it out and forwards input.
Item {
    id: root

    required property var greeter      // the ShellRoot in shell.qml (state + actions)

    readonly property var users: root.greeter.users
    readonly property var sessions: root.greeter.sessions

    function focusField() {
        field.focusField();
    }

    function clearField() {
        field.clear();
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

    Wallpaper {
        anchors.fill: parent
        colophon: false
        ambient: false
    }

    // ---- top-left: host · system ------------------------------------------------------
    Row {
        x: 24
        y: 18
        height: 16
        spacing: 8

        Icon {
            anchors.verticalCenter: parent.verticalCenter
            glyph: "monitor"
            size: 15
            stroke: 1.6
        }

        MText {
            anchors.verticalCenter: parent.verticalCenter
            height: 16
            textFormat: Text.StyledText
            text: hostnameFile.text().trim() + " <font color=\"" + Theme.textFaint + "\">·</font> " + Strings.osName + " " + Sys.osVersion
            size: 11
            font.letterSpacing: 0.22
        }
    }

    CornerStatus {
        anchors.top: parent.top
        anchors.topMargin: 18
        anchors.right: parent.right
        anchors.rightMargin: 24
        showLayout: false
        showSsid: true
    }

    // ---- hero --------------------------------------------------------------------------
    Item {
        id: hero

        y: Math.round(parent.height * 180 / 900)
        width: parent.width
        height: 381

        BigClock {
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Row {
            id: tiles

            anchors.horizontalCenter: parent.horizontalCenter
            y: 126 + 52
            spacing: 16
            visible: !root.greeter.manualUser

            Repeater {
                model: root.users

                UserTile {
                    required property var modelData
                    required property int index

                    name: modelData.display
                    avatar: modelData.avatar
                    meta: root.greeter.lastLoginText(modelData.name, clock.date)
                    selected: index === root.greeter.userIndex
                    onPicked: {
                        root.greeter.selectUser(index);
                        field.focusField();
                    }
                }
            }
        }

        // no listed users: ask for the name first (plain text), then the password
        MText {
            anchors.horizontalCenter: parent.horizontalCenter
            y: 126 + 52 + 40
            visible: root.greeter.manualUser
            text: root.greeter.manualName.length > 0 ? root.greeter.manualName : Strings.enterUserName
            size: 13
            color: Theme.textDim
        }

        PasswordField {
            id: field

            anchors.horizontalCenter: parent.horizontalCenter
            y: 126 + 52 + 107 + 26
            busy: root.greeter.busy
            error: root.greeter.failed
            masked: !root.greeter.askingName && !root.greeter.promptEcho
            placeholder: root.greeter.askingName ? Strings.userNamePlaceholder : (root.greeter.prompt.length > 0 ? root.greeter.prompt : Strings.passwordPlaceholder)
            onSubmit: text => root.greeter.submit(text)
        }

        // a message from PAM/greetd, else the key hints
        MText {
            anchors.horizontalCenter: parent.horizontalCenter
            y: field.y + 40 + 14
            height: 16
            visible: root.greeter.message.length > 0
            text: root.greeter.message
            size: 11
            color: root.greeter.failed ? Theme.bad : Theme.textDim
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            y: field.y + 40 + 14
            height: 20
            spacing: 8
            visible: root.greeter.message.length === 0

            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6
                visible: root.users.length > 1

                Keycap {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Tab"
                }
                MText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: Strings.otherUser
                    size: 11
                    color: Theme.textFaint
                }
            }

            MText {
                anchors.verticalCenter: parent.verticalCenter
                visible: root.users.length > 1
                text: "·"
                size: 11
                color: Theme.textFaint
            }

            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6

                Keycap {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Super"
                }
                Keycap {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Alt"
                }
                Keycap {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "A"
                }
                MText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: Strings.a11yShort
                    size: 11
                    color: Theme.textFaint
                }
            }
        }
    }

    // ---- accessibility popover (Super+Alt+A) ---------------------------------------------
    Rectangle {
        id: a11yPop

        visible: root.greeter.a11yOpen
        anchors.horizontalCenter: parent.horizontalCenter
        y: hero.y + field.y + 40 + 44
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

    // ---- footer (left 28, right 28, bottom 20, 32 high) ----------------------------------
    Item {
        id: foot

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: 28
        anchors.rightMargin: 28
        anchors.bottomMargin: 20
        height: 32

        Row {
            anchors.verticalCenter: parent.verticalCenter
            spacing: 14
            visible: root.sessions.length > 0

            MText {
                anchors.verticalCenter: parent.verticalCenter
                text: Strings.sessionLabel
                size: 11
                caps: true
                color: Theme.textFaint
            }

            Repeater {
                model: root.sessions

                Pill {
                    required property var modelData
                    required property int index

                    anchors.verticalCenter: parent.verticalCenter
                    text: Strings.ru && modelData.nameRu.length > 0 ? modelData.nameRu : modelData.name
                    glyph: modelData.glyph
                    selected: index === root.greeter.sessionIndex
                    onPicked: {
                        root.greeter.sessionIndex = index;
                        field.focusField();
                    }
                }
            }
        }

        MorseMark {
            anchors.centerIn: parent
            unit: 1.5
        }

        Row {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: 18

            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                Pill {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "RU"
                    selected: Strings.ru
                    onPicked: {
                        Strings.langOverride = "ru";
                        field.focusField();
                    }
                }
                Pill {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "EN"
                    selected: !Strings.ru
                    onPicked: {
                        Strings.langOverride = "en";
                        field.focusField();
                    }
                }
            }

            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8

                PowerButton {
                    glyph: "moon"
                    label: Strings.suspend
                    onActivated: Quickshell.execDetached(["systemctl", "suspend"])
                }
                PowerButton {
                    glyph: "svoya-restart"
                    label: Strings.reboot
                    onActivated: Quickshell.execDetached(["systemctl", "reboot"])
                }
                PowerButton {
                    glyph: "power"
                    label: Strings.poweroff
                    onActivated: Quickshell.execDetached(["systemctl", "poweroff"])
                }
            }
        }
    }
}
