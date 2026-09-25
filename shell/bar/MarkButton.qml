import QtQuick
import qs.core
import qs.components

// The Morse mark (··· ——— ···); the ——— light up in accent while Jackson listens, thinks,
// works or speaks (DESIGN §5). Opens the СОС menu.
// Box: 22px high, padding 0 8, radius 6, hover surface3; the mark's advance
// is 75px as in the mockup's SVG (last symbol + trailing letter space).
Rectangle {
    id: root

    property var screen: null

    implicitWidth: 8 + 75 + 8
    implicitHeight: 22
    radius: Theme.radiusSmall
    color: mouse.containsMouse || Ui.modal === "sos" ? Theme.surface3 : "transparent"

    Accessible.role: Accessible.Button
    Accessible.name: Strings.sosMenu

    MorseMark {
        x: 8
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.text
        lit: Jackson.signalLive
    }

    MouseArea {
        id: mouse

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: Ui.toggle("sos", root.screen)
    }
}
