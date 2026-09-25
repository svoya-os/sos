import QtQuick
import qs.core

// Pill chip: 22px, 1px lineStrong border, mono 11 textDim, optional status dot.
// Used for Jackson's route («● локально · qwen3.5-14b»).
Rectangle {
    id: root

    property string text: ""
    property color dotColor: Theme.ok
    property bool showDot: true

    implicitWidth: row.implicitWidth + 18
    implicitHeight: 22
    radius: height / 2
    color: "transparent"
    border.width: 1
    border.color: Theme.lineStrong
    antialiasing: true

    Row {
        id: row

        anchors.centerIn: parent
        spacing: 7

        Dot {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.showDot
            color: root.dotColor
        }

        MText {
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            size: 11
            color: Theme.textDim
        }
    }
}
