import QtQuick
import Quickshell
import qs.core

// One notification (toast or control-center history). Head: mono 11 app name
// (textDim 500) + time (textFaint); Jackson's carry his mini avatar/scope.
// Body: Plex Sans 13/1.5 — summary in text, body in textDim. Up to two
// actions as small buttons. `entry` is a toast record from Notifs (real
// Notification in `entry.n`, or a local shell toast); `notification` a bare one.
Item {
    id: root

    property var entry: null
    property var notification: root.entry ? root.entry.n : null
    property bool compact: false
    property bool toast: false

    signal closeRequested

    readonly property var n: root.notification
    readonly property string appName: root.n ? (root.n.appName || "") : (root.entry ? root.entry.appName || "" : "")
    readonly property string summary: root.clean(root.n ? root.n.summary : (root.entry ? root.entry.summary : ""))
    readonly property string body: root.clean(root.n ? root.n.body : (root.entry ? root.entry.body : ""))
    readonly property var actions: root.n && root.n.actions ? root.n.actions.slice(0, 2) : []
    readonly property bool jackson: root.entry ? root.entry.jackson === true : (root.n ? Notifs.isJackson(root.n) : false)
    readonly property var when: root.entry && root.entry.time ? root.entry.time : Notifs.timeOf(root.n)

    // Bodies arrive as plain text or with light markup: show plain text only.
    function clean(s) {
        return (s || "").replace(/<[^>]*>/g, "").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&").replace(/&quot;/g, "\"").replace(/&#39;/g, "'").trim();
    }

    implicitHeight: col.implicitHeight + (root.compact ? 16 : 27)
    implicitWidth: 330

    SystemClock {
        id: clock

        precision: SystemClock.Minutes
    }

    Rectangle {
        anchors.fill: parent
        visible: root.compact
        radius: 8
        color: hover.containsMouse ? Theme.surface3 : "transparent"
    }

    HoverHandler {
        id: hover
    }

    Column {
        id: col

        x: root.compact ? 8 : 14
        y: root.compact ? 8 : 13
        width: parent.width - 2 * x
        spacing: root.compact ? 5 : 9

        Item {
            width: parent.width
            height: 14

            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8

                JacksonAvatar {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.jackson
                    mini: true
                    size: 14
                    live: false
                }

                MText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.appName
                    size: 11
                    font.weight: Font.Medium
                    font.letterSpacing: 0.22
                    color: Theme.textDim
                }

                MText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.when ? Fmt.ago(root.when, clock.date) : ""
                    size: 11
                    font.letterSpacing: 0.22
                    color: Theme.textFaint
                }
            }

            Icon {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                visible: hover.hovered
                glyph: "x"
                size: 13
                color: closeMouse.containsMouse ? Theme.text : Theme.textFaint

                MouseArea {
                    id: closeMouse

                    anchors.fill: parent
                    anchors.margins: -6
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (root.n)
                            root.n.dismiss();
                        root.closeRequested();
                    }
                }
            }
        }

        SText {
            width: parent.width
            visible: text.length > 0
            text: root.summary
            size: 13
            wrapMode: Text.WordWrap
            maximumLineCount: root.compact ? 2 : 3
            elide: Text.ElideRight
            lineHeight: 1.5
            color: Theme.text
        }

        SText {
            width: parent.width
            visible: text.length > 0
            text: root.body
            size: 13
            wrapMode: Text.WordWrap
            maximumLineCount: root.compact ? 2 : 4
            elide: Text.ElideRight
            lineHeight: 1.5
            color: Theme.textDim
        }

        Row {
            visible: root.actions.length > 0
            spacing: 8
            topPadding: 2

            Repeater {
                model: root.actions

                Button {
                    required property var modelData

                    small: true
                    text: modelData.text || ""
                    onClicked: modelData.invoke()
                }
            }
        }
    }
}
