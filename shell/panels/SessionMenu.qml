import QtQuick
import qs.core
import qs.components

// Session menu: lock · log out · suspend · restart · shut down. Everything but
// lock asks once more: the row turns into «Нажми ещё раз, чтобы подтвердить»
// (warn/bad) for 8 s; a second Enter or click runs it, Esc cancels.
PanelFrame {
    id: root

    property int pending: -1

    readonly property var base: [
        { glyph: "lock", label: Strings.lock, hint: "L", key: "l", confirm: false, run: () => { Ui.hide(); Actions.lock(); } },
        { glyph: "log-out", label: Strings.logout, hint: "E", key: "e", confirm: true, run: () => { Ui.hide(); Actions.logout(); } },
        { glyph: "moon", label: Strings.suspend, hint: "S", key: "s", confirm: true, run: () => { Ui.hide(); Actions.suspend(); } },
        { glyph: "rotate-ccw", label: Strings.reboot, hint: "R", key: "r", confirm: true, run: () => { Ui.hide(); Actions.reboot(); } },
        { glyph: "power", label: Strings.poweroff, hint: "P", key: "p", confirm: true, run: () => { Ui.hide(); Actions.poweroff(); } }
    ]
    readonly property var items: root.base.map((it, i) => i === root.pending ? Object.assign({}, it, { label: Strings.confirmAgain, danger: true }) : it)

    function choose(i) {
        const it = root.base[i];
        if (it.confirm && root.pending !== i) {
            root.pending = i;
            expire.restart();
            return;
        }
        root.pending = -1;
        it.run();
    }

    width: 300
    implicitHeight: col.implicitHeight + 16
    radius: 12

    onShownChanged: {
        root.pending = -1;
        if (root.shown)
            Qt.callLater(menu.focusMenu);
    }

    Timer {
        id: expire

        interval: 8000
        onTriggered: root.pending = -1
    }

    Column {
        id: col

        x: 8
        y: 8
        width: parent.width - 16
        spacing: 4

        Item {
            width: parent.width
            height: 30

            Caption {
                x: 10
                anchors.verticalCenter: parent.verticalCenter
                text: Strings.session
            }

            MText {
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                text: Sys.user
                size: 11
                color: Theme.textFaint
            }
        }

        Divider {
            width: parent.width
        }

        MenuList {
            id: menu

            width: parent.width
            items: root.items
            onChosen: index => root.choose(index)
        }
    }
}
