import QtQuick
import qs.core
import qs.components

// Shortcut cheat sheet (Super+K): the default keyboard map
// (docs/ARCHITECTURE.md §6) as keycaps in two columns.
PanelFrame {
    id: root

    readonly property var rows: [
        { keys: "Super Space", text: Strings.csLauncher },
        { keys: "Super J", text: Strings.csJackson },
        { keys: "Super V", text: Strings.csClipboard },
        { keys: "Super Shift S", text: Strings.csShot },
        { keys: "Super Enter", text: Strings.csTerminal },
        { keys: "Super E", text: Strings.csFiles },
        { keys: "Super Q", text: Strings.csClose },
        { keys: "Super F", text: Strings.csFullscreen },
        { keys: "Super T", text: Strings.csTiling },
        { keys: "Super 1…9", text: Strings.csWorkspaces },
        { keys: "Super Shift 1…9", text: Strings.csMoveToWorkspace },
        { keys: "Super ← → ↑ ↓", text: Strings.csFocus },
        { keys: "Super K", text: Strings.csCheatsheet },
        { keys: "Super Z", text: Strings.csUndo },
        { keys: "Super Esc", text: Strings.csDoctor },
        { keys: "Super L", text: Strings.csLock },
        { keys: "Super A", text: Strings.csControlCenter },
        { keys: "Super Shift Q", text: Strings.csSession },
        { keys: "Super Alt A", text: Strings.csAccessibility },
        { keys: "Alt Shift", text: Strings.csLayout }
    ]
    readonly property int half: Math.ceil(root.rows.length / 2)

    width: 760
    implicitHeight: col.implicitHeight

    onShownChanged: {
        if (root.shown)
            Qt.callLater(() => keys.forceActiveFocus());
    }

    Item {
        id: keys

        focus: true
        Keys.onEscapePressed: Ui.hide()
        Keys.onPressed: event => {
            if (event.key === Qt.Key_K || event.key === Qt.Key_Return) {
                Ui.hide();
                event.accepted = true;
            }
        }
    }

    Column {
        id: col

        width: parent.width

        Item {
            width: parent.width
            height: 54

            SText {
                x: 18
                anchors.verticalCenter: parent.verticalCenter
                text: Strings.shortcuts
                size: Theme.fsHeading
                font.weight: Font.Medium
            }

            MorseMark {
                anchors.right: parent.right
                anchors.rightMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.textDim
            }
        }

        Divider {
            width: parent.width
        }

        Row {
            x: 18
            topPadding: 12
            bottomPadding: 16
            spacing: 24

            Repeater {
                model: 2

                Column {
                    id: column

                    required property int index

                    width: (col.width - 36 - 24) / 2
                    spacing: 2

                    Repeater {
                        model: root.rows.slice(column.index * root.half, (column.index + 1) * root.half)

                        Item {
                            required property var modelData

                            width: column.width
                            height: 32

                            KeyCombo {
                                anchors.verticalCenter: parent.verticalCenter
                                keys: modelData.keys
                            }

                            SText {
                                x: 150
                                width: parent.width - 150
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.text
                                size: 13
                                color: Theme.textDim
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
            }
        }
    }
}
