import QtQuick
import qs.core
import qs.components

// Step 2 · language and keyboard. Two language cards (the whole UI switches at
// once), layout chips (the first one drives shortcuts; English is kept first
// when chosen), the switch key, and a field to try the result. Layout changes
// go to Settings; the shell writes them to Hyprland (svoya-shell.conf).
Item {
    id: root

    required property var wizard

    readonly property var layouts: (Settings.kbLayouts || "us,ru").split(",").filter(x => x.length > 0)
    readonly property var available: ["us", "ru", "ua", "by", "kz", "de", "fr", "es", "pl", "tr"]
    readonly property var switches: [
        { id: "grp:alt_shift_toggle", label: "Alt + Shift" },
        { id: "grp:ctrl_shift_toggle", label: "Ctrl + Shift" },
        { id: "grp:caps_toggle", label: "Caps Lock" }
    ]

    function toggleLayout(code) {
        let list = root.layouts.slice();
        const at = list.indexOf(code);
        if (at >= 0) {
            if (list.length === 1)
                return;
            list.splice(at, 1);
        } else {
            list.push(code);
        }
        // shortcuts follow the first layout: keep the Latin one first
        if (list.indexOf("us") > 0) {
            list.splice(list.indexOf("us"), 1);
            list.unshift("us");
        }
        root.wizard.setKeyboard(list.join(","), Settings.kbSwitch || "grp:alt_shift_toggle");
    }

    Column {
        width: parent.width
        spacing: 24

        Row {
            spacing: 16

            Repeater {
                model: [
                    { id: "ru", name: "Русский", hint: Strings.wzRuHint },
                    { id: "en", name: "English", hint: Strings.wzEnHint }
                ]

                WizCard {
                    id: langCard

                    required property var modelData

                    width: 336
                    height: 86
                    selected: Strings.lang === modelData.id
                    onPicked: Settings.language = modelData.id

                    WizTile {
                        x: 18
                        y: 18
                        glyph: "svoya-globe"
                        accent: langCard.selected
                    }
                    SText {
                        x: 62
                        y: 18
                        height: 20
                        text: modelData.name
                        size: 15
                        font.weight: Font.Medium
                    }
                    SText {
                        x: 62
                        y: 42
                        width: parent.width - 62 - 18
                        height: 20
                        text: modelData.hint
                        size: 13
                        color: Theme.textDim
                        elide: Text.ElideRight
                    }
                    WizCheck {
                        x: parent.width - 18 - width
                        y: 19
                        checked: langCard.selected
                    }
                }
            }
        }

        // layouts
        Column {
            width: parent.width
            spacing: 12

            Row {
                spacing: 10

                SText {
                    id: layoutsTitle

                    text: Strings.wzLayouts
                    size: 14
                    font.weight: Font.Medium
                }
                MText {
                    anchors.baseline: layoutsTitle.baseline
                    text: Strings.wzLayoutsHint
                    size: 11
                    color: Theme.textFaint
                }
            }

            Flow {
                width: parent.width
                spacing: 8

                Repeater {
                    model: root.available

                    Rectangle {
                        id: chip

                        required property string modelData
                        readonly property int order: root.layouts.indexOf(modelData)
                        readonly property bool chosen: chip.order >= 0

                        width: chipRow.implicitWidth + 24
                        height: 32
                        radius: 9
                        color: chip.chosen ? Theme.surface3 : (chipMouse.containsMouse ? Theme.surface3 : (Theme.isDark ? Theme.surface : Theme.surface2))
                        border.width: 1
                        border.color: chip.chosen ? Theme.selected : Theme.line
                        antialiasing: true

                        Row {
                            id: chipRow

                            anchors.centerIn: parent
                            spacing: 8

                            MText {
                                anchors.verticalCenter: parent.verticalCenter
                                text: chip.modelData.toUpperCase()
                                size: 11.5
                                font.weight: Font.Medium
                                color: chip.chosen ? Theme.text : Theme.textDim
                            }
                            SText {
                                anchors.verticalCenter: parent.verticalCenter
                                text: Strings.kbNames[chip.modelData] || chip.modelData
                                size: 13
                                color: chip.chosen ? Theme.text : Theme.textDim
                            }
                            MText {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: chip.order === 0 && root.layouts.length > 1
                                text: "1"
                                size: 10.5
                                color: Theme.textFaint
                            }
                        }

                        MouseArea {
                            id: chipMouse

                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.toggleLayout(chip.modelData)
                        }
                    }
                }
            }
        }

        // switch key + try field
        Row {
            spacing: 40

            Column {
                spacing: 12

                SText {
                    text: Strings.wzSwitchWith
                    size: 14
                    font.weight: Font.Medium
                }
                Segmented {
                    options: root.switches.map(s => ({ id: s.id, label: s.label }))
                    current: Settings.kbSwitch || "grp:alt_shift_toggle"
                    onPicked: key => root.wizard.setKeyboard(root.layouts.join(","), key)
                }
            }

            Column {
                spacing: 12

                SText {
                    text: Strings.wzTryHere
                    size: 14
                    font.weight: Font.Medium
                }
                Rectangle {
                    width: 360
                    height: 40
                    radius: 9
                    color: Theme.surface2
                    border.width: 1
                    border.color: tryField.input.activeFocus ? Theme.selected : Theme.lineStrong

                    TextField {
                        id: tryField

                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 60
                        placeholder: "Привет · Hello"
                        onAccepted: root.wizard.next()
                    }

                    MText {
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        text: Hypr.layoutCode
                        size: 11.5
                        font.weight: Font.Medium
                        color: Theme.textDim
                    }
                }
            }
        }
    }
}
