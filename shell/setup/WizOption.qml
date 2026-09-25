import QtQuick
import qs.core
import qs.components

// Option row (setup-look.html .opt-t): radius 14, 1px line, solid surface;
// title Plex Sans 500 13/18, a mono 11/16 note in textFaint, a switch on the
// right (optionally preceded by a 26px round "play" button).
Rectangle {
    id: root

    property string title: ""
    property string note: ""
    property bool checked: false
    property bool showPlay: false

    signal toggled(bool value)
    signal played

    implicitHeight: 60
    radius: 14
    color: Theme.isDark ? Theme.surface : Theme.surface2
    border.width: 1
    border.color: Theme.line
    antialiasing: true

    Column {
        x: 16
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - 32 - controls.width - 12

        SText {
            width: parent.width
            height: 18
            text: root.title
            size: 13
            font.weight: Font.Medium
            elide: Text.ElideRight
        }
        MText {
            width: parent.width
            height: 16
            text: root.note
            size: 11
            color: Theme.textFaint
            elide: Text.ElideRight
        }
    }

    Row {
        id: controls

        anchors.right: parent.right
        anchors.rightMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        spacing: 12

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.showPlay
            width: 26
            height: 26
            radius: 13
            color: playMouse.containsMouse ? Theme.surface3 : "transparent"
            border.width: 1
            border.color: Theme.lineStrong
            antialiasing: true

            Icon {
                anchors.centerIn: parent
                anchors.horizontalCenterOffset: 1
                glyph: "svoya-play"
                size: 11
                stroke: 2
                color: Theme.textDim
            }

            MouseArea {
                id: playMouse

                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.played()
            }
        }

        Toggle {
            anchors.verticalCenter: parent.verticalCenter
            checked: root.checked
            onToggled: value => root.toggled(value)
        }
    }
}
