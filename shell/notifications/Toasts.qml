import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.Notifications
import qs.core
import qs.components

// Toasts (DESIGN.md §5): 330px, top-right (right 18, top 44 = bar + 14),
// radius 12, surface2, 1px line, soft shadow. Newest at the bottom of the
// stack, at most four. Normal toasts leave after their timeout (6 s default,
// paused while hovered); critical ones stay until dismissed. The window is
// click-through outside the toasts and never takes keyboard focus.
PanelWindow {
    id: win

    readonly property real pad: 60     // room for the shadow around the stack
    readonly property bool bottomBar: Settings.layout === "classic"

    screen: Hypr.focusedScreen
    visible: Notifs.toasts.length > 0 && !Ui.locked
    anchors.top: true
    anchors.right: true
    margins.top: win.bottomBar ? 0 : Theme.barHeight
    exclusionMode: ExclusionMode.Ignore
    implicitWidth: 330 + 18 + win.pad
    implicitHeight: stack.implicitHeight + 14 + win.pad
    color: "transparent"
    mask: Region {
        item: stack
    }

    WlrLayershell.namespace: "svoya-toasts"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

    Column {
        id: stack

        x: win.pad
        y: 14
        width: 330
        spacing: 10

        Repeater {
            model: Notifs.toasts

            Item {
                id: toast

                required property var modelData
                readonly property bool critical: modelData.urgency === NotificationUrgency.Critical
                readonly property real timeout: {
                    const n = modelData.n;
                    // already milliseconds: Quickshell stores the D-Bus expire_timeout
                    // as-is (notification.cpp:115; its "seconds" doc comment is wrong)
                    const t = n && n.expireTimeout > 0 ? n.expireTimeout : 6000;
                    return Math.max(3000, Math.min(20000, t));
                }

                width: 330
                height: card.implicitHeight
                opacity: 0
                Component.onCompleted: opacity = 1

                Behavior on opacity {
                    NumberAnimation {
                        duration: Theme.base
                        easing.type: Theme.easing
                    }
                }

                RectangularShadow {
                    anchors.fill: parent
                    radius: Theme.radiusToast
                    offset: Qt.vector2d(0, 28)
                    blur: 60
                    spread: -24
                    color: Theme.alpha(Theme.shadow, Theme.shadow.a * 0.85)
                }

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusToast
                    color: Theme.surface2
                    border.width: 1
                    border.color: toast.critical ? Theme.bad : Theme.line
                }

                NotificationCard {
                    id: card

                    width: parent.width
                    entry: toast.modelData
                    toast: true
                    onCloseRequested: Notifs.removeToast(toast.modelData.key)
                }

                // click the body: default action if any, else just dismiss the toast
                TapHandler {
                    onTapped: {
                        const n = toast.modelData.n;
                        if (n && n.actions && n.actions.length > 0) {
                            for (let i = 0; i < n.actions.length; i++) {
                                if (n.actions[i].identifier === "default") {
                                    n.actions[i].invoke();
                                    break;
                                }
                            }
                        } else if (toast.modelData.jackson) {
                            Ui.show("jackson");
                        }
                        Notifs.removeToast(toast.modelData.key);
                    }
                }

                HoverHandler {
                    id: hover
                }

                Timer {
                    running: !toast.critical && !hover.hovered
                    interval: toast.timeout
                    onTriggered: Notifs.removeToast(toast.modelData.key)
                }
            }
        }
    }
}
