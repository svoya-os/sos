import QtQuick
import qs.core

// Switch (components.css .switch): 32×18 track (surface3 + 1px lineStrong; `text` when on —
// never the accent, DESIGN §11), 12px knob 3px in (textFaint; surface when on). Space/Enter toggles when focused.
Item {
    id: root

    property bool checked: false
    signal toggled(bool value)

    implicitWidth: 32
    implicitHeight: 18
    activeFocusOnTab: true

    function flip() {
        root.toggled(!root.checked);
    }

    Keys.onSpacePressed: root.flip()
    Keys.onReturnPressed: root.flip()

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: root.checked ? Theme.selected : Theme.surface3
        border.width: root.checked ? 0 : 1
        border.color: Theme.lineStrong
        antialiasing: true

        Behavior on color {
            ColorAnimation {
                duration: Theme.fast
            }
        }

        Rectangle {
            width: 12
            height: 12
            radius: 6
            y: 3
            x: root.checked ? parent.width - width - 3 : 3
            color: root.checked ? Theme.surface : Theme.textFaint
            antialiasing: true

            Behavior on x {
                NumberAnimation {
                    duration: Theme.fast
                    easing.type: Theme.easing
                }
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.flip()
    }

    FocusRing {
        radiusBase: 9
    }
}
