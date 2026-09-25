import QtQuick
import qs.core
import qs.components

// 32×32 power button of the greeter (greeter.html .pwr span): radius 9,
// surface2 with a 1px lineStrong inset, 15px icon (stroke 1.7) in textDim.
// Needs two presses: the first arms it (a `text` edge — neutral, DESIGN §11–§12) for 3 s,
// the second acts.
Item {
    id: root

    property string glyph: "power"
    property string label: ""

    signal activated

    property bool armed: false

    width: 32
    height: 32

    Rectangle {
        anchors.fill: parent
        radius: 9
        color: root.armed ? Theme.surface3 : Theme.surface2
        border.width: root.armed ? 1.5 : 1
        border.color: root.armed ? Theme.selected : (mouse.containsMouse ? Theme.textFaint : Theme.lineStrong)
        antialiasing: true
    }

    Icon {
        anchors.centerIn: parent
        glyph: root.glyph
        size: 15
        stroke: 1.7
        color: root.armed || mouse.containsMouse ? Theme.text : Theme.textDim
    }

    // label above the button while hovered or armed
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.top
        anchors.bottomMargin: 8
        visible: mouse.containsMouse || root.armed
        width: tip.implicitWidth + 16
        height: 22
        radius: 6
        color: Theme.surface3
        border.width: 1
        border.color: Theme.lineStrong

        MText {
            id: tip

            anchors.centerIn: parent
            text: root.armed ? Strings.confirmAgain : root.label
            size: 11
            color: Theme.text
        }
    }

    Timer {
        id: disarm

        interval: 3000
        onTriggered: root.armed = false
    }

    MouseArea {
        id: mouse

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            if (root.armed) {
                root.armed = false;
                disarm.stop();
                root.activated();
            } else {
                root.armed = true;
                disarm.restart();
            }
        }
    }
}
