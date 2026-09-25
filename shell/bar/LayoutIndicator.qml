import QtQuick
import qs.core

// Keyboard layout (RU / EN); click switches to the next layout.
Item {
    id: root

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight
    visible: Hypr.layoutCode.length > 0

    Accessible.role: Accessible.Button
    Accessible.name: Strings.keyboardLayout

    BarText {
        id: label

        text: Hypr.layoutCode
    }

    MouseArea {
        anchors.fill: parent
        anchors.margins: -6
        cursorShape: Qt.PointingHandCursor
        onClicked: Hypr.nextLayout()
    }
}
