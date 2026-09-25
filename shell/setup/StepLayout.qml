import QtQuick
import Quickshell.Widgets
import qs.core
import qs.components

// Step 4 · windows: Clean (floating), Classic (taskbar at the bottom), Hacker
// (tiling, no title bars, accent border). Pictures are rendered from the
// mockup CSS (assets/setup/layout-<id>-<graphite|paper>.png). Picking one sets
// Settings.layout; the shell moves the bar and reloads the Hyprland preset.
Item {
    id: root

    required property var wizard

    readonly property var presets: [
        { id: "clean", name: Strings.wizClean, hint: Strings.wizCleanHint, glyph: "svoya-windows" },
        { id: "classic", name: Strings.wizClassic, hint: Strings.wizClassicHint, glyph: "panel-bottom" },
        { id: "hacker", name: Strings.wizHacker, hint: Strings.wizHackerHint, glyph: "svoya-tiles" }
    ]

    Row {
        spacing: 16

        Repeater {
            model: root.presets

            WizCard {
                id: card

                required property var modelData

                width: 336
                height: 8 + 200 + 12 + 20 + 3 + 40 + 14
                selected: Settings.layout === modelData.id
                onPicked: Settings.layout = modelData.id

                ClippingRectangle {
                    x: 8
                    y: 8
                    width: 320
                    height: 200
                    radius: 8
                    color: Theme.surface3

                    Image {
                        anchors.fill: parent
                        source: Theme.asset("setup/layout-" + card.modelData.id + "-" + (Theme.isDark ? "graphite" : "paper") + ".png")
                        sourceSize.width: 696
                        sourceSize.height: 435
                        fillMode: Image.PreserveAspectCrop
                        smooth: true
                        mipmap: true
                    }
                }

                Rectangle {
                    x: 8
                    y: 8
                    width: 320
                    height: 200
                    radius: 8
                    color: "transparent"
                    border.width: 1
                    border.color: Qt.rgba(0.5, 0.5, 0.5, 0.18)
                }

                Row {
                    x: 14
                    y: 220
                    height: 20
                    spacing: 8

                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        glyph: card.modelData.glyph
                        size: 16
                        stroke: 1.7
                        color: card.selected ? Theme.accent : Theme.textDim
                    }
                    SText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: card.modelData.name
                        size: 15
                        font.weight: Font.Medium
                    }
                }

                WizCheck {
                    x: card.width - 14 - width
                    y: 221
                    checked: card.selected
                }

                SText {
                    x: 14
                    y: 243
                    width: card.width - 28
                    text: card.modelData.hint
                    size: 13
                    lineHeight: 20
                    lineHeightMode: Text.FixedHeight
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                    color: Theme.textDim
                }
            }
        }
    }
}
