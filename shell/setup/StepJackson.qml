import QtQuick
import qs.core
import qs.components

// Step 6, page 1 of 2 · meet Jackson (design/mockups/setup-jackson.html, WORKFLOWS §1).
// Left: the stage — his greeting, the 128 px mascot (happy), his name and look in words, how to
// call him. Right: Чёрт or Кот, a quick look (skin/fur, outfit = the accent, name), humor, and a
// sample answer that changes with the humor. Everything is written at once and stays reversible:
// the look to ~/.config/svoya/avatar.json (Avatar), humor with `j persona humor` (wizard.setHumor).
// The rest (style, glasses, persona…) lives in the customizer: right-click Jackson.
Item {
    id: root

    required property var wizard

    readonly property var look: Avatar.look
    readonly property string character: root.look.character
    readonly property real stageWidth: 392
    readonly property real colWidth: 1040 - root.stageWidth - 24
    readonly property bool nameOk: Avatar.validName(nameField.text)

    function commitName() {
        nameCommit.stop();
        const n = nameField.text.trim();
        if (n.length > 0 && Avatar.validName(n) && n !== Avatar.name)
            Avatar.set("name", n);
    }

    Component.onCompleted: nameField.text = Avatar.name
    // leaving the page within the 700 ms debounce still keeps the name
    Component.onDestruction: {
        try {
            root.commitName();
        } catch (e) {}
    }

    Timer {
        id: nameCommit

        interval: 700
        onTriggered: root.commitName()
    }

    // caps caption with a quiet note on the right
    component Head: Item {
        id: head

        property string text: ""
        property string note: ""

        width: parent ? parent.width : 0
        height: 28

        MText {
            x: 2
            anchors.top: parent.top
            text: head.text
            size: 11
            caps: true
            font.weight: Font.Medium
            color: Theme.textFaint
        }
        MText {
            anchors.right: parent.right
            anchors.rightMargin: 2
            anchors.top: parent.top
            text: head.note
            size: 11
            color: Theme.textFaint
        }
    }

    // a labelled row of the «quick look» card
    component LookRow: Item {
        id: lrow

        property string label: ""
        property bool last: false
        default property alias control: rslot.data

        width: parent ? parent.width : 0
        height: 48

        SText {
            x: 18
            anchors.verticalCenter: parent.verticalCenter
            text: lrow.label
            size: 13.5
            color: Theme.textDim
        }

        Item {
            id: rslot

            x: 150
            width: parent.width - 150 - 18
            height: parent.height
        }

        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            visible: !lrow.last
            color: Theme.line
        }
    }

    Row {
        spacing: 24

        // ==== the stage ===============================================================================
        Rectangle {
            id: stage

            width: root.stageWidth
            height: right.height
            radius: 16
            color: Theme.isDark ? Theme.surface : Theme.surface2
            border.width: 1
            border.color: Theme.line

            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                y: Math.max(24, (parent.height - height - 48) / 2)
                spacing: 18

                // his greeting
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: stage.width - 64
                    height: hello.implicitHeight + 28
                    radius: 12
                    color: Theme.surface2
                    border.width: 1
                    border.color: Theme.lineStrong

                    SText {
                        id: hello

                        x: 16
                        y: 14
                        width: parent.width - 32
                        textFormat: Text.StyledText
                        text: Strings.wzHello(Avatar.name)
                        size: 14
                        lineHeight: 1.45
                        wrapMode: Text.WordWrap
                    }
                }

                JacksonAvatar {
                    anchors.horizontalCenter: parent.horizontalCenter
                    size: 128
                    backing: false
                    menu: false
                    forceAnim: "happy"
                    live: false
                    scopeWidth: 160
                    scopeHeight: 48
                }

                Column {
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 4

                    SText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: Avatar.name
                        size: 20
                        font.weight: Font.Medium
                    }
                    MText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: {
                            const who = root.character === "cat" ? Strings.cuCat : Strings.cuImp;
                            const skin = Avatar.skinName(root.look.skin, root.character).toLowerCase();
                            const outfit = root.look.outfit === "accent" ? Strings.cuAsAccent : (Theme.accentList.find(a => a.id === root.look.outfit) || { name: root.look.outfit }).name.toLowerCase();
                            return who + " · " + skin + " · " + outfit;
                        }
                        size: 11
                        color: Theme.textFaint
                    }
                }
            }

            // how to call him
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 18
                spacing: 6

                Keycap {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Super"
                }
                Keycap {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "J"
                }
                MText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: Strings.wzCall + "   " + Strings.wzHoldVoice
                    size: 11
                    color: Theme.textFaint
                }
            }
        }

        // ==== choices ===================================================================================
        Column {
            id: right

            width: root.colWidth
            spacing: 0

            Head {
                text: Strings.wzWhoCloser
                note: Strings.wzBothSame
            }

            Row {
                spacing: 16

                Repeater {
                    model: Avatar.characters

                    WizCard {
                        id: ccard

                        required property string modelData

                        width: (root.colWidth - 16) / 2
                        height: 96
                        selected: root.character === modelData
                        onPicked: Avatar.set("character", ccard.modelData)

                        Rectangle {
                            id: tile

                            x: 14
                            anchors.verticalCenter: parent.verticalCenter
                            width: 64
                            height: 64
                            radius: 12
                            color: Theme.surface3
                            border.width: 1
                            border.color: Theme.lineStrong

                            JacksonAvatar {
                                anchors.centerIn: parent
                                size: 64
                                backing: false
                                menu: false
                                live: false
                                forceAnim: "idle"
                                look: Avatar.resolve(Object.assign({}, Avatar.stored, { character: ccard.modelData }))
                                scopeWidth: 56
                                scopeHeight: 18
                            }
                        }

                        Column {
                            anchors.left: tile.right
                            anchors.leftMargin: 14
                            anchors.right: parent.right
                            anchors.rightMargin: 40
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4

                            SText {
                                text: ccard.modelData === "cat" ? Strings.cuCat : Strings.cuImp
                                size: 15
                                font.weight: Font.Medium
                            }
                            SText {
                                width: parent.width
                                text: Strings.wzCharacterDescs[ccard.modelData] || ""
                                size: 12.5
                                lineHeight: 1.35
                                wrapMode: Text.WordWrap
                                maximumLineCount: 3
                                elide: Text.ElideRight
                                color: Theme.textDim
                            }
                        }

                        WizCheck {
                            x: ccard.width - 14 - width
                            y: 14
                            checked: ccard.selected
                        }
                    }
                }
            }

            Item {
                width: 1
                height: 14
            }

            Head {
                text: Strings.wzQuickLook
                note: Strings.wzQuickLookNote
            }

            Rectangle {
                width: root.colWidth
                height: lookCol.height
                radius: 14
                color: Theme.isDark ? Theme.surface : Theme.surface2
                border.width: 1
                border.color: Theme.line

                Column {
                    id: lookCol

                    width: parent.width

                    LookRow {
                        label: root.character === "cat" ? Strings.cuFur : Strings.cuSkin
                        height: 62

                        Row {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 8

                            Repeater {
                                model: Avatar.skins[root.character]

                                Column {
                                    id: skinCell

                                    required property string modelData

                                    width: 60
                                    spacing: 2

                                    Swatch {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        size: 26
                                        color: Avatar.skinColor(skinCell.modelData, root.character)
                                        selected: root.look.skin === skinCell.modelData
                                        label: Avatar.skinName(skinCell.modelData, root.character)
                                        onPicked: Avatar.set("skin", skinCell.modelData)
                                    }
                                    MText {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        width: parent.width
                                        horizontalAlignment: Text.AlignHCenter
                                        elide: Text.ElideRight
                                        text: Avatar.skinName(skinCell.modelData, root.character)
                                        size: 10.5
                                        color: root.look.skin === skinCell.modelData ? Theme.text : Theme.textFaint
                                    }
                                }
                            }
                        }
                    }

                    LookRow {
                        label: Strings.cuOutfit

                        Row {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 10

                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 16
                                height: 16
                                radius: 8
                                color: Avatar.outfitColor("accent", root.character)
                                border.width: 1
                                border.color: Qt.rgba(0.5, 0.5, 0.5, 0.3)
                            }
                            SText {
                                anchors.verticalCenter: parent.verticalCenter
                                text: Strings.wzOutfitAccent(Theme.accentName)
                                size: 13.5
                            }
                            MText {
                                anchors.verticalCenter: parent.verticalCenter
                                text: Strings.wzOutfitNote
                                size: 11
                                color: Theme.textFaint
                            }
                            TextButton {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: root.look.outfit !== "accent"
                                text: Strings.cuAsAccent
                                onClicked: Avatar.set("outfit", "accent")
                            }
                        }
                    }

                    LookRow {
                        label: Strings.cuName
                        height: 54

                        Row {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 14

                            Rectangle {
                                width: 250
                                height: 36
                                radius: Theme.radiusButton
                                color: Theme.isDark ? Theme.surface2 : Theme.surface
                                border.width: 1
                                border.color: nameField.input.activeFocus ? Theme.text : Theme.lineStrong

                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: -3
                                    z: -1
                                    radius: parent.radius + 3
                                    visible: nameField.input.activeFocus
                                    color: "transparent"
                                    border.width: 3
                                    border.color: Theme.line
                                }

                                TextField {
                                    id: nameField

                                    anchors.fill: parent
                                    anchors.leftMargin: 14
                                    anchors.rightMargin: 14
                                    size: 14.5
                                    placeholder: Avatar.defaultName
                                    onTextChanged: {
                                        if (nameField.input.activeFocus)
                                            nameCommit.restart();
                                    }
                                    onAccepted: {
                                        root.commitName();
                                        root.wizard.next();
                                    }
                                    onEscape: root.wizard.back()
                                }
                            }

                            MText {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.nameOk || nameField.text.length === 0 ? Strings.cuNameHint : Strings.cuNameBad
                                size: 11
                                color: root.nameOk || nameField.text.length === 0 ? Theme.textFaint : Theme.warn
                            }
                        }
                    }

                    LookRow {
                        label: Strings.cuHumor
                        last: true

                        Row {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 12

                            MText {
                                anchors.verticalCenter: parent.verticalCenter
                                text: Strings.cuHumorLow
                                size: 11
                                color: Theme.textFaint
                            }
                            Slider {
                                anchors.verticalCenter: parent.verticalCenter
                                width: root.colWidth - 150 - 18 - 24 - 170
                                value: root.wizard.humor / 2
                                Accessible.name: Strings.cuHumor
                                onMoved: v => {
                                    const level = Math.round(v * 2);
                                    if (level !== root.wizard.humor)
                                        root.wizard.setHumor(level);
                                }
                            }
                            MText {
                                anchors.verticalCenter: parent.verticalCenter
                                text: Strings.cuHumorHigh
                                size: 11
                                color: Theme.textFaint
                            }
                        }
                    }
                }
            }

            Item {
                width: 1
                height: 14
            }

            Head {
                text: Strings.wzHowHeAnswers
                note: Strings.wzHowHeAnswersNote
            }

            // a sample exchange
            Rectangle {
                width: root.colWidth
                height: 96
                radius: 14
                color: Theme.isDark ? Theme.surface : Theme.surface2
                border.width: 1
                border.color: Theme.line

                Rectangle {
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    y: 12
                    width: question.implicitWidth + 28
                    height: 32
                    radius: 10
                    color: Theme.surface3

                    SText {
                        id: question

                        anchors.centerIn: parent
                        text: Strings.wzSampleQ
                        size: 13
                    }
                }

                Row {
                    x: 14
                    y: 52
                    spacing: 12

                    JacksonAvatar {
                        anchors.verticalCenter: parent.verticalCenter
                        size: 32
                        menu: false
                        live: false
                        forceAnim: "talking"
                        scopeWidth: 32
                        scopeHeight: 12
                    }
                    SText {
                        anchors.verticalCenter: parent.verticalCenter
                        width: root.colWidth - 28 - 44
                        text: Strings.wzSampleA[Math.max(0, Math.min(2, root.wizard.humor))]
                        size: 13.5
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }
}
