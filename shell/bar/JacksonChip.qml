import QtQuick
import qs.core
import qs.components

// Jackson's mini-scope (22×10) in a chip (padding 3/6, radius 6). At rest the trace is
// neutral (textDim) and still; while Jackson listens or works it is the live signal: accent,
// moving, on an accentSoft chip (DESIGN §5, §11). Hidden when the AI switch is off.
Rectangle {
    id: root

    implicitWidth: scope.width + 12
    implicitHeight: 16
    radius: Theme.radiusSmall
    visible: Jackson.enabled
    color: Jackson.signalLive ? Theme.accentSoft : (mouse.containsMouse || Ui.modal === "jackson" ? Theme.surface3 : "transparent")

    Accessible.role: Accessible.Button
    Accessible.name: Jackson.name

    Behavior on color {
        ColorAnimation {
            duration: Theme.base
        }
    }

    Oscilloscope {
        id: scope

        anchors.centerIn: parent
        width: 22
        height: 10
        mode: Jackson.mode === "off" || Jackson.mode === "offline" ? "idle" : Jackson.mode
        level: Jackson.level
        live: Jackson.active
        color: Jackson.signalLive ? Theme.accent : Theme.textDim
        glow: Jackson.signalLive && Theme.glow
        opacity: Jackson.mode === "offline" ? 0.5 : 1
        amp: 4
        freq: 1.6
        seed: 0.2
        breathe: false
    }

    MouseArea {
        id: mouse

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: Ui.toggle("jackson")
    }
}
