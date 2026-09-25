import QtQuick
import qs.core

// <kbd>: mono 500 10.5, textDim, padding 3/6/4, 1px lineStrong border with a
// 2px bottom edge, radius 5, surface background.
Rectangle {
    id: root

    property string text: ""
    property color textColor: Theme.textDim

    implicitWidth: label.implicitWidth + 12 + 2
    implicitHeight: 10.5 + 7 + 3 + 1
    radius: Theme.radiusKeycap
    color: Theme.lineStrong
    antialiasing: true

    Rectangle {
        anchors.fill: parent
        anchors.leftMargin: 1
        anchors.rightMargin: 1
        anchors.topMargin: 1
        anchors.bottomMargin: 2
        radius: Theme.radiusKeycap - 1
        color: Theme.surface
        antialiasing: true
    }

    MText {
        id: label

        anchors.horizontalCenter: parent.horizontalCenter
        y: 3
        height: 10.5 + 1
        text: root.text
        size: 10.5
        font.weight: Font.Medium
        color: root.textColor
    }
}
