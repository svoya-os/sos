import QtQuick
import Quickshell
import Quickshell.Widgets
import qs.core

// Lock screen face (DESIGN.md §5, design/mockups/lock.html): the wallpaper with
// the signal line, status top-right, the hero column at 226/900 of the height
// (clock + date, user row 56px below, 320px password field, a status line),
// and the bottom row: accessibility (left), the Morse mark (center), the
// colophon (right, drawn by the wallpaper).
Item {
    id: root

    property string userName: Sys.user
    property string displayName: root.userName
    property string avatar: ""            // image path; the initial letter otherwise
    property bool busy: false
    property string message: ""           // PAM prompt, info or error
    property bool error: false
    property bool inputEnabled: true

    signal submit(string password)

    function focusField() {
        field.focusField();
    }

    function clear() {
        field.clear();
    }

    Wallpaper {
        anchors.fill: parent
        colophon: true
    }

    CornerStatus {
        anchors.top: parent.top
        anchors.topMargin: 18
        anchors.right: parent.right
        anchors.rightMargin: 24
        showLayout: true
    }

    Item {
        id: hero

        y: Math.round(parent.height * 226 / 900)
        width: parent.width
        height: 314

        BigClock {
            anchors.horizontalCenter: parent.horizontalCenter
        }

        // user row: 40px avatar + 12 + name (Plex Sans 500 15)
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            y: 126 + 56
            height: 40
            spacing: 12

            ClippingRectangle {
                width: 40
                height: 40
                radius: 20
                color: Theme.surface3
                border.width: 1
                border.color: Theme.lineStrong

                Image {
                    id: face

                    anchors.fill: parent
                    source: root.avatar.length > 0 ? "file://" + root.avatar : ""
                    sourceSize.width: 80
                    sourceSize.height: 80
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    visible: status === Image.Ready
                }

                SText {
                    anchors.centerIn: parent
                    visible: face.status !== Image.Ready
                    text: root.displayName.length > 0 ? root.displayName[0].toUpperCase() : "?"
                    size: 15
                    font.weight: Font.Medium
                }
            }

            SText {
                anchors.verticalCenter: parent.verticalCenter
                text: root.displayName
                size: 15
                font.weight: Font.Medium
            }
        }

        PasswordField {
            id: field

            anchors.horizontalCenter: parent.horizontalCenter
            y: 126 + 56 + 40 + 22
            busy: root.busy
            error: root.error
            inputEnabled: root.inputEnabled
            onSubmit: text => root.submit(text)
        }

        // status line (14px below the field): a PAM message, else a running job
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            y: field.y + 40 + 14
            height: 16
            spacing: 8
            visible: root.message.length > 0 || Status.job !== null

            Dot {
                anchors.verticalCenter: parent.verticalCenter
                visible: root.message.length === 0
                size: 5
                color: Theme.accent
            }

            MText {
                anchors.verticalCenter: parent.verticalCenter
                height: 16
                visible: root.message.length > 0
                text: root.message
                size: 11
                color: root.error ? Theme.bad : Theme.textDim
            }

            MText {
                readonly property var job: Status.job

                anchors.verticalCenter: parent.verticalCenter
                height: 16
                visible: root.message.length === 0 && job !== null
                textFormat: Text.StyledText
                text: job === null ? "" : Strings.whileAway + " " + (job.label || "") + (job.progress !== undefined ? " <font color=\"" + Theme.textDim + "\">" + Math.round(job.progress * 100) + "%</font>" : "") + (job.etaSec ? " · " + Strings.left(job.etaSec) : "")
                size: 11
                color: Theme.textFaint
            }
        }
    }

    // accessibility: a small popover with the three switches that matter here
    TextButton {
        id: a11y

        anchors.left: parent.left
        anchors.leftMargin: 28
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 22
        glyph: "svoya-accessibility"
        text: Strings.a11yShort
        selected: a11yPop.visible
        onClicked: a11yPop.visible = !a11yPop.visible
    }

    Rectangle {
        id: a11yPop

        visible: false
        anchors.left: a11y.left
        anchors.bottom: a11y.top
        anchors.bottomMargin: 12
        width: 272
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

    // the mark, 1.5×, centered 38px above the bottom edge
    MorseMark {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 36
        unit: 1.5
    }
}
