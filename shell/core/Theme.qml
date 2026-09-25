pragma Singleton

// SOS Shell design tokens (design/DESIGN.md, themes/*.toml, themes/accents.toml).
//
// Source of truth at runtime: ~/.local/state/svoya/theme.json, written by `sos theme apply` and
// `sos theme accent` (docs/ARCHITECTURE.md §4.1, cli/svoya_cli/theme/apply.py) and hot-reloaded
// here. The greeter reads the system copy, /etc/svoya/theme.json (`sos theme apply --system`);
// SVOYA_THEME_FILE overrides both. Flat JSON ({"id", "mode", "choice", "wall": "#AARRGGBB", …,
// "accentId", "accentStrong", …}); a nested layout ({"color": {...}}) is accepted too. Missing
// keys fall back to Graphite + the «Сигнал» accent below.
//
// Accent (DESIGN §10–§11): accent, accentSoft, accentStrong (hover/pressed), accentInk (text on
// the accent) plus the choice (accentId, accentCustom). `previewAccent` shows another accent
// without applying it (control center swatches on hover); `setAccent()` applies through the CLI.
//
// Colors cross-fade for 260 ms when the theme or the accent changes (instant with reduce motion
// and while the first theme.json is loading, so a login never fades from the defaults).

import QtQuick
import Quickshell
import Quickshell.Io
import "Color.js" as Color

Singleton {
    id: root

    // ---- built-in defaults: Graphite + «Сигнал» (themes/graphite.toml, accents.toml) ---------
    readonly property var defaults: ({
        id: "graphite",
        mode: "dark",
        pair: "paper",
        name: { en: "Graphite", ru: "Графит" },
        color: {
            wall: "#0c0d0f", bar: "#0e0f11", surface: "#141518", surface2: "#191b1f",
            surface3: "#22252a", line: "#25282d", lineStrong: "#363a41", text: "#ebe8e1",
            textDim: "#9d9a92", textFaint: "#67655f", accent: "#ffb547", accentSoft: "#24ffb547",
            accentStrong: "#ffd093", accentInk: "#141518", ok: "#8fd48a", warn: "#f5cf52",
            bad: "#ff6b6b", cloud: "#7ad3e6", shadow: "#b3000000"
        },
        font: { sans: "IBM Plex Sans", mono: "IBM Plex Mono", pixel: "Departure Mono" },
        shape: { radius: 11, radiusSmall: 6, radiusLarge: 16, border: 1 },
        motion: { fast: 120, base: 180, slow: 260 },
        effects: { grain: 0.07, glow: true, scanlines: false }
    })

    // The greeter (a config root named "greeter") shows the system theme.
    readonly property bool systemTheme: /\/greeter\/?$/.test(Quickshell.shellDir)
    readonly property string path: {
        const forced = Quickshell.env("SVOYA_THEME_FILE");
        if (forced && forced.length > 0)
            return forced;
        if (root.systemTheme)
            return "/etc/svoya/theme.json";
        const state = Quickshell.env("XDG_STATE_HOME");
        const base = state && state.length > 0 ? state : Quickshell.env("HOME") + "/.local/state";
        return base + "/svoya/theme.json";
    }

    // Resolve one token: nested section first, then the flat key, then default.
    function tok(section, key) {
        const sec = adapter[section];
        if (sec && sec[key] !== undefined && sec[key] !== null && sec[key] !== "")
            return sec[key];
        const flat = adapter[key];
        if (flat !== undefined && flat !== null && flat !== "")
            return flat;
        const def = root.defaults[section];
        return def ? def[key] : undefined;
    }

    function num(section, key) {
        const v = Number(root.tok(section, key));
        return isNaN(v) ? Number(root.defaults[section][key]) : v;
    }

    function bool(section, key) {
        const v = root.tok(section, key);
        return v === true || v === "true" || v === 1;
    }

    // true once the first theme.json read finished (or failed): from then on colors fade
    property bool settled: false

    FileView {
        id: file

        path: root.path
        watchChanges: true
        printErrors: false // a missing theme.json on first boot is normal
        onFileChanged: reload()
        onLoaded: Qt.callLater(() => root.settled = true)
        onLoadFailed: root.settled = true

        JsonAdapter {
            id: adapter

            // meta (flat, as written by `sos theme apply`)
            property string mode
            property string pair
            property string choice    // "auto" when the day/night switch is on
            property string nameEn
            property string nameRu
            property string accentId      // an accents.toml id, "custom" or "theme"
            property string accentNameEn
            property string accentNameRu
            property var accentCustom     // the user's own "#rrggbb" (or null)
            property bool accentAdjusted  // lightness was moved for contrast
            property var accentContrast
            // nested sections (themes/*.toml layout, accepted as well)
            property var name
            property var color
            property var font
            property var shape
            property var motion
            property var effects

            // flat keys (the same tokens without sections)
            property var wall
            property var bar
            property var surface
            property var surface2
            property var surface3
            property var line
            property var lineStrong
            property var text
            property var textDim
            property var textFaint
            property var accent
            property var accentSoft
            property var accentStrong
            property var accentInk
            property var ok
            property var warn
            property var bad
            property var cloud
            property var shadow
            property var sans
            property var mono
            property var pixel
            property var radius
            property var radiusSmall
            property var radiusLarge
            property var border
            property var fast
            property var base
            property var slow
            property var grain
            property var glow
            property var scanlines
        }
    }

    Timer {
        // no theme file and no answer yet: stop waiting
        running: !root.settled
        interval: 1500
        onTriggered: root.settled = true
    }

    // `id` cannot be a QML property name, so it is read from the raw text.
    readonly property string themeId: {
        const txt = file.text();
        if (txt && txt.length > 0) {
            try {
                const parsed = JSON.parse(txt);
                if (parsed && typeof parsed.id === "string" && parsed.id.length > 0)
                    return parsed.id;
            } catch (e) {}
        }
        return root.defaults.id;
    }

    // ---- meta -----------------------------------------------------------------
    readonly property string mode: adapter.mode.length > 0 ? adapter.mode : root.defaults.mode
    readonly property bool isDark: root.mode !== "light"
    readonly property string pair: adapter.pair.length > 0 ? adapter.pair : root.defaults.pair
    readonly property bool autoMode: adapter.choice === "auto"
    // what the base-theme switch shows: graphite | paper | phosphor | auto
    readonly property string baseChoice: root.autoMode ? "auto" : root.themeId
    readonly property string displayName: {
        if (adapter.nameEn.length > 0 || adapter.nameRu.length > 0)
            return (Strings.ru ? adapter.nameRu : adapter.nameEn) || adapter.nameEn || root.themeId;
        const n = adapter.name ? adapter.name : root.defaults.name;
        return (Strings.ru ? n.ru : n.en) || root.themeId;
    }

    // accessibility switches (shell settings, DESIGN.md §9)
    readonly property bool reduceMotion: Settings.reduceMotion || root.bool("motion", "reduce")
    readonly property bool highContrast: Settings.highContrast
    readonly property real textScale: Settings.largeText ? 1.15 : 1.0

    // ---- the accent choice (DESIGN §10) ------------------------------------------------------------
    readonly property string accentId: adapter.accentId.length > 0 ? adapter.accentId : "signal"
    readonly property string accentCustom: typeof adapter.accentCustom === "string" ? adapter.accentCustom : ""
    // what the user picked: an accent id or their own "#rrggbb"
    readonly property string accentChoice: root.accentId === "custom" && root.accentCustom.length > 0 ? root.accentCustom : root.accentId
    readonly property bool accentAdjusted: adapter.accentAdjusted
    readonly property string accentName: {
        if (root.accentId === "custom")
            return Strings.t("Свой", "Custom");
        const n = Strings.ru ? adapter.accentNameRu : adapter.accentNameEn;
        if (n.length > 0)
            return n;
        const a = Color.accentById(root.accentId);
        return a ? (Strings.ru ? a.ru : a.en) : root.accentId;
    }
    // the eight accents for swatches, in this theme's mode
    readonly property var accentList: Color.ACCENTS.map(a => ({
                id: a.id,
                name: Strings.ru ? a.ru : a.en,
                color: root.isDark ? a.dark : a.light
            }))

    // An accent id or "#hex" shown instead of the applied one (hover preview), "" = none.
    property string previewAccent: ""
    // a click keeps its choice previewed until theme.json reports it (no flash back)
    property string pendingAccent: ""
    readonly property string shownAccent: root.previewAccent.length > 0 ? root.previewAccent : root.pendingAccent
    readonly property var previewTokens: root.shownAccent.length > 0 ? Color.resolveAccent(root.shownAccent, root.mode, String(root.tok("color", "surface"))) : null

    function accentTokens(choice) {
        return Color.resolveAccent(choice, root.mode, String(root.tok("color", "surface")));
    }

    // {id, en, ru, dark, light} of an accents.toml id (null for anything else)
    function accentById(id) {
        return Color.accentById(id);
    }

    function contrastWith(a, b) {
        return Color.contrast(String(a), String(b));
    }

    // ---- applying (the CLI renders every template: Hyprland, GTK/Qt, terminals; `sos undo`) ----------
    // The login screen follows when Settings.themeOnLogin is on: one `sos theme apply --system`
    // (polkit asks for the admin password) once the user has finished choosing — when the open panel
    // closes, or 20 s after the last change with no panel open — instead of a prompt per click, and
    // never while an overlay holds the keyboard (the password dialog would sit under it).
    // The wizard turns `autoSystemSync` off and applies it after it hides.
    property bool systemSyncPending: false
    property bool autoSystemSync: true
    signal systemSyncDone(bool ok)

    function setAccent(choice) {
        if (!choice || choice.length === 0)
            return;
        root.pendingAccent = choice;
        pendingClear.restart();
        Sys.sos(["theme", "accent", choice, "--json"], function (code) {
            if (code !== 0) {
                root.pendingAccent = "";
                return;
            }
            root.queueSystemSync();
        });
    }

    // graphite | paper | phosphor | auto
    function setBase(themeId) {
        Sys.sos(["theme", "apply", themeId, "--quiet"], function (code) {
            if (code === 0)
                root.queueSystemSync();
        });
    }

    function queueSystemSync() {
        if (!Settings.themeOnLogin)
            return;
        root.systemSyncPending = true;
        if (root.autoSystemSync)
            systemSync.restart();
    }

    function flushSystemSync() {
        if (!root.systemSyncPending)
            return;
        root.systemSyncPending = false;
        systemSync.stop();
        root.applySystemTheme(function (code) {
            root.systemSyncDone(code === 0);
        });
    }

    // the current look → /etc/svoya/theme.json (cb(exitCode): 0 = done, else not changed)
    function applySystemTheme(cb) {
        Sys.sos(["theme", "apply", "--system", "--quiet"], cb || null);
    }

    Timer {
        id: systemSync

        interval: 20000
        onTriggered: {
            if (Ui.open)
                systemSync.restart();
            else
                root.flushSystemSync();
        }
    }

    Connections {
        target: Ui

        function onModalChanged() {
            if (!Ui.open && root.autoSystemSync)
                root.flushSystemSync();
        }
    }

    onAccentChoiceChanged: {
        if (root.pendingAccent.length > 0 && root.pendingAccent.toLowerCase() === root.accentChoice.toLowerCase())
            root.pendingAccent = "";
    }

    Timer {
        id: pendingClear

        interval: 6000
        onTriggered: root.pendingAccent = ""
    }

    // ---- colors: targets (instant) ---------------------------------------------------------------
    readonly property color targetLine: root.highContrast ? root.tok("color", "lineStrong") : root.tok("color", "line")
    readonly property color targetLineStrong: root.highContrast ? root.tok("color", "textFaint") : root.tok("color", "lineStrong")
    readonly property color targetTextDim: root.highContrast ? root.tok("color", "text") : root.tok("color", "textDim")
    readonly property color targetTextFaint: root.highContrast ? root.tok("color", "textDim") : root.tok("color", "textFaint")
    readonly property color targetAccent: root.previewTokens ? root.previewTokens.color : root.tok("color", "accent")
    readonly property color targetAccentSoft: root.previewTokens ? root.previewTokens.soft : root.tok("color", "accentSoft")
    readonly property color targetAccentInk: root.previewTokens ? root.previewTokens.ink : root.tok("color", "accentInk")
    readonly property color targetAccentStrong: {
        if (root.previewTokens)
            return root.previewTokens.strong;
        const s = root.tok("color", "accentStrong");
        return s ? s : Color.strong(String(root.tok("color", "accent")), root.mode);
    }

    // ---- colors: what everything binds to (cross-fade 260 ms) --------------------------------------
    readonly property int colorMs: root.reduceMotion || !root.settled ? 0 : 260

    property color wall: root.tok("color", "wall")
    property color bar: root.tok("color", "bar")
    property color surface: root.tok("color", "surface")
    property color surface2: root.tok("color", "surface2")
    property color surface3: root.tok("color", "surface3")
    property color line: root.targetLine
    property color lineStrong: root.targetLineStrong
    property color text: root.tok("color", "text")
    property color textDim: root.targetTextDim
    property color textFaint: root.targetTextFaint
    property color accent: root.targetAccent
    property color accentSoft: root.targetAccentSoft
    property color accentStrong: root.targetAccentStrong
    property color accentInk: root.targetAccentInk
    property color ok: root.tok("color", "ok")
    property color warn: root.tok("color", "warn")
    property color bad: root.tok("color", "bad")
    property color cloud: root.tok("color", "cloud")
    property color shadow: root.tok("color", "shadow")

    Behavior on wall {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on bar {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on surface {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on surface2 {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on surface3 {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on line {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on lineStrong {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on text {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on textDim {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on textFaint {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on accent {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on accentSoft {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on accentStrong {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on accentInk {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on ok {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on warn {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on bad {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on cloud {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }
    Behavior on shadow {
        ColorAnimation {
            duration: root.colorMs
            easing.type: Easing.OutCubic
        }
    }

    // Neutral selection and focus colors (DESIGN §9, §11: the accent never marks a selection).
    readonly property color selected: root.text                        // on / selected / checked
    readonly property color focusRing: root.alpha(root.text, 0.7)       // 2px outline, 2px offset

    // ---- typography (DESIGN.md §2) -------------------------------------------
    readonly property string sans: root.tok("font", "sans")
    readonly property string mono: root.tok("font", "mono")
    readonly property string pixel: root.tok("font", "pixel")

    readonly property real fsDisplay: 96      // lock & greeter clock, weight 300
    readonly property real fsTitle: 20        // Jackson input, launcher query
    readonly property real fsWizard: 28       // wizard step titles
    readonly property real fsHeading: 16
    readonly property real fsBody: 14
    readonly property real fsAnswer: 14.2     // Jackson answer paragraphs (mockup)
    readonly property real fsUi: 13
    readonly property real fsWindowTitle: 12.5
    readonly property real fsSystem: 11.5     // the bar
    readonly property real fsMeta: 11
    readonly property real fsPixel: 11        // Departure Mono only at 11/22/33

    // OpenType features used by the mockup (font-feature-settings: "ss02", "zero")
    readonly property var sansFeatures: ({ "ss02": 1, "zero": 1 })
    readonly property var monoFeatures: ({ "zero": 1 })
    readonly property var tabularFeatures: ({ "tnum": 1, "zero": 1 })

    // letter-spacing helpers (CSS em -> px)
    function em(px, value) {
        return px * value;
    }

    // ---- shape (DESIGN.md §3) --------------------------------------------------
    readonly property real radius: root.num("shape", "radius")           // windows
    readonly property real radiusSmall: root.num("shape", "radiusSmall") // small controls
    readonly property real radiusLarge: root.num("shape", "radiusLarge") // floating panels
    readonly property real border: root.num("shape", "border")
    readonly property real radiusButton: 9
    readonly property real radiusKeycap: 5
    readonly property real radiusToast: 12
    readonly property real radiusBlock: 10 // bordered blocks inside panels (tables)

    // 4px grid: 4 8 12 16 18 24 32 48
    readonly property int sp4: 4
    readonly property int sp8: 8
    readonly property int sp12: 12
    readonly property int sp16: 16
    readonly property int sp18: 18
    readonly property int sp24: 24
    readonly property int sp32: 32
    readonly property int sp48: 48

    readonly property int barHeight: 30

    // ---- motion (DESIGN.md §4): OutCubic, no bounce; reduce motion -> 0 -------
    readonly property int fast: root.reduceMotion ? 0 : root.num("motion", "fast")
    readonly property int base: root.reduceMotion ? 0 : root.num("motion", "base")
    readonly property int slow: root.reduceMotion ? 0 : root.num("motion", "slow")
    readonly property int easing: Easing.OutCubic

    // ---- effects --------------------------------------------------------------
    readonly property real grain: root.num("effects", "grain")
    readonly property bool glow: root.bool("effects", "glow") && root.isDark
    readonly property bool scanlines: root.bool("effects", "scanlines")

    // ---- helpers --------------------------------------------------------------
    function alpha(c, a) {
        return Qt.rgba(c.r, c.g, c.b, a);
    }

    function mix(a, b, t) {
        return Qt.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t, a.a + (b.a - a.a) * t);
    }

    // URL of a file in shell/assets (works for the shell, greeter and setup roots,
    // which link the same assets directory).
    function asset(rel) {
        return Qt.resolvedUrl("../assets/" + rel);
    }

    // Absolute filesystem path of a file in shell/assets (for Process arguments).
    function assetPath(rel) {
        return Quickshell.shellPath("assets/" + rel);
    }
}
