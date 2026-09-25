import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Services.Pam
import qs.core
import qs.components

// Lock screen: ext-session-lock (WlSessionLock) + PAM (pam_unix via the
// svoya-lock service), a face per screen (LockFace). Locks on Super+L /
// `quickshell ipc call lock lock` / `loginctl lock-session`, after
// Settings.idleLockMinutes of idle time, and before sleep (a logind delay
// inhibitor holds suspend until the lock surfaces are up).
//
// If the shell dies while locked, Hyprland keeps the session locked; with
// misc:allow_session_lock_restore a restarted shell can take over.
Scope {
    id: root

    property string pamDir: "/etc/pam.d"
    property bool pamReady: false
    property bool busy: false
    property string pending: ""
    property string message: ""
    property bool failed: false
    readonly property bool locked: lock.locked

    function lockNow() {
        if (lock.locked)
            return;
        if (!root.pamReady) {
            Notifs.shellToast(Strings.lockUnavailable, "", "lock");
            return;
        }
        Ui.hide();
        root.message = "";
        root.failed = false;
        root.busy = false;
        Ui.locked = true;
        lock.locked = true;
        // Status keeps streaming: the lock face shows a running job ("while you're away")
    }

    function unlock() {
        lock.locked = false;
        Ui.locked = false;
        root.busy = false;
        root.message = "";
        root.failed = false;
    }

    function submit(password) {
        if (root.busy || password.length === 0)
            return;
        if (pam.active)
            pam.abort();
        root.pending = password;
        root.busy = true;
        root.failed = false;
        root.message = "";
        if (!pam.start()) {
            root.busy = false;
            root.failed = true;
            root.message = Strings.wrongPassword;
        }
    }

    // Our PAM file ships in /etc/pam.d (svoya-shell package); a checkout run
    // falls back to the copy in shell/assets/pam.d.
    Component.onCompleted: {
        Sys.run(["test", "-f", "/etc/pam.d/svoya-lock"], function (code) {
            root.pamDir = code === 0 ? "/etc/pam.d" : Theme.assetPath("pam.d");
            root.pamReady = true;
        });
    }

    Connections {
        target: Actions

        function onLockRequested() {
            root.lockNow();
        }
    }

    WlSessionLock {
        id: lock

        locked: false
        onLockedChanged: {
            if (!locked)
                Ui.locked = false;
        }

        WlSessionLockSurface {
            id: surface

            color: Theme.wall

            LockFace {
                id: face

                anchors.fill: parent
                avatar: Sys.home + "/.face"
                busy: root.busy
                message: root.message
                error: root.failed
                onSubmit: password => root.submit(password)
                Component.onCompleted: Qt.callLater(face.focusField)

                Connections {
                    target: root

                    function onFailedChanged() {
                        if (root.failed)
                            face.clear();
                    }
                }
            }
        }
    }

    PamContext {
        id: pam

        config: "svoya-lock"
        configDirectory: root.pamDir
        user: Sys.user
        onResponseRequiredChanged: {
            if (pam.responseRequired && root.pending.length > 0) {
                pam.respond(root.pending);
                root.pending = "";
            }
        }
        onPamMessage: {
            if (!pam.responseRequired && pam.message.length > 0)
                root.message = pam.message;
        }
        onCompleted: function (result) {
            root.busy = false;
            root.pending = "";
            if (result === PamResult.Success) {
                root.unlock();
            } else {
                root.failed = true;
                root.message = Strings.wrongPassword;
            }
        }
        onError: function (error) {
            root.busy = false;
            root.pending = "";
            root.failed = true;
            root.message = Strings.wrongPassword;
        }
    }

    // ---- idle: lock after N minutes, screens off after M minutes --------------------------
    IdleMonitor {
        enabled: Settings.idleLockMinutes > 0
        timeout: Math.max(1, Settings.idleLockMinutes) * 60
        onIsIdleChanged: {
            if (isIdle)
                root.lockNow();
        }
    }

    IdleMonitor {
        enabled: Settings.idleScreenOffMinutes > 0 && Hypr.present
        timeout: Math.max(1, Settings.idleScreenOffMinutes) * 60
        onIsIdleChanged: Sys.run(["hyprctl", "dispatch", "dpms", isIdle ? "off" : "on"])
    }

    // ---- logind: lock before sleep and on `loginctl lock-session` -----------------------------
    readonly property string sessionPath: {
        // sd_bus_path_encode: every char but [A-Za-z0-9] (and a leading digit) -> _XX
        const id = Quickshell.env("XDG_SESSION_ID") || "";
        let out = "";
        for (let i = 0; i < id.length; i++) {
            const c = id[i];
            const alnum = /[A-Za-z0-9]/.test(c) && !(i === 0 && /[0-9]/.test(c));
            out += alnum ? c : "_" + c.charCodeAt(0).toString(16);
        }
        return out.length > 0 ? "/org/freedesktop/login1/session/" + out : "";
    }

    function onLogind(line) {
        if (line.indexOf("org.freedesktop.login1.Manager.PrepareForSleep") >= 0) {
            if (line.indexOf("(true") >= 0) {
                if (Settings.lockOnSuspend)
                    root.lockNow();
                release.restart(); // let sleep proceed once the lock is up
            } else {
                inhibitor.running = Settings.lockOnSuspend && Sys.has["systemd-inhibit"];
            }
        } else if (line.indexOf("org.freedesktop.login1.Session.Lock ") >= 0) {
            if (root.sessionPath.length === 0 || line.indexOf(root.sessionPath + ":") === 0)
                root.lockNow();
        }
    }

    Process {
        id: logind

        running: Sys.has["gdbus"] === true
        command: ["gdbus", "monitor", "--system", "--dest", "org.freedesktop.login1"]
        stdout: SplitParser {
            onRead: data => root.onLogind(data)
        }
    }

    // A delay inhibitor: logind waits (up to InhibitDelayMaxSec) for us to lock.
    Process {
        id: inhibitor

        running: Settings.lockOnSuspend && Sys.has["systemd-inhibit"] === true
        command: ["systemd-inhibit", "--what=sleep", "--mode=delay", "--who=SOS Shell", "--why=Lock the screen before sleep", "sleep", "infinity"]
    }

    Timer {
        id: release

        interval: 600
        onTriggered: inhibitor.running = false
    }
}
