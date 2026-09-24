pragma Singleton

// Small system helpers: one-off commands with callbacks, detached launches,
// terminal launching, sounds and the list of optional tools that exist.

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    // Optional tools detected at startup: { name: true } for every tool found.
    property var has: ({})
    readonly property var tools: ["svoya", "hyprctl", "cliphist", "wl-copy", "wl-paste", "grim", "slurp", "tesseract", "brightnessctl", "nmcli", "bluetoothctl", "rfkill", "pw-play", "gdbus", "systemd-inhibit", "secret-tool", "xdg-terminal-exec", "kitty", "foot", "alacritty", "ghostty", "gnome-terminal", "ptyxis", "konsole", "x-terminal-emulator", "hyprshutdown", "loginctl", "systemctl", "xdg-open", "notify-send", "python3"]

    readonly property string runtimeDir: {
        const r = Quickshell.env("XDG_RUNTIME_DIR");
        return (r && r.length > 0 ? r : "/tmp") + "/svoya";
    }
    readonly property string home: Quickshell.env("HOME")
    readonly property string user: Quickshell.env("USER") || Quickshell.env("LOGNAME") || ""

    // Run argv, then cb(exitCode, stdout, stderr). stdin (optional) is written and closed.
    function run(argv, cb, stdin) {
        const p = procComponent.createObject(root, {
            command: argv,
            callback: cb || null,
            input: stdin === undefined ? null : String(stdin)
        });
        p.running = true;
        return p;
    }

    // Run through /bin/sh -c. Extra args become $1, $2… (never interpolate user text).
    function sh(script, args, cb, stdin) {
        return root.run(["sh", "-c", script, "sh"].concat(args || []), cb, stdin);
    }

    function detach(argv) {
        Quickshell.execDetached(argv);
    }

    function detachSh(script, args) {
        Quickshell.execDetached(["sh", "-c", script, "sh"].concat(args || []));
    }

    // Open a terminal, optionally running a command (argv list). Honors
    // Settings.terminal, then xdg-terminal-exec, then common terminals.
    function terminal(argv) {
        const cmd = argv || [];
        const custom = Settings.terminal;
        const script = 'term="$1"; shift; ' + 'if [ -n "$term" ] && command -v "$term" >/dev/null 2>&1; then exec "$term" "$@"; fi; ' + 'if command -v xdg-terminal-exec >/dev/null 2>&1; then exec xdg-terminal-exec "$@"; fi; ' + 'for t in kitty foot alacritty ghostty ptyxis gnome-terminal konsole x-terminal-emulator; do ' + '  if command -v "$t" >/dev/null 2>&1; then ' + '    if [ $# -eq 0 ]; then exec "$t"; fi; ' + '    case "$t" in gnome-terminal|ptyxis) exec "$t" -- "$@";; *) exec "$t" -e "$@";; esac; ' + '  fi; ' + 'done';
        root.detachSh(script, [custom].concat(cmd));
    }

    // freedesktop sound name -> first existing file in the Svoya sound theme.
    function playSound(name) {
        if (!root.has["pw-play"])
            return;
        root.detachSh('for d in /usr/share/svoya/sounds/stereo /usr/share/svoya/sounds /usr/share/sounds/svoya/stereo; do ' + 'for e in oga ogg wav; do f="$d/$1.$e"; if [ -f "$f" ]; then exec pw-play "$f"; fi; done; done', [name]);
    }

    function copyText(text) {
        if (root.has["wl-copy"])
            root.run(["wl-copy"], null, text);
        else
            Quickshell.clipboardText = text;
    }

    function openUrl(url) {
        Qt.openUrlExternally(url);
    }

    function mkdirRuntime() {
        root.run(["mkdir", "-p", root.runtimeDir, root.runtimeDir + "/shots"]);
    }

    Component {
        id: procComponent

        Process {
            id: proc

            property var callback: null
            property var input: null
            property bool finished: false

            function finish(code, o, e) {
                if (proc.finished)
                    return;
                proc.finished = true;
                const cb = proc.callback;
                proc.destroy();
                if (cb) {
                    try {
                        cb(code, o, e);
                    } catch (err) {
                        console.warn("svoya: command callback failed:", err);
                    }
                }
            }

            stdinEnabled: proc.input !== null
            stdout: StdioCollector {
                id: outCollector
            }
            stderr: StdioCollector {
                id: errCollector
            }
            onStarted: {
                if (proc.input !== null) {
                    proc.write(proc.input);
                    proc.stdinEnabled = false; // closes stdin -> EOF for the child
                }
            }
            onExited: function (exitCode, exitStatus) {
                proc.finish(exitCode, outCollector.text, errCollector.text);
            }
            // A binary that cannot start never emits exited(); only runningChanged.
            // (On a normal exit, exited() comes first and finish() is a no-op here.)
            onRunningChanged: {
                if (!proc.running)
                    proc.finish(127, "", "failed to start");
            }
        }
    }

    Process {
        id: probe

        running: true
        command: ["sh", "-c", 'for t in "$@"; do command -v "$t" >/dev/null 2>&1 && echo "$t"; done', "sh"].concat(root.tools)
        stdout: StdioCollector {
            onStreamFinished: {
                const found = {};
                const lines = text.split("\n");
                for (let i = 0; i < lines.length; i++) {
                    if (lines[i].length > 0)
                        found[lines[i]] = true;
                }
                root.has = found;
            }
        }
    }

    Component.onCompleted: root.mkdirRuntime()
}
