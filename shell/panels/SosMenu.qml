import QtQuick
import qs.core
import qs.components

// СОС menu (click on the Morse mark): About · Settings · Modules · Doctor · Session.
PanelFrame {
    id: root

    width: 248
    implicitHeight: col.implicitHeight + 16
    radius: 12
    highlight: false

    onShownChanged: {
        if (root.shown)
            Qt.callLater(menu.focusMenu);
    }

    Column {
        id: col

        x: 8
        y: 8
        width: parent.width - 16
        spacing: 4

        Row {
            x: 10
            height: 30
            spacing: 10

            MorseMark {
                anchors.verticalCenter: parent.verticalCenter
            }
            MText {
                anchors.verticalCenter: parent.verticalCenter
                text: Strings.osName + " " + Sys.osVersion
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
            items: [
                { glyph: "info", label: Strings.about, key: "a", run: () => Ui.show("about") },
                { glyph: "settings", label: Strings.settings, key: "s", run: () => Ui.openLauncher("settings", "") },
                { glyph: "package", label: Strings.modulesTitle, key: "m", run: () => Ui.openLauncher("modules", "") },
                { glyph: "stethoscope", label: Strings.doctor, hint: "Super Esc", key: "d", run: () => { Ui.hide(); Actions.doctor(); } },
                { glyph: "power", label: Strings.session, key: "e", run: () => Ui.show("session") }
            ]
            onChosen: index => items[index].run()
        }
    }
}
