import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import Quickshell.Widgets
import qs.core
import qs.components
import "Fuzzy.js" as Fuzzy

// Every window at a glance (Super+Tab, three fingers up — Windows' Task View): live pictures of
// the windows of every desktop, the desktops as chips above. Typing filters by title and app;
// Tab / ↑ ↓ move, Enter or a click brings the window, a middle click closes it, Esc closes this.
// Held Alt+Tab shows the same pictures as the switcher (core/WindowSwitch.qml): the most recently
// used first, no search; letting go of Alt goes to the chosen one, Esc cancels.
PanelFrame {
    id: root

    property real maxWidth: 1200
    property string query: ""
    property int selected: 0

    readonly property bool switching: WindowSwitch.active
    readonly property int current: root.switching ? WindowSwitch.index : root.selected

    readonly property int columns: Math.max(2, Math.min(4, Math.floor((root.width - 32 + 12) / (256 + 12))))
    readonly property real tileWidth: Math.floor((root.width - 32 - (root.columns - 1) * 12) / root.columns)
    readonly property real thumbHeight: Math.round(root.tileWidth * 0.58)

    // windows of the numbered desktops (hidden ones — Super+D — live on a special workspace)
    readonly property var windows: {
        if (root.switching)
            return WindowSwitch.windows;
        const all = Hyprland.toplevels.values.filter(t => t && t.workspace && t.workspace.id > 0);
        all.sort((a, b) => a.workspace.id - b.workspace.id);
        return all;
    }
    readonly property var shownWindows: root.switching || root.query.trim().length === 0 ? root.windows : root.windows.filter(t => Fuzzy.score(root.query, root.label(t)) > 60)
    readonly property var desktops: Hyprland.workspaces.values.filter(w => w && w.id > 0).sort((a, b) => a.id - b.id)

    function appOf(t) {
        const ipc = t && t.lastIpcObject ? t.lastIpcObject : {};
        return (t && t.wayland && t.wayland.appId) || ipc["class"] || "";
    }

    function label(t) {
        const app = root.appOf(t);
        const entry = app ? DesktopEntries.heuristicLookup(app) : null;
        return (t.title || "") + " " + (entry ? entry.name : app);
    }

    function bring(i) {
        if (root.switching) {
            WindowSwitch.commit(i);
            return;
        }
        const t = root.shownWindows[i];
        if (!t)
            return;
        Ui.hide();
        WindowSwitch.bring(t);
    }

    function move(d) {
        const n = root.shownWindows.length;
        if (root.switching)
            WindowSwitch.step(d);
        else if (n > 0)
            root.selected = (root.selected + d + n) % n;
    }

    width: Math.min(root.maxWidth, 1200)
    implicitHeight: col.implicitHeight

    onQueryChanged: root.selected = 0
    onShownChanged: {
        if (root.shown) {
            field.text = "";
            Hyprland.refreshToplevels();
            Hyprland.refreshWorkspaces();
            // start on the window after the active one, as Alt+Tab does
            const active = root.windows.findIndex(t => t.activated);
            root.selected = root.windows.length > 1 && active >= 0 ? (active + 1) % root.windows.length : 0;
            if (root.switching)
                Qt.callLater(() => switchKeys.forceActiveFocus());
            else
                Qt.callLater(field.focusInput);
        } else if (root.switching) {
            WindowSwitch.cancel();          // closed another way (a click outside) while Alt is held
        }
    }

    // the keys while Alt+Tab is held (Tab itself arrives through the global shortcut)
    Item {
        id: switchKeys

        Keys.onEscapePressed: WindowSwitch.cancel()
        Keys.onReturnPressed: WindowSwitch.commit()
        Keys.onEnterPressed: WindowSwitch.commit()
        Keys.onLeftPressed: WindowSwitch.step(-1)
        Keys.onRightPressed: WindowSwitch.step(1)
        Keys.onUpPressed: WindowSwitch.step(-root.columns)
        Keys.onDownPressed: WindowSwitch.step(root.columns)
    }

    Column {
        id: col

        width: parent.width

        Item {
            width: parent.width
            height: 27.6 + 16 + 18
            visible: !root.switching

            TextField {
                id: field

                x: 18
                y: 16
                width: parent.width - 36
                big: true
                placeholder: Strings.overviewPlaceholder
                onTextChanged: root.query = text
                onAccepted: root.bring(root.selected)
                onEscapePressed: Ui.hide()
                onTabPressed: root.move(1)
                onUpPressed: root.move(-root.columns)
                onDownPressed: root.move(root.columns)
            }
        }

        Divider {
            width: parent.width
            visible: !root.switching
        }

        // the desktops: a click goes there
        Flow {
            x: 16
            width: parent.width - 32
            topPadding: 12
            spacing: 6
            visible: !root.switching

            Repeater {
                model: root.desktops

                Rectangle {
                    id: chip

                    required property var modelData

                    width: chipText.implicitWidth + 22
                    height: 26
                    radius: 13
                    color: chip.modelData.focused ? Theme.surface3 : (chipMouse.containsMouse ? Theme.surface2 : "transparent")
                    border.width: 1
                    border.color: chip.modelData.focused ? Theme.lineStrong : Theme.line

                    MText {
                        id: chipText

                        anchors.centerIn: parent
                        text: Strings.workspace + " " + chip.modelData.id + " · " + chip.modelData.toplevels.values.length
                        size: 11
                        color: chip.modelData.focused ? Theme.text : Theme.textDim
                    }

                    MouseArea {
                        id: chipMouse

                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            Ui.hide();
                            chip.modelData.activate();
                        }
                    }
                }
            }
        }

        MText {
            x: 18
            width: parent.width - 36
            topPadding: 24
            bottomPadding: 24
            visible: root.shownWindows.length === 0
            text: root.windows.length === 0 ? Strings.overviewEmpty : Strings.overviewNothing
            size: 12.5
            color: Theme.textFaint
        }

        Grid {
            id: grid

            x: 16
            topPadding: 12
            bottomPadding: 16
            columns: root.columns
            columnSpacing: 12
            rowSpacing: 12
            visible: root.shownWindows.length > 0

            Repeater {
                model: root.shownWindows

                Rectangle {
                    id: tile

                    required property var modelData
                    required property int index
                    readonly property bool current: tile.index === root.current
                    readonly property var entry: DesktopEntries.heuristicLookup(root.appOf(tile.modelData))

                    width: root.tileWidth
                    height: root.thumbHeight + 42
                    radius: 12
                    color: tile.current ? Theme.surface3 : (tileMouse.containsMouse ? Theme.surface : "transparent")
                    border.width: tile.current ? 1.5 : 1
                    border.color: tile.current ? Theme.selected : Theme.line

                    Rectangle {
                        id: frame

                        x: 8
                        y: 8
                        width: parent.width - 16
                        height: root.thumbHeight
                        radius: 8
                        color: Theme.surface
                        clip: true

                        ScreencopyView {
                            id: view

                            readonly property real ratio: view.sourceSize.width > 0 && view.sourceSize.height > 0 ? view.sourceSize.width / view.sourceSize.height : 1.6

                            anchors.centerIn: parent
                            width: Math.min(frame.width, frame.height * view.ratio)
                            height: Math.min(frame.height, frame.width / view.ratio)
                            captureSource: root.shown ? tile.modelData.wayland : null
                            live: false
                            constraintSize: Qt.size(frame.width * 2, frame.height * 2)
                        }

                        // before the picture comes (or when a window cannot be captured): its icon
                        IconImage {
                            anchors.centerIn: parent
                            implicitSize: 40
                            visible: !view.hasContent
                            source: tile.entry && tile.entry.icon ? Quickshell.iconPath(tile.entry.icon, true) : ""
                        }
                    }

                    Row {
                        x: 10
                        y: root.thumbHeight + 16
                        width: parent.width - 20
                        spacing: 7

                        IconImage {
                            anchors.verticalCenter: parent.verticalCenter
                            implicitSize: 14
                            source: tile.entry && tile.entry.icon ? Quickshell.iconPath(tile.entry.icon, true) : ""
                            visible: source.toString().length > 0
                        }

                        SText {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 21 - wsText.implicitWidth - 7
                            text: tile.modelData.title || (tile.entry ? tile.entry.name : root.appOf(tile.modelData))
                            size: 12
                            color: tile.current ? Theme.text : Theme.textDim
                            elide: Text.ElideRight
                        }

                        MText {
                            id: wsText

                            anchors.verticalCenter: parent.verticalCenter
                            text: String(tile.modelData.workspace ? tile.modelData.workspace.id : "")
                            size: 10.5
                            color: Theme.textFaint
                        }
                    }

                    MouseArea {
                        id: tileMouse

                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                        cursorShape: Qt.PointingHandCursor
                        onClicked: mouse => {
                            if (mouse.button === Qt.MiddleButton && tile.modelData.wayland && !root.switching)
                                tile.modelData.wayland.close();
                            else
                                root.bring(tile.index);
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
            topPadding: 10
            bottomPadding: 12
            text: root.switching ? Strings.switchHint : Strings.overviewHint
            size: 11
            color: Theme.textFaint
        }
    }
}
