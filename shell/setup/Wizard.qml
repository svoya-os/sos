import QtQuick
import QtQuick.Effects
import qs.core
import qs.components

// The wizard frame (design/mockups/setup.css): a 64px top strip (brand,
// progress, accessibility + skip), the 1040px content column at 104px
// (eyebrow, title, subtitle, then the step), and the footer 36px above the
// bottom (Back · note · Next/Enter). Enter = next, Esc = back; fields that
// take Enter themselves keep it.
FocusScope {
    id: root

    required property var wizard

    readonly property int step: root.wizard.step
    readonly property bool single: root.wizard.single

    Keys.onReturnPressed: root.wizard.next()
    Keys.onEnterPressed: root.wizard.next()
    Keys.onEscapePressed: root.wizard.back()

    // ---- top strip ----------------------------------------------------------------------------
    Item {
        id: top

        width: parent.width
        height: 64

        Row {
            x: 28
            anchors.verticalCenter: parent.verticalCenter
            spacing: 12

            Item {
                width: 75
                height: 13
                anchors.verticalCenter: parent.verticalCenter

                MorseMark {
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4

                SText {
                    text: Strings.wzBrand
                    size: 13
                    font.weight: Font.Medium
                }
                SText {
                    text: root.single ? Strings.wzA11yOnly : Strings.wzFirstRun
                    size: 13
                    color: Theme.textFaint
                }
            }
        }

        Row {
            anchors.centerIn: parent
            spacing: 14
            visible: !root.single

            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 5

                Repeater {
                    model: root.wizard.count

                    Item {
                        required property int index

                        width: 26
                        height: 3

                        RectangularShadow {
                            anchors.fill: seg
                            visible: index === root.step && Theme.isDark
                            radius: 2
                            blur: 8
                            color: Theme.alpha(Theme.accent, 0.4)
                        }

                        Rectangle {
                            id: seg

                            anchors.fill: parent
                            radius: 2
                            color: index === root.step ? Theme.accent : (index < root.step ? Theme.mix(Theme.lineStrong, Theme.accent, 0.55) : Theme.lineStrong)
                        }

                        MouseArea {
                            anchors.fill: parent
                            anchors.margins: -6
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.wizard.goTo(index)
                        }
                    }
                }
            }

            MText {
                anchors.verticalCenter: parent.verticalCenter
                textFormat: Text.StyledText
                text: "<font color=\"" + Theme.text + "\">" + (root.step + 1) + "</font> / " + root.wizard.count
                size: 11.5
                font.weight: Font.Medium
                font.letterSpacing: 0.46
            }
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 28
            anchors.verticalCenter: parent.verticalCenter
            spacing: 20

            Item {
                anchors.verticalCenter: parent.verticalCenter
                width: a11yRow.width
                height: 20

                Row {
                    id: a11yRow

                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8

                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        glyph: "svoya-accessibility"
                        size: 15
                        stroke: 1.6
                        color: a11yMouse.containsMouse ? Theme.text : Theme.textDim
                    }
                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 4

                        Keycap {
                            text: "Super"
                        }
                        Keycap {
                            text: "Alt"
                        }
                        Keycap {
                            text: "A"
                        }
                    }
                }

                MouseArea {
                    id: a11yMouse

                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.wizard.goTo(0)
                }
            }

            TextButton {
                anchors.verticalCenter: parent.verticalCenter
                visible: !root.single
                text: Strings.wzSkipAll
                onClicked: root.wizard.skipAll()
            }
        }
    }

    // ---- content column -----------------------------------------------------------------------------
    Item {
        id: body

        x: Math.round((parent.width - 1040) / 2)
        y: 104
        width: 1040
        height: foot.y - 20 - body.y

        MText {
            y: 0
            height: 11
            text: Strings.wzEyebrows[root.step]
            size: 11
            font.weight: Font.Medium
            caps: true
            color: Theme.accent
        }

        SText {
            y: 25
            height: 34
            text: Strings.wzTitles[root.step]
            size: 28
            font.weight: Font.Medium
        }

        InlineText {
            id: sub

            y: 69
            width: 660
            text: Strings.wzSubs[root.step]
        }

        Loader {
            id: stepLoader

            y: sub.y + sub.height + 32
            width: body.width
            height: body.height - y
            focus: true
            sourceComponent: [a11y, language, look, layout, profile, ai, privacy][root.step]
        }

        // step change: 180 ms fade and 6px rise (DESIGN §4), none with reduce motion
        Connections {
            target: root.wizard

            function onStepChanged() {
                enter.restart();
            }
        }

        ParallelAnimation {
            id: enter

            NumberAnimation {
                target: body
                property: "opacity"
                from: 0
                to: 1
                duration: Theme.base
                easing.type: Theme.easing
            }
            NumberAnimation {
                target: body
                property: "y"
                from: 110
                to: 104
                duration: Theme.base
                easing.type: Theme.easing
            }
        }
    }

    Component {
        id: a11y

        StepA11y {
            wizard: root.wizard
        }
    }
    Component {
        id: language

        StepLanguage {
            wizard: root.wizard
        }
    }
    Component {
        id: look

        StepLook {
            wizard: root.wizard
        }
    }
    Component {
        id: layout

        StepLayout {
            wizard: root.wizard
        }
    }
    Component {
        id: profile

        StepProfile {
            wizard: root.wizard
        }
    }
    Component {
        id: ai

        StepAi {
            wizard: root.wizard
        }
    }
    Component {
        id: privacy

        StepPrivacy {
            wizard: root.wizard
        }
    }

    // ---- footer ---------------------------------------------------------------------------------------
    Item {
        id: foot

        x: body.x
        y: parent.height - 36 - 40
        width: 1040
        height: 40

        Button {
            visible: root.step > 0 && !root.single
            large: true
            text: Strings.wzBack
            glyph: "chevron-left"
            fill: Theme.isDark ? Theme.surface : Theme.surface2
            textColor: Theme.textDim
            onClicked: root.wizard.back()
        }

        MText {
            anchors.centerIn: parent
            textFormat: Text.StyledText
            text: root.footNote
            size: 11
            color: Theme.textFaint
        }

        Button {
            anchors.right: parent.right
            primary: true
            large: true
            text: root.single ? Strings.wizDone : (root.wizard.last ? Strings.wizFinish : Strings.wzNext)
            hint: "Enter"
            onClicked: root.wizard.next()
        }
    }

    readonly property string footNote: {
        const w = root.wizard;
        if (w.pullState === "running" && w.pullTotal > 0)
            return Strings.wzDownloading(Fmt.bytes(w.pullBytes), Fmt.bytes(w.pullTotal)) + " · " + Math.round(w.pullFraction * 100) + "%";
        return Strings.wzFootNote.replace("<b>", "<font color=\"" + Theme.textDim + "\">").replace("</b>", "</font>");
    }
}
