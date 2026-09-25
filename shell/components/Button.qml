import QtQuick
import qs.core

// Buttons from the mockup: 34px, radius 9, Plex Sans 13/500 (`small` 26px;
// `large` 40px, 18px padding, 13.5px — the wizard footer).
// primary = accent fill + accentInk; otherwise 1px lineStrong outline on
// `fill` (transparent by default).
// `hint` renders a mono key hint («Enter») at 60% opacity. Keyboard: Tab to
// focus, Enter/Space to press (2px accent focus ring).
Rectangle {
    id: root

    property string text: ""
    property string hint: ""
    property string glyph: ""
    property bool primary: false
    property bool small: false
    property bool danger: false
    property bool enabledState: true
    property bool large: false
    property color fill: "transparent"
    property color textColor: root.primary ? Theme.accentInk : (root.danger ? Theme.bad : Theme.text)

    signal clicked

    implicitWidth: row.implicitWidth + (root.small ? 20 : (root.large ? 36 : 28))
    implicitHeight: root.small ? 26 : (root.large ? 40 : 34)
    radius: root.small ? 7 : Theme.radiusButton
    color: root.primary ? (mouse.containsMouse || mouse.pressed ? Theme.accentStrong : Theme.accent) : (mouse.containsMouse ? Theme.surface3 : root.fill)
    border.width: root.primary ? 0 : 1
    border.color: Theme.lineStrong
    opacity: root.enabledState ? 1 : 0.45
    antialiasing: true
    activeFocusOnTab: true

    Keys.onReturnPressed: event => {
        root.clicked();
        event.accepted = true;
    }
    Keys.onEnterPressed: event => {
        root.clicked();
        event.accepted = true;
    }
    Keys.onSpacePressed: event => {
        root.clicked();
        event.accepted = true;
    }

    Behavior on color {
        ColorAnimation {
            duration: Theme.fast
        }
    }

    Row {
        id: row

        anchors.centerIn: parent
        spacing: 8

        Icon {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.glyph.length > 0
            glyph: root.glyph.length > 0 ? root.glyph : "check"
            size: root.small ? 13 : 15
            color: root.textColor
        }

        SText {
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            size: root.small ? 12 : (root.large ? 13.5 : 13)
            font.weight: Font.Medium
            color: root.textColor
        }

        MText {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.hint.length > 0
            text: root.hint
            size: 11
            opacity: root.large ? 0.62 : 0.6
            color: root.primary ? Theme.accentInk : Theme.textDim
        }
    }

    MouseArea {
        id: mouse

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        enabled: root.enabledState
        onClicked: root.clicked()
    }

    FocusRing {
        radiusBase: root.radius
    }
}
