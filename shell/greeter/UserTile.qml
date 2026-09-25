import QtQuick
import Quickshell.Widgets
import qs.core
import qs.components

// One user on the greeter (design/mockups/greeter.html .user): 176px wide,
// 56px avatar circle (surface3, 1px lineStrong; the selected one gets a 3px gap
// in the wall color and a 2px accent ring), name Plex Sans 14/18 (500 when
// selected, textDim 400 otherwise), a mono 11/16 meta line in textFaint.
// Unselected avatars are drawn at 72% opacity.
Item {
    id: root

    property string name: ""
    property string meta: ""
    property string avatar: ""       // image path or ""
    property bool selected: false

    signal picked

    width: 176
    height: 56 + 14 + 18 + 3 + 16

    // ring: 0 0 0 3px wall, 0 0 0 5px accent
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        y: -5
        width: 66
        height: 66
        radius: 33
        visible: root.selected
        color: Theme.accent
        antialiasing: true

        Rectangle {
            anchors.centerIn: parent
            width: 62
            height: 62
            radius: 31
            color: Theme.wall
            antialiasing: true
        }
    }

    ClippingRectangle {
        id: circle

        anchors.horizontalCenter: parent.horizontalCenter
        width: 56
        height: 56
        radius: 28
        color: Theme.surface3
        border.width: 1
        border.color: Theme.lineStrong
        opacity: root.selected ? 1 : 0.72

        Image {
            id: face

            anchors.fill: parent
            source: root.avatar.length > 0 ? "file://" + root.avatar : ""
            sourceSize.width: 112
            sourceSize.height: 112
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            visible: status === Image.Ready
        }

        SText {
            anchors.centerIn: parent
            visible: face.status !== Image.Ready
            text: root.name.length > 0 ? root.name[0].toUpperCase() : "?"
            size: 20
            font.weight: Font.Medium
        }
    }

    SText {
        anchors.horizontalCenter: parent.horizontalCenter
        y: 56 + 14
        height: 18
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: root.name
        size: 14
        font.weight: root.selected ? Font.Medium : Font.Normal
        color: root.selected ? Theme.text : Theme.textDim
    }

    MText {
        anchors.horizontalCenter: parent.horizontalCenter
        y: 56 + 14 + 18 + 3
        height: 16
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: root.meta
        size: 11
        color: Theme.textFaint
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.picked()
    }
}
