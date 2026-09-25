pragma Singleton

// Svoya Shell design tokens (design/DESIGN.md, themes/*.toml).
//
// Source of truth at runtime: ~/.local/state/svoya/theme.json, written by
// `sos theme apply` (docs/ARCHITECTURE.md §4.1, cli/svoya_cli/theme/apply.py)
// and hot-reloaded here. The CLI writes flat JSON ({"id", "mode", "pair",
// "nameEn", "nameRu", "choice", "wall": "#AARRGGBB", …, "sans", "radius",
// "fast", "grain", …}); a nested layout ({"color": {...}}) is accepted too.
// Missing keys fall back to the built-in Graphite defaults below
// (themes/graphite.toml). QML parses #AARRGGBB (alpha first) natively.

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    // ---- built-in defaults: Graphite (themes/graphite.toml) -------------------
    readonly property var defaults: ({
        id: "graphite",
        mode: "dark",
        pair: "paper",
        name: { en: "Graphite", ru: "Графит" },
        color: {
            wall: "#0c0d0f", bar: "#0e0f11", surface: "#141518", surface2: "#191b1f",
            surface3: "#22252a", line: "#25282d", lineStrong: "#363a41", text: "#ebe8e1",
            textDim: "#9d9a92", textFaint: "#67655f", accent: "#ffb547", accentSoft: "#24ffb547",
            accentInk: "#1b1204", ok: "#8fd48a", warn: "#ffb547", bad: "#ff7a6b",
            cloud: "#7ad3e6", shadow: "#b3000000"
        },
        font: { sans: "IBM Plex Sans", mono: "IBM Plex Mono", pixel: "Departure Mono" },
        shape: { radius: 11, radiusSmall: 6, radiusLarge: 16, border: 1 },
        motion: { fast: 120, base: 180, slow: 260 },
        effects: { grain: 0.07, glow: true, scanlines: false }
    })

    readonly property string path: {
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

    FileView {
        id: file

        path: root.path
        watchChanges: true
        printErrors: false // a missing theme.json on first boot is normal
        onFileChanged: reload()

        JsonAdapter {
            id: adapter

            // meta (flat, as written by `sos theme apply`)
            property string mode
            property string pair
            property string choice    // "auto" when the day/night switch is on
            property string nameEn
            property string nameRu
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

    // ---- colors ---------------------------------------------------------------
    readonly property color wall: root.tok("color", "wall")
    readonly property color bar: root.tok("color", "bar")
    readonly property color surface: root.tok("color", "surface")
    readonly property color surface2: root.tok("color", "surface2")
    readonly property color surface3: root.tok("color", "surface3")
    readonly property color line: root.highContrast ? root.tok("color", "lineStrong") : root.tok("color", "line")
    readonly property color lineStrong: root.highContrast ? root.tok("color", "textFaint") : root.tok("color", "lineStrong")
    readonly property color text: root.tok("color", "text")
    readonly property color textDim: root.highContrast ? root.tok("color", "text") : root.tok("color", "textDim")
    readonly property color textFaint: root.highContrast ? root.tok("color", "textDim") : root.tok("color", "textFaint")
    readonly property color accent: root.tok("color", "accent")
    readonly property color accentSoft: root.tok("color", "accentSoft")
    readonly property color accentInk: root.tok("color", "accentInk")
    readonly property color ok: root.tok("color", "ok")
    readonly property color warn: root.tok("color", "warn")
    readonly property color bad: root.tok("color", "bad")
    readonly property color cloud: root.tok("color", "cloud")
    readonly property color shadow: root.tok("color", "shadow")

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
