import QtQuick
import qs.core

// Single-line input with the signature 2px accent caret. `big` = the 20px
// title style (Jackson, launcher); otherwise 14px body text.
Item {
    id: root

    property alias text: input.text
    property alias input: input
    property string placeholder: ""
    property bool big: false
    property bool password: false
    property real size: root.big ? Theme.fsTitle : Theme.fsBody
    property bool mono: false          // Plex Mono (hex values, paths)

    signal accepted
    signal escape
    signal upPressed
    signal downPressed
    signal tabPressed
    signal deletePressed

    implicitHeight: Math.ceil(root.size * 1.38)
    implicitWidth: 200

    function focusInput() {
        input.forceActiveFocus();
    }

    TextInput {
        id: input

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.text
        selectionColor: Theme.accentSoft
        selectedTextColor: Theme.text
        font.family: root.mono ? Theme.mono : Theme.sans
        font.pixelSize: root.size
        font.features: root.mono ? Theme.monoFeatures : Theme.sansFeatures
        font.letterSpacing: root.size >= 20 ? -0.005 * root.size : 0
        echoMode: root.password ? TextInput.Password : TextInput.Normal
        passwordCharacter: "•"
        clip: true
        focus: true
        selectByMouse: true
        cursorDelegate: Rectangle {
            width: 2
            color: Theme.accent
            visible: input.activeFocus
        }
        Keys.onReturnPressed: root.accepted()
        Keys.onEnterPressed: root.accepted()
        Keys.onEscapePressed: root.escape()
        Keys.onUpPressed: root.upPressed()
        Keys.onDownPressed: root.downPressed()
        Keys.onTabPressed: root.tabPressed()
        Keys.onDeletePressed: event => {
            // Delete at the end of the text acts on the selected list row
            if (input.cursorPosition >= input.length) {
                root.deletePressed();
                event.accepted = true;
            } else {
                event.accepted = false;
            }
        }
    }

    SText {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        visible: input.text.length === 0
        text: root.placeholder
        size: root.size
        color: Theme.textFaint
        elide: Text.ElideRight
    }
}
