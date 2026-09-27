import QtQuick
import qs.core
import qs.components
import "Emoji.js" as Emoji

// Emoji (Super+. or Super+; — as on Windows): type a word in Russian or English, Enter (or a click)
// puts the emoji into the window you were in (wtype) and on the clipboard. The ones you used come
// first. Tab / ↑ ↓ move, Esc closes.
PanelFrame {
    id: root

    property string query: ""
    property int selected: 0
    readonly property int columns: 12
    readonly property var found: {
        const hits = Emoji.search(root.query);
        if (root.query.trim().length > 0)
            return hits;
        const recent = (Settings.recentEmoji || []).filter(e => typeof e === "string");
        const first = recent.map(e => Emoji.list.find(x => x[0] === e) || [e, "", ""]);
        return first.concat(hits.filter(x => recent.indexOf(x[0]) < 0));
    }

    function pick(i) {
        const e = root.found[i];
        if (!e)
            return;
        const recent = [e[0]].concat((Settings.recentEmoji || []).filter(x => x !== e[0])).slice(0, 24);
        Settings.recentEmoji = recent;
        Ui.hide();
        // after the overlay lets go of the keyboard, type it where the cursor was
        Sys.sh('printf %s "$1" | wl-copy; command -v wtype >/dev/null || exit 3; sleep 0.25; exec wtype -- "$1"', [e[0]], function (code) {
            if (code === 3)
                Notifs.shellToast(Strings.emojiCopied(e[0]), Strings.emojiPaste, "face-slightly-smiling");
        });
    }

    function move(d) {
        const n = root.found.length;
        if (n > 0)
            root.selected = Math.max(0, Math.min(n - 1, root.selected + d));
    }

    width: 12 * 44 + 32
    implicitHeight: col.implicitHeight

    onQueryChanged: root.selected = 0
    onShownChanged: {
        if (root.shown) {
            field.text = "";
            Qt.callLater(field.focusInput);
        }
    }

    Column {
        id: col

        width: parent.width

        Item {
            width: parent.width
            height: 27.6 + 16 + 18

            TextField {
                id: field

                x: 18
                y: 16
                width: parent.width - 36
                big: true
                placeholder: Strings.emojiPlaceholder
                onTextChanged: root.query = text
                onAccepted: root.pick(root.selected)
                onEscapePressed: Ui.hide()
                onTabPressed: root.move(1)
                onUpPressed: root.move(-root.columns)
                onDownPressed: root.move(root.columns)
            }
        }

        Divider {
            width: parent.width
        }

        MText {
            x: 18
            topPadding: 20
            bottomPadding: 20
            visible: root.found.length === 0
            text: Strings.emojiNothing
            size: 12.5
            color: Theme.textFaint
        }

        Flickable {
            x: 16
            width: parent.width - 32
            height: Math.min(grid.implicitHeight, 6 * 44) + (root.found.length > 0 ? 16 : 0)
            topMargin: 8
            bottomMargin: 8
            contentHeight: grid.implicitHeight
            clip: true
            visible: root.found.length > 0
            boundsBehavior: Flickable.StopAtBounds

            Grid {
                id: grid

                columns: root.columns
                spacing: 0

                Repeater {
                    model: root.found

                    Rectangle {
                        id: cell

                        required property var modelData
                        required property int index
                        readonly property bool current: cell.index === root.selected

                        width: 44
                        height: 44
                        radius: 10
                        color: cell.current ? Theme.surface3 : (cellMouse.containsMouse ? Theme.surface : "transparent")
                        border.width: cell.current ? 1 : 0
                        border.color: Theme.lineStrong

                        Text {
                            anchors.centerIn: parent
                            text: cell.modelData[0]
                            font.family: "Noto Color Emoji"
                            font.pixelSize: 24
                        }

                        MouseArea {
                            id: cellMouse

                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.pick(cell.index)
                        }
                    }
                }
            }
        }

        Divider {
            width: parent.width
        }

        MText {
            x: 18
            width: parent.width - 36
            topPadding: 10
            bottomPadding: 12
            text: root.found[root.selected] ? root.found[root.selected][0] + "  " + (Strings.lang === "ru" ? root.found[root.selected][2] : root.found[root.selected][1]) : Strings.emojiHint
            size: 11
            color: Theme.textFaint
            elide: Text.ElideRight
        }
    }
}
