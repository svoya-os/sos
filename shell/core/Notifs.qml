pragma Singleton

// Notification daemon (org.freedesktop.Notifications) + toast queue + history.
//
// Do-not-disturb: Settings.dnd or the "presentation" focus mode hides every
// toast except critical ones. "work"/"study" focus modes let through only
// critical and Jackson notifications. Everything still lands in the history
// shown in the control center. Shell feedback ("Скопировано") uses
// shellToast(): toast only, never history.

import QtQuick
import Quickshell
import Quickshell.Services.Notifications

Singleton {
    id: root

    readonly property bool dnd: Settings.dnd || Settings.focusMode === "presentation"
    readonly property bool quiet: Settings.focusMode === "work" || Settings.focusMode === "study"
    readonly property var history: {
        const list = server.trackedNotifications.values.slice();
        list.reverse();
        return list;
    }
    readonly property int count: server.trackedNotifications.values.length

    // Toasts on screen: [{key, n, local, appName, summary, body, icon, urgency, jackson, time}]
    property var toasts: []
    property var times: ({})   // notification id -> Date it arrived
    property int serial: 0
    readonly property int maxToasts: 4

    function isJackson(n) {
        const a = ((n.appName || "") + " " + (n.desktopEntry || "")).toLowerCase();
        return a.indexOf("jackson") >= 0 || a.indexOf("джексон") >= 0;
    }

    function timeOf(n) {
        return n && root.times[n.id] ? root.times[n.id] : null;
    }

    function pushToast(entry) {
        root.serial += 1;
        entry.key = root.serial;
        let list = root.toasts.concat([entry]);
        if (list.length > root.maxToasts)
            list = list.slice(list.length - root.maxToasts);
        root.toasts = list;
    }

    function removeToast(key) {
        root.toasts = root.toasts.filter(t => t.key !== key);
    }

    function removeToastFor(n) {
        root.toasts = root.toasts.filter(t => t.n !== n);
    }

    function incoming(n) {
        const stamp = Object.assign({}, root.times);
        stamp[n.id] = new Date();
        root.times = stamp;
        n.closed.connect(function () {
            root.removeToastFor(n);
        });
        if (n.lastGeneration)
            return; // re-emitted after a shell reload: history only
        const critical = n.urgency === NotificationUrgency.Critical;
        const jackson = root.isJackson(n);
        if (root.dnd && !critical)
            return;
        if (root.quiet && !critical && !jackson)
            return;
        if (Ui.locked)
            return;
        root.pushToast({
            n: n,
            local: false,
            jackson: jackson,
            urgency: n.urgency,
            time: new Date()
        });
        if (!root.dnd)
            Sys.playSound(critical ? "dialog-warning" : "message-new-instant");
    }

    // Toast-only feedback from the shell itself.
    function shellToast(summary, body, icon) {
        if (Ui.locked)
            return;
        root.pushToast({
            n: null,
            local: true,
            appName: Strings.osName,
            summary: summary || "",
            body: body || "",
            icon: icon || "",
            jackson: icon === "jackson",
            urgency: NotificationUrgency.Normal,
            time: new Date()
        });
    }

    function dismiss(n) {
        if (n)
            n.dismiss();
    }

    function clearAll() {
        const list = server.trackedNotifications.values.slice();
        for (let i = 0; i < list.length; i++)
            list[i].dismiss();
        root.toasts = root.toasts.filter(t => t.local);
    }

    function toggleDnd() {
        Settings.dnd = !Settings.dnd;
    }

    NotificationServer {
        id: server

        keepOnReload: true
        persistenceSupported: true
        bodySupported: true
        bodyMarkupSupported: false
        bodyHyperlinksSupported: false
        actionsSupported: true
        imageSupported: false
        onNotification: function (n) {
            n.tracked = true;
            root.incoming(n);
        }
    }
}
