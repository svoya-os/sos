import QtQuick
import qs.core
import qs.components
import "Fuzzy.js" as Fuzzy

// Clipboard history (Super+V) over cliphist: search, Enter copies the entry
// back (`cliphist decode | wl-copy`), Delete forgets it, Esc closes.
PanelFrame {
    id: root

    property var entries: []       // [{line, id, text, image}]
    property string query: ""
    property int selected: 0
    property bool loading: false

    readonly property var visibleEntries: root.query.trim().length === 0 ? root.entries : root.entries.filter(e => Fuzzy.score(root.query, e.text) > 60)

    function load() {
        if (!Sys.has["cliphist"]) {
            root.entries = [];
            return;
        }
        root.loading = true;
        Sys.run(["cliphist", "list"], function (code, out) {
            root.loading = false;
            const list = [];
            const lines = out.split("\n");
            for (let i = 0; i < lines.length && list.length < 300; i++) {
                const line = lines[i];
                const tab = line.indexOf("\t");
                if (tab < 0)
                    continue;
                const text = line.slice(tab + 1);
                const img = /^\[\[ binary data (.+) \]\]$/.exec(text);
                list.push({ line: line, id: line.slice(0, tab), text: img ? Strings.image + " · " + img[1] : text, image: !!img });
            }
            root.entries = list;
            root.selected = 0;
        });
    }

    function copy(i) {
        const e = root.visibleEntries[i];
        if (!e)
            return;
        Sys.sh("cliphist decode | wl-copy", [], function (code) {
            if (code === 0)
                Notifs.shellToast(Strings.copied, e.image ? "" : e.text.slice(0, 80), "copy");
        }, e.line + "\n");
        Ui.hide();
    }

    function forget(i) {
        const e = root.visibleEntries[i];
        if (!e)
            return;
        Sys.run(["cliphist", "delete"], function () {
            root.load();
        }, e.line + "\n");
    }

    function move(d) {
        const n = root.visibleEntries.length;
        if (n > 0) {
            root.selected = (root.selected + d + n) % n;
            list.positionViewAtIndex(root.selected, ListView.Contain);
        }
    }

    width: 640
    implicitHeight: col.implicitHeight

    onQueryChanged: root.selected = 0
    onShownChanged: {
        if (root.shown) {
            field.text = "";
            root.load();
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
                placeholder: Strings.clipboardPlaceholder
                onTextChanged: root.query = text
                onAccepted: root.copy(root.selected)
                onEscapePressed: Ui.hide()
                onUpPressed: root.move(-1)
                onDownPressed: root.move(1)
                onDeletePressed: root.forget(root.selected)
            }
        }

        Divider {
            width: parent.width
        }

        ListView {
            id: list

            x: 8
            width: parent.width - 16
            height: Math.min(contentHeight, 10 * 40) + (count > 0 ? 16 : 0)
            topMargin: 8
            bottomMargin: 8
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: root.visibleEntries
            visible: count > 0

            delegate: ListRow {
                required property var modelData
                required property int index

                width: list.width
                glyph: modelData.image ? "image" : "clipboard"
                title: modelData.text.replace(/\s+/g, " ")
                selected: index === root.selected
                hint: "Enter"
                onActivated: root.copy(index)
                onHovered: root.selected = index
            }
        }

        SText {
            x: 30
            height: 52
            visible: root.visibleEntries.length === 0 && !root.loading
            text: Sys.has["cliphist"] ? Strings.clipboardEmpty : Strings.clipboardMissing
            color: Theme.textDim
        }

        Item {
            width: parent.width
            height: 40

            Divider {
                width: parent.width
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                spacing: 14

                Row {
                    spacing: 6
                    Keycap {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Enter"
                    }
                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Strings.copy.toLowerCase()
                        size: 11
                        color: Theme.textFaint
                    }
                }
                Row {
                    spacing: 6
                    Keycap {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Del"
                    }
                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Strings.deleteKey
                        size: 11
                        color: Theme.textFaint
                    }
                }
                Row {
                    spacing: 6
                    Keycap {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Esc"
                    }
                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Strings.close
                        size: 11
                        color: Theme.textFaint
                    }
                }
            }
        }
    }
}
