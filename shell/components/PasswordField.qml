import QtQuick
import qs.core

// The 320×40 password field of the lock screen and greeter
// (components.css .field / .pw): surface2, 1px lineStrong, radius 9; focused =
// accent border + a 3px accentSoft ring. Typed characters are 7px dots (gap 6)
// followed by the 2px accent caret; a 30×30 "go" button sits on the right.
// The TextInput itself stays invisible; it only holds the text and the focus.
FocusScope {
    id: root

    property alias text: input.text
    property string placeholder: Strings.passwordPlaceholder
    property bool busy: false
    property bool error: false
    property bool inputEnabled: true
    property bool masked: true           // false: plain text (the greeter's user-name prompt)

    signal submit(string text)

    implicitWidth: 320
    implicitHeight: 40

    function focusField() {
        input.forceActiveFocus();
    }

    function clear() {
        input.text = "";
    }

    function send() {
        if (input.text.length > 0 && !root.busy)
            root.submit(input.text);
    }

    readonly property bool focused: input.activeFocus
    readonly property color ringColor: root.error ? Theme.bad : Theme.accent

    Rectangle {
        anchors.fill: frame
        anchors.margins: -3
        radius: 12
        visible: root.focused || root.error
        color: root.error ? Theme.alpha(Theme.bad, 0.16) : Theme.accentSoft
        antialiasing: true
    }

    Rectangle {
        id: frame

        anchors.fill: parent
        radius: 9
        color: Theme.surface2
        border.width: 1
        border.color: root.focused || root.error ? root.ringColor : Theme.lineStrong
        opacity: root.inputEnabled ? 1 : 0.6
        antialiasing: true
    }

    TextInput {
        id: input

        x: 14
        width: root.width - 14 - 46
        anchors.verticalCenter: parent.verticalCenter
        focus: true
        enabled: root.inputEnabled
        readOnly: root.busy
        echoMode: root.masked ? TextInput.Password : TextInput.Normal
        passwordMaskDelay: 0
        color: root.masked ? "transparent" : Theme.text
        selectionColor: root.masked ? "transparent" : Theme.accentSoft
        selectedTextColor: Theme.text
        font.family: Theme.sans
        font.pixelSize: 14
        font.features: Theme.sansFeatures
        clip: true
        cursorDelegate: Rectangle {
            // masked input draws its own caret after the dots
            width: 2
            color: Theme.accent
            visible: !root.masked && input.activeFocus
        }
        Keys.onReturnPressed: root.send()
        Keys.onEnterPressed: root.send()
    }

    Row {
        id: dots

        x: 14
        anchors.verticalCenter: parent.verticalCenter
        spacing: 6
        visible: root.masked

        Repeater {
            model: root.masked ? Math.min(input.length, 30) : 0

            Rectangle {
                width: 7
                height: 7
                radius: 3.5
                color: root.busy ? Theme.textDim : Theme.text
                antialiasing: true
            }
        }
    }

    // caret: after the dots (10px gap + 1), or at the start before the placeholder
    Rectangle {
        visible: root.masked && root.focused && !root.busy
        x: input.length > 0 ? 14 + dots.width + 11 : 13
        anchors.verticalCenter: parent.verticalCenter
        width: 2
        height: 18
        radius: 1
        color: Theme.accent
    }

    SText {
        x: 14 + (root.masked && root.focused ? 2 : 0)
        anchors.verticalCenter: parent.verticalCenter
        visible: input.length === 0
        text: root.busy ? Strings.checking : root.placeholder
        size: 14
        color: Theme.textFaint
    }

    // go: 30×30, radius 7, surface3, 5px from the right edge
    Rectangle {
        id: go

        anchors.right: parent.right
        anchors.rightMargin: 6
        anchors.verticalCenter: parent.verticalCenter
        width: 30
        height: 30
        radius: 7
        color: goMouse.containsMouse ? Theme.lineStrong : Theme.surface3
        antialiasing: true

        Icon {
            anchors.centerIn: parent
            glyph: root.busy ? "clock" : "arrow-right"
            size: 15
            stroke: 1.8
            color: goMouse.containsMouse || input.length > 0 ? Theme.text : Theme.textDim
        }

        MouseArea {
            id: goMouse

            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.send()
        }
    }
}
