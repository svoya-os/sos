//@ pragma AppId sos.shell
//@ pragma IconTheme Papirus
//@ pragma Env QS_NO_RELOAD_POPUP=1

// SOS Shell — entry point (`quickshell -p /usr/share/svoya/shell`, started by
// `sos session-start`). Targets Quickshell 0.3.1 on Qt 6.10 and Hyprland 0.53+.
//
// Per screen: wallpaper (background layer) and the bar. Once: the overlay that
// hosts every modal panel, notification toasts, the OSD, the lock screen and
// the POST splash. Keybindings in /usr/share/svoya/hypr/hyprland.conf reach the
// shell through the IPC targets below (`quickshell -p … ipc call <target> <fn>`),
// except Super+J, a global shortcut (svoya:jackson) so the shell sees press and
// release: tap = open/close Jackson, hold = push-to-talk.
//
// Live reload on file changes is off unless SVOYA_SHELL_DEV=1, so a package
// upgrade never reloads a half-written tree.

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import qs.core
import qs.bar
import qs.wallpaper
import qs.panels
import qs.notifications
import qs.lock
import qs.post

ShellRoot {
    id: shell

    settings.watchFiles: Quickshell.env("SVOYA_SHELL_DEV") === "1"

    Variants {
        model: Quickshell.screens

        Background {
            primary: modelData === Quickshell.screens[0]
        }
    }

    Variants {
        model: Quickshell.screens

        Bar {}
    }

    Overlay {}

    Toasts {}

    Osd {}

    Lock {}

    Post {}

    // Jackson's fixed lines (lock screen, Strings.jLocked…) speak in his persona's voice
    Binding {
        target: Strings
        property: "kentVoice"
        value: Jackson.personaId === "kent" && Jackson.humor > 0
    }

    // ---- Super+J: tap toggles the panel, hold talks (when Jackson has a voice) ----------------
    Scope {
        id: ptt

        property bool wasOpen: false
        property bool holding: false

        function press() {
            if (Ui.locked)
                return;
            ptt.wasOpen = Ui.modal === "jackson";
            if (!ptt.wasOpen)
                Ui.show("jackson");
            hold.restart();
        }

        function release() {
            if (hold.running) {
                // a tap: the press already opened the panel; a tap on an open panel closes it
                hold.stop();
                if (ptt.wasOpen)
                    Ui.hide();
                return;
            }
            if (ptt.holding) {
                ptt.holding = false;
                Jackson.listen(false);
            }
        }

        Timer {
            id: hold

            interval: 350
            onTriggered: {
                if (Jackson.voice && !Ui.locked) {
                    ptt.holding = true;
                    Jackson.listen(true);
                }
            }
        }
    }

    GlobalShortcut {
        appid: "svoya"
        name: "jackson"
        description: "Jackson: tap to open, hold to talk"
        onPressed: ptt.press()
        onReleased: ptt.release()
    }

    // ---- IPC (quickshell -p /usr/share/svoya/shell ipc call <target> <function> [args]) ------------
    IpcHandler {
        target: "launcher"

        function toggle(): void {
            if (Ui.modal === "launcher")
                Ui.hide();
            else
                Ui.openLauncher("all", "");
        }
        function open(query: string): void {
            Ui.openLauncher("all", query);
        }
        function settings(): void {
            Ui.openLauncher("settings", "");
        }
        function modules(): void {
            Ui.openLauncher("modules", "");
        }
        function install(): void {
            Ui.openLauncher("install", "");
        }
    }

    IpcHandler {
        target: "jackson"

        function toggle(): void {
            Ui.toggle("jackson");
        }
        function open(): void {
            Ui.show("jackson");
        }
        function ask(text: string): void {
            Actions.askJackson(text);
        }
        function cancel(): void {
            Jackson.cancel();
        }
        function customize(): void {
            Actions.customizeJackson();
        }
        // the microphone button from a key or a script: talk (again: that's it; while he talks: quiet)
        function talk(): void {
            Ui.show("jackson");
            Jackson.talk();
        }
        // for people who bind push-to-talk to another key in user.conf (bind + bindr)
        function press(): void {
            ptt.press();
        }
        function release(): void {
            ptt.release();
        }
    }

    IpcHandler {
        target: "clipboard"

        function toggle(): void {
            Ui.toggle("clipboard");
        }
    }

    IpcHandler {
        target: "screenshot"

        function region(): void {
            Actions.screenshot();
        }
    }

    IpcHandler {
        target: "controlcenter"

        function toggle(): void {
            Ui.toggle("cc");
        }
        function look(): void {
            Actions.openLook();
        }
    }

    IpcHandler {
        target: "session"

        function toggle(): void {
            Ui.toggle("session");
        }
    }

    IpcHandler {
        target: "cheatsheet"

        function toggle(): void {
            Ui.toggle("cheatsheet");
        }
    }

    IpcHandler {
        target: "menu"

        function toggle(): void {
            Ui.toggle("sos");
        }
    }

    IpcHandler {
        target: "lock"

        function lock(): void {
            Actions.lock();
        }
        function isLocked(): bool {
            return Ui.locked;
        }
    }

    IpcHandler {
        target: "layout"

        function toggleTiling(): void {
            Hypr.toggleTiling();
        }
        function apply(preset: string): void {
            if (["clean", "classic", "hacker"].indexOf(preset) >= 0)
                Actions.setLayout(preset);
        }
    }

    IpcHandler {
        target: "system"

        function undo(): void {
            Actions.undo();
        }
        function doctor(): void {
            Actions.doctor();
        }
        function terminal(): void {
            Sys.terminal([]);
        }
        function accessibility(): void {
            Actions.openSetup("accessibility");
        }
        function setup(): void {
            Actions.openSetup("");
        }
    }

    IpcHandler {
        target: "osd"

        function brightness(): void {
            Brightness.refresh(true);
        }
        function volume(): void {
            Ui.showOsd("volume", Audio.volume, Audio.muted);
        }
    }

    IpcHandler {
        target: "notifications"

        function toggleDnd(): void {
            Notifs.toggleDnd();
        }
        function clear(): void {
            Notifs.clearAll();
        }
    }
}
