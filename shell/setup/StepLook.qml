import QtQuick
import Quickshell
import Quickshell.Widgets
import qs.core
import qs.components

// Step 3 · look (design/mockups/setup-look.html). Four theme cards with the
// mockup's mini desktops (assets/setup/theme-*.png), the «Auto» day strip
// (07:00–20:00, a marker for now) and three option rows. Picking a card runs
// `sos theme apply <id>`: the whole screen, this wizard included, recolors.
Item {
    id: root

    required property var wizard

    readonly property var themes: [
        { id: "graphite", name: Strings.themeGraphite, sub: Strings.wzGraphiteSub, a: "0c0d0f", b: "ffb547" },
        { id: "paper", name: Strings.themePaper, sub: Strings.wzPaperSub, a: "e9e6de", b: "2b3af7" },
        { id: "auto", name: Strings.themeAuto, sub: Strings.wzAutoSub, a: "", b: "" },
        { id: "phosphor", name: Strings.themePhosphor, sub: Strings.wzPhosphorSub, a: "050806", b: "5cf08f" }
    ]

    SystemClock {
        id: now

        precision: SystemClock.Minutes
    }

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
                onPicked: root.wizard.applyTheme(modelData.id)

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

    // ---- how «Auto» works: a 24-hour strip ------------------------------------------------------------
    Rectangle {
        id: auto

        y: cards.height + 20
        width: parent.width
        height: 32 + Math.max(autoText.height, 44)
        radius: 14
        color: Theme.isDark ? Theme.surface : Theme.surface2
        border.width: 1
        border.color: Theme.line

        Column {
            id: autoText

            x: 18
            anchors.verticalCenter: parent.verticalCenter
            width: 372
            spacing: 3

            SText {
                height: 18
                text: Strings.wzAutoTitle
                size: 13
                font.weight: Font.Medium
            }
            SText {
                width: parent.width
                text: Strings.wzAutoBody
                size: 12.5
                lineHeight: 19
                lineHeightMode: Text.FixedHeight
                wrapMode: Text.WordWrap
                color: Theme.textDim
            }
        }

        Item {
            id: day

            readonly property real dawn: 7 / 24
            readonly property real dusk: 20 / 24
            readonly property real nowPos: (now.date.getHours() * 60 + now.date.getMinutes()) / 1440
            readonly property color night: Theme.isDark ? "#2a2d33" : "#3a3d44"
            readonly property color light: Theme.isDark ? "#d9d5cb" : "#cdc8bc"

            x: 18 + 372 + 40
            width: parent.width - x - 18
            height: 44
            anchors.verticalCenter: parent.verticalCenter

            Row {
                y: 11
                width: parent.width
                height: 6
                spacing: 2

                Rectangle {
                    width: day.width * day.dawn - 2
                    height: 6
                    radius: 3
                    color: day.night
                }
                Rectangle {
                    width: day.width * (day.dusk - day.dawn) - 2
                    height: 6
                    radius: 3
                    color: day.light
                }
                Rectangle {
                    width: day.width * (1 - day.dusk)
                    height: 6
                    radius: 3
                    color: day.night
                }
            }

            Rectangle {
                x: day.width * day.nowPos - 1
                y: 6
                width: 2
                height: 16
                radius: 1
                color: Theme.accent
            }

            MText {
                x: Math.min(day.width - width, Math.max(0, day.width * day.nowPos - width / 2))
                y: -14
                text: Strings.wzNow + " " + Fmt.clock(now.date)
                size: 11
                font.weight: Font.Medium
                color: Theme.accent
            }

            Repeater {
                model: [
                    { at: 0, text: "00:00", edge: -1 },
                    { at: day.dawn, text: "07:00 · " + Strings.themePaper, edge: 0 },
                    { at: day.dusk, text: "20:00 · " + Strings.themeGraphite, edge: 0 },
                    { at: 1, text: "24:00", edge: 1 }
                ]

                MText {
                    required property var modelData

                    x: modelData.edge < 0 ? 0 : (modelData.edge > 0 ? day.width - width : day.width * modelData.at - width / 2)
                    y: 28
                    text: modelData.text
                    size: 11
                    color: Theme.textFaint
                }
            }
        }
    }

    // ---- options ------------------------------------------------------------------------------------------
    Row {
        y: auto.y + auto.height + 16
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
