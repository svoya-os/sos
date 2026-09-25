import QtQuick
import Quickshell
import Quickshell.Widgets
import qs.core
import qs.components

// Step 3 · look (design/mockups/setup-look.html). Four theme cards with the
// mockup's mini desktops (assets/setup/theme-*.png), the accent (eight swatches
// + «Свой…», hover previews, a click applies: `sos theme accent <id>`) with
// «На экране входа» (on for the first user of the machine; the login screen
// gets the look after the wizard, `sos theme apply --system`), then three option
// rows. Picking a card runs `sos theme apply <id>`: the whole screen, this wizard
// included, recolors in 260 ms.
Item {
    id: root

    required property var wizard

    readonly property var themes: [
        { id: "graphite", name: Strings.themeGraphite, sub: Strings.wzGraphiteSub, a: "0c0d0f", b: "ebe8e1" },
        { id: "paper", name: Strings.themePaper, sub: Strings.wzPaperSub, a: "e9e6de", b: "151515" },
        { id: "auto", name: Strings.themeAuto, sub: Strings.wzAutoSub, a: "", b: "" },
        { id: "phosphor", name: Strings.themePhosphor, sub: Strings.wzPhosphorSub, a: "050806", b: "5cf08f" }
    ]

    Row {
        id: cards

        spacing: 16

        Repeater {
            model: root.themes

            WizCard {
                id: card

                required property var modelData

                width: 248
                height: 241
                selected: root.wizard.themeChoice === modelData.id
                onPicked: root.wizard.applyTheme(card.modelData.id)

                ClippingRectangle {
                    x: 8
                    y: 8
                    width: 232
                    height: 145
                    radius: 8
                    color: Theme.surface3

                    Image {
                        anchors.fill: parent
                        source: Theme.asset("setup/theme-" + card.modelData.id + ".png")
                        sourceSize.width: 696
                        sourceSize.height: 435
                        fillMode: Image.PreserveAspectCrop
                        smooth: true
                        mipmap: true
                    }
                }

                // inset hairline over the picture (rgba(128,128,128,.18))
                Rectangle {
                    x: 8
                    y: 8
                    width: 232
                    height: 145
                    radius: 8
                    color: "transparent"
                    border.width: 1
                    border.color: Qt.rgba(0.5, 0.5, 0.5, 0.18)
                }

                Row {
                    x: 14
                    y: 165
                    height: 20
                    spacing: 8

                    SText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: card.modelData.name
                        size: 15
                        font.weight: Font.Medium
                    }
                    WizTag {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: card.modelData.id === "auto"
                        kind: "line"
                        text: Strings.wzDefault
                    }
                }

                WizCheck {
                    x: card.width - 14 - width
                    y: 166
                    checked: card.selected
                }

                SText {
                    x: 14
                    y: 188
                    width: card.width - 28
                    height: 20
                    text: card.modelData.sub
                    size: 13
                    color: Theme.textDim
                    elide: Text.ElideRight
                }

                Row {
                    x: 14
                    y: 216
                    height: 11
                    spacing: 10

                    Repeater {
                        model: card.modelData.id === "auto" ? [{ icon: "sun", text: "07:00" }, { icon: "moon", text: "20:00" }] : [{ hex: card.modelData.a }, { hex: card.modelData.b }]

                        Row {
                            required property var modelData

                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 5

                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: modelData.hex !== undefined
                                width: 9
                                height: 9
                                radius: 3
                                color: modelData.hex !== undefined ? "#" + modelData.hex : "transparent"
                                border.width: 1
                                border.color: Qt.rgba(0.5, 0.5, 0.5, 0.35)
                            }
                            Icon {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: modelData.icon !== undefined
                                glyph: modelData.icon !== undefined ? modelData.icon : "sun"
                                size: 11
                                color: Theme.textFaint
                            }
                            MText {
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.hex !== undefined ? modelData.hex : modelData.text
                                size: 11
                                color: Theme.textFaint
                            }
                        }
                    }
                }
            }
        }
    }

    // ---- accent + the login screen ----------------------------------------------------------------------
    Rectangle {
        id: accentCard

        y: cards.height + 20
        width: parent.width
        height: Math.max(accentText.height, picker.height, 56) + 36
        radius: 14
        color: Theme.isDark ? Theme.surface : Theme.surface2
        border.width: 1
        border.color: Theme.line

        Column {
            id: accentText

            x: 18
            y: 18
            width: 236
            spacing: 4

            SText {
                height: 18
                text: Strings.accentLabel
                size: 13
                font.weight: Font.Medium
            }
            MText {
                width: parent.width
                text: Strings.wzAccentSub
                size: 11
                lineHeight: 16
                lineHeightMode: Text.FixedHeight
                wrapMode: Text.WordWrap
                color: Theme.textFaint
            }
        }

        AccentPicker {
            id: picker

            x: 18 + 236 + 16
            y: 14
            width: parent.width - x - loginSwitch.width - 36
            labels: true
            swatch: 30
        }

        Row {
            id: loginSwitch

            anchors.right: parent.right
            anchors.rightMargin: 18
            y: 22
            spacing: 12

            Toggle {
                anchors.verticalCenter: parent.verticalCenter
                checked: Settings.themeOnLogin
                Accessible.name: Strings.useOnLogin
                onToggled: value => Settings.themeOnLogin = value
            }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                SText {
                    text: Strings.wzOnLogin
                    size: 13
                    font.weight: Font.Medium
                }
                MText {
                    text: Strings.wzOnLoginSub
                    size: 11
                    color: Theme.textFaint
                }
            }
        }
    }

    // ---- options ------------------------------------------------------------------------------------------
    Row {
        y: accentCard.y + accentCard.height + 16
        width: parent.width
        spacing: 16

        WizOption {
            width: (parent.width - 32) / 3
            title: Strings.wizStartupSound
            note: Strings.wzSoundSub
            showPlay: true
            checked: Settings.startupSound
            onToggled: value => Settings.startupSound = value
            onPlayed: Sys.playSound("desktop-login")
        }
        WizOption {
            width: (parent.width - 32) / 3
            title: Strings.wizReduceMotion
            note: Strings.wzMotionSub
            checked: Settings.reduceMotion
            onToggled: value => Settings.reduceMotion = value
        }
        WizOption {
            width: (parent.width - 32) / 3
            title: Strings.wizHighContrast
            note: Strings.wzContrastSub
            checked: Settings.highContrast
            onToggled: value => Settings.highContrast = value
        }
    }
}
