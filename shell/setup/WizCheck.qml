import QtQuick
import qs.core
import qs.components

// Selection mark (setup-*.html .sel / .mrow .rd). `radio`: a 16px ring that
// fills with a 5px `text` border when checked. Otherwise an 18px circle
// (1.5px lineStrong) that becomes a `text` disc with a surface-colored check. Neutral: the
// accent never marks a selection (DESIGN §11).
Item {
    id: root

    property bool checked: false
    property bool radio: false

    implicitWidth: root.radio ? 16 : 18
    implicitHeight: root.radio ? 16 : 18

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: root.checked && !root.radio ? Theme.selected : "transparent"
        border.width: root.checked ? (root.radio ? 5 : 0) : 1.5
        border.color: root.checked ? Theme.selected : Theme.lineStrong
        antialiasing: true
    }

    Icon {
        anchors.centerIn: parent
        visible: root.checked && !root.radio
        glyph: "check"
        size: 11
        stroke: 2.8
        color: Theme.surface
    }
}
