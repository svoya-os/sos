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

    // Alt+Tab as on Windows (core/WindowSwitch.qml): Tab with Alt held picks, letting go of Alt goes
    GlobalShortcut {
        appid: "svoya"
        name: "alttab"
        description: "Alt+Tab: the window used before"
        onPressed: WindowSwitch.tab()
    }

    GlobalShortcut {
        appid: "svoya"
        name: "alt"
        description: "Alt let go: ends Alt+Tab"
        onReleased: WindowSwitch.commit()
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
            if (Ui.locked)
                return;
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

    // SOS ASCII outside the shell (Theme.symbolsFor): the folders (the GTK icon theme SOS-Symbols-*)
    // and the cursor (sos-symbols, for Hyprland and GTK) while the symbol layer covers them; put back
    // when it stops, but only while they are still ours (an icon theme or a cursor you chose yourself
    // stays). `sos theme apply` picks the same icon theme (cli/svoya_cli/theme/symbols.py).
    QtObject {
        id: systemLook

        readonly property string icons: Theme.symbolsFor("folders") ? (Theme.isDark ? "SOS-Symbols-Dark" : "SOS-Symbols-Light") : ""
        readonly property string plainIcons: Theme.isDark ? "Papirus-Dark" : "Papirus-Light"
        readonly property string cursor: Theme.symbolsFor("cursor") ? "sos-symbols" : ""

        property bool cursorSet: false     // this shell set the symbol cursor: it may put Adwaita back
        property string lastKey: ""        // "icons|cursor" as last applied

        // gsettings (GTK) when it is there; Hyprland's cursor (hyprctl) in any case. When the choice
        // changes while the shell runs, the theme files that name it are written again first: the
        // cursor apps get at the next login (XCURSOR_THEME in svoya-colors.conf), Qt's and fuzzel's
        // icons. That may reload Hyprland, so its cursor is set a second later.
        function apply() {
            const key = systemLook.icons + "|" + systemLook.cursor;
            const rerender = systemLook.lastKey.length > 0 && systemLook.lastKey !== key;
            systemLook.lastKey = key;
            const putBack = systemLook.cursor.length === 0 && systemLook.cursorSet;
            systemLook.cursorSet = systemLook.cursor.length > 0;
            Sys.sh((rerender ? 'c=$(command -v sos || command -v svoya) && "$c" theme apply --quiet --only hyprland --only qt6ct --only fuzzel >/dev/null 2>&1 && sleep 1; ' : '')
                + 's=org.gnome.desktop.interface; gs() { command -v gsettings >/dev/null 2>&1 && gsettings "$@"; }; '
                + 'icons=$(gs get $s icon-theme 2>/dev/null | tr -d "\'"); '
                + 'if [ -n "$1" ]; then [ -d "/usr/share/icons/$1" ] && [ "$icons" != "$1" ] && gs set $s icon-theme "$1"; '
                + 'else case $icons in SOS-Symbols*) [ -d "/usr/share/icons/$2" ] && gs set $s icon-theme "$2";; esac; fi; '
                + 'size=${XCURSOR_SIZE:-24}; cur=$(gs get $s cursor-theme 2>/dev/null | tr -d "\'"); '
                + 'if [ -n "$3" ] && [ -d "/usr/share/icons/$3/cursors" ]; then [ "$cur" = "$3" ] || gs set $s cursor-theme "$3"; '
                + 'hyprctl setcursor "$3" "$size" >/dev/null 2>&1; '
                + 'elif [ "$cur" = sos-symbols ] || [ "$4" = 1 ]; then [ "$cur" = sos-symbols ] && gs set $s cursor-theme Adwaita; '
                + 'hyprctl setcursor Adwaita "$size" >/dev/null 2>&1; fi; exit 0',
                [systemLook.icons, systemLook.plainIcons, systemLook.cursor, putBack ? "1" : ""]);
        }

        onIconsChanged: systemLookLater.restart()
        onPlainIconsChanged: systemLookLater.restart()
        onCursorChanged: systemLookLater.restart()
        Component.onCompleted: systemLookLater.restart()
    }
    Timer {
        id: systemLookLater

        // after theme.json is read and a theme switch has settled
        interval: 1500
        onTriggered: systemLook.apply()
    }

    // SOS ASCII over everything: qs ipc call ascii eye | story | planets | saver | rain | logo | heart
    IpcHandler {
        target: "ascii"

        function saver(): void {
            Ui.showAscii("saver");
        }
        function eye(): void {
            Ui.showAscii("eye");
        }
        function story(): void {
            Ui.showAscii("story");
        }
        function planets(): void {
            Ui.showAscii("planets");
        }
        function rain(): void {
            Ui.showAscii("rain");
        }
        function logo(): void {
            Ui.showAscii("logo");
        }
        function heart(): void {
            Ui.showAscii("heart");
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
        // Super+Shift+T (PowerToys' Text Extractor): a region's text straight to the clipboard
        function text(): void {
            Actions.screenshotText();
        }
    }

    IpcHandler {
        target: "overview"

        function toggle(): void {
            Ui.toggle("overview");
        }
        function open(): void {
            Ui.show("overview");
        }
    }

    IpcHandler {
        target: "emoji"

        function toggle(): void {
            Ui.toggle("emoji");
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
        function desktop(): void {
            Ui.hide();
            Hypr.toggleDesktop();
        }
        // Ctrl+Shift+Esc: what runs and what it takes (btop in a terminal)
        function monitor(): void {
            Sys.terminal(["btop"]);
        }
        function colorPicker(): void {
            Actions.pickColor();
        }
        function gameMode(): void {
            Hypr.toggleGameMode();
        }
        // off | auto | on (the Control Center's «Ночной свет»); anything else flips on ↔ off
        function nightLight(mode: string): void {
            Settings.nightLight = ["off", "auto", "on"].indexOf(mode) >= 0 ? mode : (Hypr.nightApplied ? "off" : "on");
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
