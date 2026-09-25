import QtQuick
import qs.core
import qs.components

// Step 7 · what stays with you: the privacy promise, the first system
// snapshot (`sos snapshot create --json`; works without a password when
// snapper allows the user, otherwise it says so), what will be installed after
// setup, and the keys worth remembering.
Item {
    id: root

    required property var wizard

    readonly property var promises: [Strings.wizPrivacy1, Strings.wizPrivacy2, Strings.wizPrivacy3, Strings.wizPrivacy4]
    readonly property var combos: [
        { keys: ["Super", "Space"], text: Strings.csLauncher },
        { keys: ["Super", "J"], text: Strings.csJackson },
        { keys: ["Super", "V"], text: Strings.csClipboard },
        { keys: ["Super", "Shift", "S"], text: Strings.csShot },
        { keys: ["Super", "K"], text: Strings.csCheatsheet },
        { keys: ["Super", "Z"], text: Strings.csUndo },
        { keys: ["Super", "L"], text: Strings.csLock },
        { keys: ["Super", "Alt", "A"], text: Strings.csAccessibility }
    ]

    Row {
        spacing: 16

        Column {
            width: 608
            spacing: 16

            // promises
            Rectangle {
                width: parent.width
                height: promiseCol.height + 32
                radius: 14
                color: Theme.isDark ? Theme.surface : Theme.surface2
                border.width: 1
                border.color: Theme.line

                Column {
                    id: promiseCol

                    x: 18
                    y: 16
                    width: parent.width - 36
                    spacing: 10

                    Repeater {
                        model: root.promises

                        Row {
                            required property string modelData

                            width: parent.width
                            spacing: 12

                            Icon {
                                y: 3
                                glyph: "check"
                                size: 14
                                stroke: 2.2
                                color: Theme.ok
                            }
                            SText {
                                width: parent.width - 26
                                text: modelData
                                size: 13.5
                                lineHeight: 20
                                lineHeightMode: Text.FixedHeight
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }

            // first snapshot
            Rectangle {
                width: parent.width
                height: 14 + 20 + 3 + snapSub.height + 14 + 34 + 16
                radius: 14
                color: Theme.isDark ? Theme.surface : Theme.surface2
                border.width: 1
                border.color: Theme.line

                SText {
                    x: 18
                    y: 14
                    height: 20
                    text: Strings.wzSnapshotTitle
                    size: 14
                    font.weight: Font.Medium
                }
                SText {
                    id: snapSub

                    x: 18
                    y: 37
                    width: parent.width - 36
                    text: Strings.wzSnapshotSub
                    size: 12.5
                    lineHeight: 19
                    lineHeightMode: Text.FixedHeight
                    wrapMode: Text.WordWrap
                    color: Theme.textDim
                }
                Row {
                    x: 18
                    y: snapSub.y + snapSub.height + 14
                    height: 34
                    spacing: 12

                    Button {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: root.wizard.snapState !== "done"
                        glyph: "svoya-restart"
                        text: root.wizard.snapState === "running" ? "…" : Strings.wzSnapshotButton
                        enabledState: root.wizard.snapState !== "running"
                        onClicked: root.wizard.snapshot()
                    }
                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: root.wizard.snapState === "done"
                        glyph: "check"
                        size: 14
                        stroke: 2.2
                        color: Theme.ok
                    }
                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: root.wizard.snapState === "done" || root.wizard.snapState === "error"
                        text: root.wizard.snapState === "done" ? Strings.wizSnapshotDone + " " + root.wizard.snapInfo : Strings.wizSnapshotFailed
                        size: 11
                        color: root.wizard.snapState === "done" ? Theme.ok : Theme.warn
                    }
                }
            }

            // queued installs
            Rectangle {
                width: parent.width
                height: 48
                radius: 14
                visible: root.wizard.queuedModules.length > 0
                color: Theme.isDark ? Theme.surface : Theme.surface2
                border.width: 1
                border.color: Theme.line

                Icon {
                    x: 18
                    anchors.verticalCenter: parent.verticalCenter
                    glyph: "package"
                    size: 18
                }
                SText {
                    x: 50
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 68
                    elide: Text.ElideRight
                    textFormat: Text.StyledText
                    text: Strings.wzQueued + " <font color=\"" + Theme.text + "\"><b>" + root.wizard.queuedModules.map(id => root.wizard.moduleName(id)).join(", ") + "</b></font> · " + Strings.wzUndoHint
                    size: 13
                    color: Theme.textDim
                }
            }
        }

        // keys
        Rectangle {
            width: 1040 - 608 - 16
            height: 14 + 20 + 12 + root.combos.length * 32 + 12
            radius: 14
            color: Theme.isDark ? Theme.surface : Theme.surface2
            border.width: 1
            border.color: Theme.line

            SText {
                x: 18
                y: 14
                height: 20
                text: Strings.wzKeysTitle
                size: 14
                font.weight: Font.Medium
            }

            Column {
                x: 18
                y: 46
                width: parent.width - 36

                Repeater {
                    model: root.combos

                    Item {
                        required property var modelData

                        width: parent.width
                        height: 32

                        Row {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4

                            Repeater {
                                model: modelData.keys

                                Keycap {
                                    required property string modelData

                                    text: modelData
                                }
                            }
                        }
                        SText {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 150
                            horizontalAlignment: Text.AlignRight
                            elide: Text.ElideRight
                            text: modelData.text
                            size: 13
                            color: Theme.textDim
                        }
                    }
                }
            }
        }
    }
}
