import QtQuick
import qs.core
import qs.components

// Keyboard-first vertical menu used by the СОС menu and the session menu:
// rows 34px (icon · label · hint), Up/Down/Home/End move, Enter runs, Esc
// closes, letter keys run the row whose `key` matches.
FocusScope {
    id: root

    // [{glyph, label, hint, key, danger, run}]
    property var items: []
    property int current: 0
    signal chosen(int index)

    implicitWidth: 240
    implicitHeight: col.implicitHeight

    function focusMenu() {
        root.current = 0;
        keys.forceActiveFocus();
    }

    Item {
        id: keys

        focus: true
        Keys.onUpPressed: root.current = (root.current - 1 + root.items.length) % root.items.length
        Keys.onDownPressed: root.current = (root.current + 1) % root.items.length
        Keys.onTabPressed: root.current = (root.current + 1) % root.items.length
        Keys.onBacktabPressed: root.current = (root.current - 1 + root.items.length) % root.items.length
        Keys.onReturnPressed: root.chosen(root.current)
        Keys.onEnterPressed: root.chosen(root.current)
        Keys.onSpacePressed: root.chosen(root.current)
        Keys.onEscapePressed: Ui.hide()
        Keys.onPressed: event => {
            const t = (event.text || "").toLowerCase();
            if (t.length !== 1)
                return;
            for (let i = 0; i < root.items.length; i++) {
                if ((root.items[i].key || "").toLowerCase() === t) {
                    root.current = i;
                    root.chosen(i);
                    event.accepted = true;
                    return;
                }
            }
        }
    }

    Column {
        id: col

        width: parent.width

        Repeater {
            model: root.items

            Rectangle {
                id: row

                required property var modelData
                required property int index

                width: col.width
                height: 34
                radius: 8
                color: row.index === root.current ? Theme.surface3 : "transparent"

                Icon {
                    x: 10
                    anchors.verticalCenter: parent.verticalCenter
                    glyph: row.modelData.glyph || "chevron-right"
                    color: row.modelData.danger ? Theme.bad : (row.index === root.current ? Theme.text : Theme.textDim)
                }

                SText {
                    x: 36
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 36 - hintText.width - 20
                    text: row.modelData.label || ""
                    size: 13
                    elide: Text.ElideRight
                    color: row.modelData.danger ? Theme.bad : Theme.text
                }

                MText {
                    id: hintText

                    anchors.right: parent.right
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: row.modelData.hint || ""
                    size: 11
                    color: Theme.textFaint
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onEntered: root.current = row.index
                    onClicked: root.chosen(row.index)
                }
            }
        }
    }
}
