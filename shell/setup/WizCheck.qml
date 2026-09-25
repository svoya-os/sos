import QtQuick
import qs.core
import qs.components

// Selection mark (setup-*.html .sel / .mrow .rd). `radio`: a 16px ring that
// fills with a 5px accent border when checked. Otherwise an 18px circle
// (1.5px lineStrong) that becomes an accent disc with an accentInk check.
Item {
    id: root

    property bool checked: false
    property bool radio: false

    implicitWidth: root.radio ? 16 : 18
    implicitHeight: root.radio ? 16 : 18

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: root.checked && !root.radio ? Theme.accent : "transparent"
        border.width: root.checked ? (root.radio ? 5 : 0) : 1.5
        border.color: root.checked ? Theme.accent : Theme.lineStrong
        antialiasing: true
    }

    Icon {
        anchors.centerIn: parent
        visible: root.checked && !root.radio
        glyph: "check"
        size: 11
        stroke: 2.8
        color: Theme.accentInk
    }
}
