import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.core
import qs.components

// One layer-shell window hosts every modal surface (Jackson, launcher, control
// center, СОС menu, session, clipboard, shortcuts, about, screenshot actions,
// Jackson's customizer),
// so only one can be open and keyboard focus is exclusive while it is.
// Transparent and matte: no dimming, no blur. A click outside closes; each
// panel handles its own keys (Esc closes). The window lives on Ui.screen and
// stays mapped for the 120 ms close animation.
PanelWindow {
    id: overlay

    readonly property bool bottomBar: Settings.layout === "classic"
    readonly property real barGap: Theme.barHeight + 8

    screen: Ui.screen ? Ui.screen : Hypr.focusedScreen
    visible: Ui.open || closing.running
    anchors.top: true
    anchors.bottom: true
    anchors.left: true
    anchors.right: true
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"

    WlrLayershell.namespace: "svoya-overlay"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: Ui.open ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

    Connections {
        target: Ui

        function onModalChanged() {
            if (!Ui.open)
                closing.restart();
        }
    }

    Timer {
        id: closing

        interval: Theme.fast + 40
    }

    // click outside: close (panels swallow their own clicks)
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        onClicked: Ui.hide()
    }

    // fallback key handling when no panel field has focus
    Item {
        focus: true
        Keys.onEscapePressed: Ui.hide()
    }

    JacksonPanel {
        x: Math.round((overlay.width - width) / 2)
        y: 118
        shown: Ui.modal === "jackson"
    }

    Launcher {
        x: Math.round((overlay.width - width) / 2)
        y: 118
        shown: Ui.modal === "launcher"
    }

    ClipboardPanel {
        x: Math.round((overlay.width - width) / 2)
        y: 118
        shown: Ui.modal === "clipboard"
    }

    CheatSheet {
        x: Math.round((overlay.width - width) / 2)
        y: 118
        shown: Ui.modal === "cheatsheet"
    }

    ShotPanel {
        x: Math.round((overlay.width - width) / 2)
        y: 118
        shown: Ui.modal === "shot"
    }

    SessionMenu {
        x: Math.round((overlay.width - width) / 2)
        y: Math.round((overlay.height - height) / 2 - 60)
        shown: Ui.modal === "session"
    }

    About {
        x: Math.round((overlay.width - width) / 2)
        y: Math.round((overlay.height - height) / 2 - 60)
        shown: Ui.modal === "about"
    }

    JacksonCustomizer {
        x: Math.round((overlay.width - width) / 2)
        y: Math.max(48, Math.round((overlay.height - height) / 2))
        shown: Ui.modal === "customizer"
    }

    ControlCenter {
        x: overlay.width - width - 8
        y: overlay.bottomBar ? overlay.height - height - overlay.barGap : overlay.barGap
        maxHeight: overlay.height - overlay.barGap - 16
        shown: Ui.modal === "cc"
    }

    SosMenu {
        x: 12
        y: overlay.bottomBar ? overlay.height - height - Theme.barHeight - 6 : Theme.barHeight + 6
        shown: Ui.modal === "sos"
    }
}
