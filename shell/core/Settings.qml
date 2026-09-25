pragma Singleton

// Shell preferences: ~/.config/svoya/shell.json (owned by the shell; written by
// the control center and the first-run wizard, hot-reloaded when either writes).
// Every key is optional; defaults below. Unknown keys are ignored.

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    readonly property string configDir: {
        const cfg = Quickshell.env("XDG_CONFIG_HOME");
        return (cfg && cfg.length > 0 ? cfg : Quickshell.env("HOME") + "/.config") + "/svoya";
    }
    readonly property string path: root.configDir + "/shell.json"
    readonly property bool loaded: file.loaded

    // interface (aliases write through to the file)
    property alias language: adapter.language             // "" = from $LANG, "ru", "en"
    property alias reduceMotion: adapter.reduceMotion
    property alias highContrast: adapter.highContrast
    property alias largeText: adapter.largeText
    property alias post: adapter.post                     // POST splash after login
    property alias startupSound: adapter.startupSound
    property alias idleLockMinutes: adapter.idleLockMinutes     // 0 = never
    property alias idleScreenOffMinutes: adapter.idleScreenOffMinutes
    property alias lockOnSuspend: adapter.lockOnSuspend
    property alias dnd: adapter.dnd
    property alias focusMode: adapter.focusMode           // "", "work", "study", "presentation"
    property alias layout: adapter.layout                 // "clean", "classic", "hacker"
    property alias wallpaper: adapter.wallpaper           // image path; "" = generated wallpaper
    property alias terminal: adapter.terminal             // "" = xdg-terminal-exec / fallbacks
    property alias kbLayouts: adapter.kbLayouts           // e.g. "us,ru"
    property alias kbSwitch: adapter.kbSwitch             // xkb option, e.g. grp:alt_shift_toggle
    property alias kbCustom: adapter.kbCustom             // true once the wizard/user picked layouts
    property alias tiledWorkspaces: adapter.tiledWorkspaces // workspace ids that differ from the preset default
    property alias themeOnLogin: adapter.themeOnLogin     // theme/accent changes also go to the login screen (--system)

    FileView {
        id: file

        path: root.path
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        // Persist every change made through the aliases. Loading from disk does
        // not emit adapterUpdated, so this never loops.
        onAdapterUpdated: writeAdapter()

        JsonAdapter {
            id: adapter

            property string language: ""
            property bool reduceMotion: false
            property bool highContrast: false
            property bool largeText: false
            property bool post: true
            property bool startupSound: true
            property int idleLockMinutes: 10
            property int idleScreenOffMinutes: 15
            property bool lockOnSuspend: true
            property bool dnd: false
            property string focusMode: ""
            property string layout: "clean"
            property string wallpaper: ""
            property string terminal: ""
            property string kbLayouts: "us,ru"
            property string kbSwitch: "grp:alt_shift_toggle"
            property bool kbCustom: false
            property var tiledWorkspaces: []
            property bool themeOnLogin: false
        }
    }
}
