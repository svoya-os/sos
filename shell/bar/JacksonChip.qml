import QtQuick
import qs.core
import qs.components

// Jackson's mini-scope (22×10) in a chip (padding 3/6, radius 6), tinted with
// accentSoft while Jackson is active. Static when idle: no frames are drawn
// unless something happens. Hidden when the AI switch is off.
Rectangle {
    id: root

    implicitWidth: avatar.implicitWidth + 12
    implicitHeight: Math.max(16, avatar.implicitHeight + 6)
    radius: Theme.radiusSmall
    visible: Jackson.enabled
    color: Jackson.active || Ui.modal === "jackson" ? Theme.accentSoft : (mouse.containsMouse ? Theme.surface3 : "transparent")

    Accessible.role: Accessible.Button
    Accessible.name: Jackson.name

    Behavior on color {
        ColorAnimation {
            duration: Theme.base
        }
    }

    JacksonAvatar {
        id: avatar

        anchors.centerIn: parent
        mini: true
        size: 16
        live: Jackson.active
    }

    MouseArea {
        id: mouse

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: Ui.toggle("jackson")
    }
}
