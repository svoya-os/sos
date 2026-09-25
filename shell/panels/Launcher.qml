import QtQuick
import Quickshell
import Quickshell.Io
import qs.core
import qs.components
import "Fuzzy.js" as Fuzzy

// Launcher / command palette (Super+Space; DESIGN.md §5): the Jackson shell at
// 640px. Groups: Приложения · Файлы · Настройки · Модули · Действия, rows 40px
// (20px icon, Plex Sans 13.5 name, mono 11 secondary, Enter keycap on the top
// hit). `?text` or Tab hands the query to Jackson. Modes (СОС menu):
// settings / modules / actions show one group only; install lists what `sos install`
// knows and is not installed yet (catalog apps by category, then modules). Typing an
// app that is not installed offers «Установить …»; a few secret words do tricks.
PanelFrame {
    id: root

    property string query: ""
    property int selected: 0
    property var modules: []          // from `sos modules list --json`
    property bool modulesLoaded: false
    property var recentFiles: []      // from recently-used.xbel
    property var catalogApps: []      // from `sos apps --json`: Flathub apps by one word
    property var catalogCats: []
    property bool appsLoaded: false

    readonly property string mode: Ui.launcherMode
    readonly property bool askMode: root.query.trim().indexOf("?") === 0

    // ---- static entries ---------------------------------------------------------------------
    readonly property var settingsEntries: [
        { key: "wifi", title: Strings.wifi, secondary: Strings.network, glyph: "svoya-wifi", run: () => Ui.show("cc") },
        { key: "bt", title: Strings.bluetooth, secondary: "", glyph: "bluetooth", run: () => Ui.show("cc") },
        { key: "sound", title: Strings.sound, secondary: Strings.volume, glyph: "svoya-volume", run: () => Ui.show("cc") },
        { key: "brightness", title: Strings.brightness, secondary: "", glyph: "sun", run: () => Ui.show("cc") },
        { key: "look", title: Strings.appearance, secondary: Strings.theme + " · " + Strings.accentLabel + " · sos theme", glyph: "svoya-aperture", run: () => Actions.openLook() },
        { key: "graphite", title: Strings.theme + ": " + Strings.graphite, secondary: "sos theme apply graphite", glyph: "moon", run: () => Theme.setBase("graphite") },
        { key: "paper", title: Strings.theme + ": " + Strings.paper, secondary: "sos theme apply paper", glyph: "sun", run: () => Theme.setBase("paper") },
        { key: "auto", title: Strings.theme + ": " + Strings.auto, secondary: "sos theme apply auto", glyph: "sun-dim", run: () => Theme.setBase("auto") },
        { key: "phosphor", title: Strings.theme + ": " + Strings.phosphor, secondary: "sos theme apply phosphor", glyph: "terminal", run: () => Theme.setBase("phosphor") },
        { key: "jackson-look", title: Strings.customizeJackson, secondary: "j avatar", glyph: "user", run: () => Actions.customizeJackson() },
        { key: "focus", title: Strings.focusMode, secondary: Strings.focusWork + " · " + Strings.focusStudy + " · " + Strings.focusPresentation, glyph: "eye", run: () => Ui.show("cc") },
        { key: "privacy", title: Strings.aiPrivacy, secondary: "", glyph: "shield-check", run: () => Ui.show("cc") },
        { key: "a11y", title: Strings.accessibility, secondary: "Super Alt A", glyph: "user", run: () => Actions.openSetup("accessibility") },
        { key: "setup", title: Strings.setupWizard, secondary: "", glyph: "settings", run: () => Actions.openSetup("") },
        { key: "keys", title: Strings.shortcuts, secondary: "Super K", glyph: "keyboard", run: () => Ui.show("cheatsheet") },
        { key: "layout-clean", title: Strings.layoutPreset + ": " + Strings.wizClean, secondary: "", glyph: "app-window", run: () => Actions.setLayout("clean") },
        { key: "layout-classic", title: Strings.layoutPreset + ": " + Strings.wizClassic, secondary: "", glyph: "panel-bottom", run: () => Actions.setLayout("classic") },
        { key: "layout-hacker", title: Strings.layoutPreset + ": " + Strings.wizHacker, secondary: "", glyph: "layout-grid", run: () => Actions.setLayout("hacker") }
    ]
    // «Акцент: Сирень» → sos theme accent lilac (one row per accent)
    readonly property var accentEntries: Theme.accentList.map(a => ({
                key: "accent-" + a.id,
                title: Strings.accentLabel + ": " + a.name,
                secondary: "sos theme accent " + a.id,
                glyph: "sparkles",
                run: () => Theme.setAccent(a.id)
            }))
    readonly property var actionEntries: [
        { key: "lock", title: Strings.lock, secondary: "Super L", glyph: "lock", run: () => Actions.lock() },
        { key: "logout", title: Strings.logout, secondary: "", glyph: "log-out", run: () => Ui.show("session") },
        { key: "suspend", title: Strings.suspend, secondary: "", glyph: "moon", run: () => Ui.show("session") },
        { key: "reboot", title: Strings.reboot, secondary: "", glyph: "rotate-ccw", run: () => Ui.show("session") },
        { key: "poweroff", title: Strings.poweroff, secondary: "", glyph: "power", run: () => Ui.show("session") },
        { key: "shot", title: Strings.screenshotRegion, secondary: "Super Shift S", glyph: "scan-text", run: () => Actions.screenshot() },
        { key: "clip", title: Strings.clipboard, secondary: "Super V", glyph: "clipboard", run: () => Ui.show("clipboard") },
        { key: "undo", title: Strings.undoSystem, secondary: "sos undo", glyph: "undo-2", run: () => Actions.undo() },
        { key: "doctor", title: Strings.doctor, secondary: "sos doctor", glyph: "stethoscope", run: () => Actions.doctor() },
        { key: "dnd", title: Strings.dnd, secondary: Settings.dnd ? Strings.btOn : Strings.btOff, glyph: Settings.dnd ? "bell-off" : "bell", run: () => Notifs.toggleDnd() },
        { key: "tiling", title: Strings.toggleTiling, secondary: "Super T", glyph: "layout-grid", run: () => Hypr.toggleTiling() },
        { key: "terminal", title: Strings.terminal, secondary: "Super Enter", glyph: "terminal", run: () => Sys.terminal() },
        { key: "install apps store", title: Strings.installApps, secondary: "sos apps", glyph: "store", run: () => Ui.openLauncher("install", "") },
        { key: "skills навыки", title: Strings.jacksonSkills, secondary: "~/.local/share/svoya/jackson/skills", glyph: "book-open", run: () => root.openSkills() },
        { key: "morse sos морзе", title: Strings.morseCallSign, secondary: "sos morse", glyph: "radio", run: () => Sys.detachSos(["morse", "--quiet"]) }
    ].concat(Jackson.enabled ? root.funEntries : [])
    // Jackson's games, found by typing («монетка», «кубик», «анекдот»); answered without a model
    readonly property var funEntries: [
        { key: "coin монетка орел решка", title: Strings.funCoin, secondary: Strings.groupJackson, glyph: "dices", run: () => Actions.askJackson(Strings.funCoinAsk) },
        { key: "dice кубик d20", title: Strings.funDice, secondary: Strings.groupJackson, glyph: "dices", run: () => Actions.askJackson(Strings.funDiceAsk) },
        { key: "joke анекдот шутка", title: Strings.funJoke, secondary: Strings.groupJackson, glyph: "party-popper", run: () => Actions.askJackson(Strings.funJokeAsk) },
        { key: "rps камень ножницы бумага", title: Strings.funRps, secondary: Strings.groupJackson, glyph: "dices", run: () => Actions.askJackson(Strings.funRpsAsk) }
    ]

    // ---- secret words: the whole query, exactly; each trick is harmless or undoable (sos undo) ------
    readonly property var secrets: ({
        "sos": "sos", "сос": "sos", "...---...": "sos", "... --- ...": "sos", "···———···": "sos", "··· ——— ···": "sos",
        "iddqd": "god", "idkfa": "god",
        "пепе": "pepe", "шнейне": "pepe", "пепе шнейне": "pepe", "пепе шнейне фа": "pepe", "втфа": "pepe", "ватафа": "pepe", "pepe": "pepe",
        "42": "answer",
        "кентафурик": "kent", "kentafurik": "kent",
        "привет мир": "hello", "hello world": "hello",
        "чай": "tea", "кофе": "tea", "tea": "tea", "coffee": "tea", "418": "tea",
        "дзен": "zen", "upsil zen": "zen", "дзен upsil": "zen"
    })

    function secretRows(q) {
        const w = q.toLowerCase().replace(/ё/g, "е").replace(/[,!?]/g, "").replace(/\s+/g, " ").trim();
        const hit = root.secrets[w];
        if (!hit)
            return [];
        const gold = "#ffd700";
        const hello = 'command -v upsil >/dev/null 2>&1 || { printf "%s\\n" "$3"; read -r _; exit 0; }; ' + 'f=$(mktemp --suffix=.upl) && printf "%s\\n" "$1" >"$f" && upsil run "$f"; rm -f "$f"; ' + 'printf "\\n%s\\n" "$2"; exec upsil repl';
        const rows = {
            sos: { title: "··· ——— ···", secondary: Strings.morseCallSign, glyph: "radio", run: () => Sys.detachSos(["morse", "--quiet"]) },
            god: { title: Strings.secretGod, secondary: Strings.secretGoldSub, glyph: "zap", run: () => Theme.setAccent(gold) },
            pepe: { title: Strings.secretPepe, secondary: Strings.secretGoldSub, glyph: "party-popper", run: () => {
                    Theme.setAccent(gold);
                    if (Jackson.enabled)
                        Actions.askJackson("пепе шнейне");
                } },
            answer: { title: "42", secondary: Strings.secret42Sub, glyph: "sparkles", run: () => Actions.askJackson(Strings.secret42Ask) },
            kent: { title: Strings.secretKent, secondary: Strings.secretKentSub, glyph: "sparkles", run: () => Actions.askJackson(Strings.ru ? "привет" : "hello") },
            hello: { title: Strings.secretHello, secondary: Strings.secretHelloSub, glyph: "terminal", run: () => Sys.terminal(["sh", "-c", hello, "sh", Strings.secretHelloCode, Strings.secretHelloRepl, Strings.secretNoUpsil]) },
            tea: { title: Strings.secretTea, secondary: "sos чай", glyph: "coffee", run: () => Sys.terminal(["sh", "-c", 'c=$(command -v sos || command -v svoya) && "$c" tea; printf "\\n"; read -r _']) },
            zen: { title: Strings.secretZen, secondary: "upsil zen", glyph: "sparkles", run: () => Sys.terminal(["sh", "-c", 'upsil zen || printf "%s\\n" "$1"; printf "\\n"; read -r _', "sh", Strings.secretNoUpsil]) }
        };
        const r = rows[hit];
        return r ? [{ group: "secret", title: r.title, secondary: r.secondary, glyph: r.glyph, run: r.run, score: 1000 }] : [];
    }

    // The word for installing opens the install list («приложения», «магазин», «apps»…).
    readonly property var installWords: ["apps", "app store", "store", "install app", "install apps", "приложения",
        "установить приложение", "установить программу", "магазин", "магазин приложений", "каталог", "программы"]

    function commandRows(q) {
        const w = q.toLowerCase().replace(/ё/g, "е").replace(/\s+/g, " ").trim();
        if (root.installWords.indexOf(w) < 0)
            return [];
        return [{ group: "install", title: Strings.installApps, secondary: "sos apps", glyph: "store", run: () => Ui.openLauncher("install", ""), score: 1000 }];
    }

    function openSkills() {
        const dir = Sys.home + "/.local/share/svoya/jackson/skills";
        Sys.detachSh('[ -d "$1" ] || { command -v jackson >/dev/null 2>&1 && jackson skills init >/dev/null 2>&1; mkdir -p "$1"; }; exec xdg-open "$1"', [dir]);
    }

    // ---- results ------------------------------------------------------------------------------
    // With an empty query and no launch history yet, the first eight rows are what a new user
    // needs, not the alphabet («Advanced Network Configuration», «Bulk Rename»…). The installer
    // exists only in the live session (finalize.sh purges it) and is always on top there.
    readonly property var featuredApps: ["sos-install", "firefox", "kitty", "thunar", "org.xfce.mousepad", "mousepad",
        "org.gnome.Papers", "org.gnome.Calculator", "org.xfce.ristretto", "btop"]
    readonly property var tuckedApps: ["nm-connection-editor", "thunar-bulk-rename", "thunar-settings", "qt6ct",
        "pavucontrol", "org.pulseaudio.pavucontrol", "kitty-open", "fastfetch"]

    function appRank(id) {
        const i = root.featuredApps.indexOf(id);
        return i >= 0 ? i : (root.tuckedApps.indexOf(id) >= 0 ? 2000 : 1000);
    }

    function appRows(q) {
        const apps = DesktopEntries.applications.values;
        const out = [];
        if (q.length === 0) {
            const counts = ShellState.launchCounts || {};
            const pinned = e => e.id === "sos-install" ? 1 : 0;
            const list = apps.slice().sort((a, b) => (pinned(b) - pinned(a))
                || ((counts[b.id] || 0) - (counts[a.id] || 0))
                || (root.appRank(a.id) - root.appRank(b.id))
                || a.name.localeCompare(b.name));
            for (let i = 0; i < Math.min(8, list.length); i++)
                out.push({ group: "apps", title: list[i].name, secondary: list[i].genericName || list[i].comment || "", icon: list[i].icon, entry: list[i], score: 0 });
            return out;
        }
        for (let i = 0; i < apps.length; i++) {
            const e = apps[i];
            const sc = Fuzzy.best(q, [e.name, e.genericName, (e.keywords || []).join(" "), e.id]);
            if (sc > 60)
                out.push({ group: "apps", title: e.name, secondary: e.genericName || e.comment || "", icon: e.icon, entry: e, score: sc + Math.min(40, (ShellState.launchCounts[e.id] || 0) * 4) });
        }
        out.sort((a, b) => b.score - a.score);
        return out.slice(0, 8);
    }

    function staticRows(group, list, q, limit) {
        const out = [];
        for (let i = 0; i < list.length; i++) {
            const sc = q.length === 0 ? 1 : Fuzzy.best(q, [list[i].title, list[i].secondary, list[i].key]);
            if (sc > 60 || q.length === 0)
                out.push({ group: group, title: list[i].title, secondary: list[i].secondary, glyph: list[i].glyph, run: list[i].run, score: sc });
        }
        out.sort((a, b) => b.score - a.score);
        return out.slice(0, limit);
    }

    function moduleRows(q, limit) {
        const out = [];
        for (let i = 0; i < root.modules.length; i++) {
            const m = root.modules[i];
            const name = m.name ? (Strings.ru ? m.name.ru : m.name.en) || m.id : m.id;
            const summary = m.summary ? (Strings.ru ? m.summary.ru : m.summary.en) || "" : "";
            if (root.mode === "install" && (m.installed || (m.id === "gaming" && q.length === 0)))
                continue;                     // (Steam heads the «Игры» category instead)
            const sc = q.length === 0 ? 1 : Fuzzy.best(q, [name, m.id, summary, (m.aliases || []).join(" ")]);
            if (sc > 60 || q.length === 0)
                out.push({ group: "modules", title: name, secondary: m.installed ? Strings.installed : "sos install " + m.id, glyph: m.id === "gaming" ? "gamepad-2" : "package", module: m, score: sc + (m.installed ? 0 : 1) });
        }
        out.sort((a, b) => b.score - a.score);
        return out.slice(0, limit);
    }

    function fileRows(q) {
        if (q.length < 2)
            return [];
        const out = [];
        for (let i = 0; i < root.recentFiles.length; i++) {
            const f = root.recentFiles[i];
            const sc = Fuzzy.best(q, [f.name, f.path]);
            if (sc > 80)
                out.push({ group: "files", title: f.name, secondary: f.dir, glyph: "file", file: f.path, score: sc });
        }
        out.sort((a, b) => b.score - a.score);
        return out.slice(0, 5);
    }

    // Catalog apps that are not installed yet: «Установить Telegram» (typing «телеграм» is enough).
    // In install mode with an empty query, all of them, grouped by category.
    function installRows(q, limit) {
        if (q.length < 2 && root.mode !== "install")
            return [];
        const out = [];
        for (let i = 0; i < root.catalogApps.length; i++) {
            const a = root.catalogApps[i];
            if (a.installed)
                continue;
            const summary = a.summary ? (Strings.ru ? a.summary.ru : a.summary.en) || "" : "";
            const sc = q.length === 0 ? 1 : Fuzzy.best(q, [a.name, a.key, (a.aliases || []).join(" "), summary]);
            if (sc > 60 || q.length === 0)
                out.push({ group: q.length === 0 ? "cat:" + a.category : "install", title: q.length === 0 ? a.name : Strings.installThing(a.name), secondary: summary + " · sos install " + a.key, glyph: a.category === "games" ? "gamepad-2" : "download", app: a.key, score: sc, idx: i });
        }
        if (q.length > 0) {
            out.sort((a, b) => b.score - a.score);
        } else {
            // Steam is a module (drivers, 32-bit libraries, a password), not a Flathub app;
            // it still belongs at the top of the games, like in `sos apps`
            const gaming = root.modules.find(m => m.id === "gaming" && !m.installed);
            if (gaming)
                out.push({ group: "cat:games", title: "Steam", secondary: Strings.steamModuleSub + " · sos install steam", glyph: "gamepad-2", module: gaming, score: 1, idx: -1 });
            // by category, in the catalog's order, so each caption comes once
            const order = root.catalogCats.map(c => c.id);
            const rank = g => {
                const k = order.indexOf(g.slice(4));
                return k < 0 ? 99 : k;
            };
            out.sort((a, b) => rank(a.group) - rank(b.group) || a.idx - b.idx);
        }
        return out.slice(0, limit);
    }

    readonly property var rows: {
        const q = root.askMode ? "" : root.query.trim();
        let out = [];
        if (root.askMode) {
            out.push({ group: "jackson", title: root.query.trim().slice(1).trim() || Strings.askJackson, secondary: Strings.askJackson, glyph: "sparkles", ask: true });
            return out;
        }
        const m = root.mode;
        if (m === "install")
            return root.installRows(q, 80).concat(root.moduleRows(q, 30));
        if (m === "all" || m === "apps")
            out = out.concat(root.appRows(q));
        if (m === "all") {
            // after apps (so «сос» still finds the live installer first): a secret word, then what
            // can be installed («телеграм» → «Установить Telegram»), then recent files
            out = out.concat(root.secretRows(q)).concat(root.commandRows(q)).concat(root.installRows(q, 3));
            out = out.concat(root.fileRows(q));
        }
        if (m === "all" || m === "settings")
            out = out.concat(root.staticRows("settings", q.length > 0 ? root.settingsEntries.concat(root.accentEntries) : root.settingsEntries, q, m === "settings" ? 20 : (q.length ? 4 : 0)));
        if (m === "all" || m === "modules")
            out = out.concat(root.moduleRows(q, m === "modules" ? 30 : (q.length ? 4 : 0)));
        if (m === "all" || m === "actions")
            out = out.concat(root.staticRows("actions", root.actionEntries, q, m === "actions" ? 20 : (q.length ? 4 : 0)));
        if (q.length > 0 && Jackson.enabled)
            out.push({ group: "jackson", title: q, secondary: Strings.askJackson, glyph: "sparkles", ask: true });
        // one row per thing: «apps» finds «Установить приложение» as a command and as an action
        const seen = {};
        return out.filter(r => {
            const k = r.ask ? "?" + r.title : r.title + "\u0001" + r.secondary;
            if (seen[k])
                return false;
            seen[k] = true;
            return true;
        });
    }

    function groupTitle(g) {
        return ({
            apps: Strings.groupApps,
            files: Strings.groupFiles,
            settings: Strings.groupSettings,
            modules: Strings.groupModules,
            actions: Strings.groupActions,
            jackson: Strings.groupJackson,
            install: Strings.groupInstall,
            secret: Strings.groupSecret
        })[g] || root.categoryTitle(g);
    }

    function categoryTitle(g) {
        if (g.indexOf("cat:") !== 0)
            return "";
        const c = root.catalogCats.find(x => x.id === g.slice(4));
        return c ? (Strings.ru ? c.name.ru : c.name.en) : g.slice(4);
    }

    function activate(i) {
        const r = root.rows[i];
        if (!r)
            return;
        Ui.hide();
        if (r.ask) {
            Actions.askJackson(r.title === Strings.askJackson ? "" : r.title);
        } else if (r.entry) {
            ShellState.recordLaunch(r.entry.id);
            if (r.entry.runInTerminal)
                Sys.terminal(r.entry.command);
            else
                r.entry.execute();
        } else if (r.file) {
            Sys.detach(["xdg-open", r.file]);
        } else if (r.module) {
            if (!r.module.installed) {
                Sys.terminal(["sh", "-c", 'c=$(command -v sos || command -v svoya); "$c" install "$1"; printf "\\n"; read -r _', "sh", r.module.id]);
                root.modulesLoaded = false;
            }
        } else if (r.app) {
            Sys.terminal(["sh", "-c", 'c=$(command -v sos || command -v svoya); "$c" install "$1"; printf "\\n"; read -r _', "sh", r.app]);
            root.appsLoaded = false;
        } else if (r.run) {
            r.run();
        }
    }

    function toJackson() {
        const q = root.query.trim().replace(/^\?\s*/, "");
        Ui.hide();
        Actions.askJackson(q);
    }

    function move(d) {
        const n = root.rows.length;
        if (n === 0)
            return;
        root.selected = (root.selected + d + n) % n;
        list.positionViewAtIndex(root.selected, ListView.Contain);
    }

    width: 640
    implicitHeight: col.implicitHeight

    onQueryChanged: root.selected = 0
    onShownChanged: {
        if (root.shown) {
            field.text = Ui.launcherQuery;
            root.query = Ui.launcherQuery;
            root.selected = 0;
            Qt.callLater(field.focusInput);
            if (!root.modulesLoaded)
                root.loadModules();
            if (!root.appsLoaded)
                root.loadApps();
            xbel.reload();
        }
    }

    function loadModules() {
        Sys.sos(["modules", "list", "--json"], function (code, out) {
            if (code !== 0)
                return;
            try {
                const data = JSON.parse(out);
                const list = Array.isArray(data) ? data : (data.modules || []);
                root.modules = list.map(m => ({
                    id: m.id,
                    name: m.name,
                    summary: m.summary,
                    aliases: m.aliases || [],
                    installed: m.installed === true
                }));
                root.modulesLoaded = true;
            } catch (e) {}
        });
    }

    function loadApps() {
        Sys.sos(["apps", "--json"], function (code, out) {
            if (code !== 0)
                return;
            try {
                const data = JSON.parse(out);
                root.catalogApps = data.apps || [];
                root.catalogCats = data.categories || [];
                root.appsLoaded = true;
            } catch (e) {}
        });
    }

    // Recently used files (freedesktop bookmark spec): href + name.
    FileView {
        id: xbel

        path: Sys.home + "/.local/share/recently-used.xbel"
        printErrors: false
        onLoaded: {
            const t = xbel.text();
            const re = /<bookmark\s+href="file:\/\/([^"]+)"/g;
            const seen = {};
            const out = [];
            let m;
            while ((m = re.exec(t)) !== null && out.length < 400) {
                let p;
                try {
                    p = decodeURIComponent(m[1]);
                } catch (e) {
                    continue;
                }
                if (seen[p])
                    continue;
                seen[p] = true;
                const cut = p.lastIndexOf("/");
                out.push({ path: p, name: p.slice(cut + 1), dir: p.slice(0, cut).replace(Sys.home, "~") });
            }
            root.recentFiles = out.reverse();
        }
    }

    Column {
        id: col

        width: parent.width

        Item {
            width: parent.width
            height: 27.6 + 16 + 18

            TextField {
                id: field

                x: 18
                y: 16
                width: parent.width - 36
                big: true
                placeholder: Strings.launcherPlaceholder
                onTextChanged: root.query = text
                onAccepted: root.activate(root.selected)
                onEscapePressed: Ui.hide()
                onUpPressed: root.move(-1)
                onDownPressed: root.move(1)
                onTabPressed: root.toJackson()
            }
        }

        Rectangle {
            width: parent.width
            height: 1
            color: Theme.line
            visible: root.rows.length > 0 || root.query.length > 0
        }

        ListView {
            id: list

            x: 8
            width: parent.width - 16
            height: Math.min(contentHeight, 9 * 40 + 3 * 30) + (count > 0 ? 16 : 0)
            topMargin: 8
            bottomMargin: 8
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: root.rows
            currentIndex: root.selected
            visible: count > 0

            // group captions are drawn by the first row of each group
            delegate: Column {
                id: cell

                required property var modelData
                required property int index
                readonly property bool firstOfGroup: index === 0 || root.rows[index - 1].group !== modelData.group

                width: list.width

                Item {
                    visible: cell.firstOfGroup
                    width: parent.width
                    height: cell.index === 0 ? 24 : 30

                    Caption {
                        x: 12
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 7
                        text: root.groupTitle(cell.modelData.group)
                    }
                }

                ListRow {
                    width: parent.width
                    glyph: cell.modelData.glyph || ""
                    iconName: cell.modelData.icon || ""
                    title: cell.modelData.title
                    secondary: cell.modelData.secondary || ""
                    selected: cell.index === root.selected
                    hint: "Enter"
                    onActivated: root.activate(cell.index)
                    onHovered: root.selected = cell.index
                }
            }
        }

        SText {
            x: 30
            visible: root.rows.length === 0 && root.query.length > 0
            height: 48
            text: Strings.nothingFound
            color: Theme.textDim
        }

        // footer hints
        Item {
            width: parent.width
            height: 40

            Rectangle {
                width: parent.width
                height: 1
                color: Theme.line
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                spacing: 14

                Row {
                    spacing: 6

                    Keycap {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Enter"
                    }
                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Strings.open
                        size: 11
                        color: Theme.textFaint
                    }
                }

                Row {
                    spacing: 6
                    visible: Jackson.enabled

                    Keycap {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Tab"
                    }
                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Strings.askJackson.toLowerCase()
                        size: 11
                        color: Theme.textFaint
                    }
                }

                Row {
                    spacing: 6

                    Keycap {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Esc"
                    }
                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Strings.close
                        size: 11
                        color: Theme.textFaint
                    }
                }
            }
        }
    }
}
