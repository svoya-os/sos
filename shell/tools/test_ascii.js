// SPDX-License-Identifier: Apache-2.0
// node shell/tools/test_ascii.js — the JavaScript twin (shell/components/ascii.js) draws the same frames as
// the Python reference: every golden frame in cli/tests/golden/ascii (characters and colors), with the
// same small tolerance for a sine rounded the other way; and what only the shell uses (text layers,
// the morph, the screensaver) keeps its promises. Run by scripts/lint.sh.
"use strict";
const fs = require("fs");
const path = require("path");
const A = require("../components/ascii.js");

const root = path.join(__dirname, "..", "..");
const golden = path.join(root, "cli", "tests", "golden", "ascii");
const imp = JSON.parse(fs.readFileSync(path.join(root, "shell", "assets", "jackson", "imp.json"), "utf8"));

const cases = [
    ["eye-idle", () => new A.AsciiEye({ night: false, clock: () => "21:47" }), 2.2, [[80, 24], [160, 48]]],
    ["eye-thinking", () => new A.AsciiEye({ state: "thinking", night: false }), 3.0, [[80, 24]]],
    ["eye-done", () => new A.AsciiEye({ state: "done", night: false }), 1.1, [[80, 24]]],
    ["eye-error", () => new A.AsciiEye({ state: "error", night: false }), 1.5, [[80, 24]]],
    ["eye-story", () => new A.AsciiEye({ story: true, night: false, sprite: imp }), 7.3, [[80, 24], [160, 48]]],
    ["planets", () => new A.AsciiPlanets(), 5.6, [[80, 24], [160, 48]]],
    ["rain", () => new A.AsciiRain(), 9.0, [[80, 24], [160, 48]]],
    ["logo", () => new A.AsciiLogo(), 7.5, [[80, 24], [160, 48]]],
    ["logo-gather", () => new A.AsciiLogo(), 1.2, [[80, 24]]],
    ["heart", () => new A.AsciiHeart(), 0.07, [[80, 24], [160, 48]]],
];

let failed = 0, checked = 0;
for (const [name, make, t, sizes] of cases) {
    for (const [w, h] of sizes) {
        const cv = A.asciiRender(make(), w, h, t);
        const got = A.asciiLines(cv).join("\n") + "\n--\n" + A.asciiColorLines(cv).join("\n") + "\n";
        const want = fs.readFileSync(path.join(golden, `${name}-${w}x${h}.txt`), "utf8");
        const a = Array.from(want), b = Array.from(got);
        let diff = Math.abs(a.length - b.length);
        for (let i = 0; i < Math.min(a.length, b.length); i++) if (a[i] !== b[i]) diff++;
        const limit = Math.max(3, Math.floor(w * h / 400));
        checked++;
        if (diff > limit) {
            failed++;
            console.log(`FAIL ${name}-${w}x${h}: ${diff} cells differ (limit ${limit})`);
            const wl = want.split("\n"), gl = got.split("\n");
            for (let r = 0; r < wl.length && r < gl.length; r++)
                if (wl[r] !== gl[r]) { console.log("  want " + JSON.stringify(wl[r])); console.log("  got  " + JSON.stringify(gl[r])); break; }
        }
    }
}

// the hash is the same 32-bit function as engine.hash3
const expectHash = [[1, 2, 3, 2151121503], [7, 0, 2, null]];
for (const [i, j, k, v] of expectHash) {
    if (v === null) continue;
    if (A.asciiHash(i, j, k) !== v) { failed++; console.log(`FAIL hash(${i},${j},${k}) = ${A.asciiHash(i, j, k)}, want ${v}`); }
}

// the three text layers put together are the frame
function check(what, ok) { checked++; if (!ok) { failed++; console.log("FAIL " + what); } }
{
    const cv = A.asciiRender(new A.AsciiEye({ night: false }), 120, 40, 2.2);
    const layers = A.asciiLayers(cv).slice(1).map(s => s.split("\n"));
    const rows = A.asciiLines(cv);
    let same = layers.every(l => l.length === 40);
    for (let r = 0; r < 40 && same; r++) {
        for (let x = 0; x < 120; x++) {
            const hits = layers.map(l => l[r][x] || " ").filter(c => c !== " ");
            const want = rows[r][x] === " " || cv.co[r * 120 + x] === 0 ? [] : [rows[r][x]];
            if (hits.length !== want.length || (want.length && hits[0] !== want[0])) { same = false; break; }
        }
    }
    check("asciiLayers rebuild the frame", same);
    check("asciiLayers cut trailing spaces", layers.every(l => l.every(row => !/ $/.test(row))));
}
// a morph starts as the first picture and ends as the second
{
    const imp2 = A.asciiJackson(imp, {}, "idle", 24).map(e => [e[0] + 10, e[1] + 4, e[2], e[3]]);
    const eye = A.asciiRender(new A.AsciiEye({ hud: false, night: false }), 100, 30, 0);
    const m = new A.AsciiMorph(imp2, A.asciiCells(eye), 1.8);
    const at = t => { const cv = A.asciiCanvas(100, 30); m.draw(cv, t); return cv; };
    const key = cells => cells.map(e => e.join(",")).sort().join(";");
    check("morph begins as Jackson", key(A.asciiCells(at(0))) === key(imp2.filter((e, i, a) => a.findIndex(f => f[0] === e[0] && f[1] === e[1]) === i)));
    const end = A.asciiCells(at(1.8)), want = A.asciiCells(eye);
    const wantSet = new Set(want.map(e => e.join(",")));
    check("morph ends as the eye", end.length === want.length && end.every(e => wantSet.has(e.join(","))));
    const mid = at(0.9);
    check("morph in flight stays in four colors", Array.from(mid.co).every(c => c <= 3));
}
// the screensaver: Jackson where he stood, then the eye, the film every storyEvery seconds
{
    const s = new A.AsciiSaver({ sprite: imp, from: { x: 30, y: 6, cols: 20 }, storyEvery: 20, hold: 0.8 });
    const cv0 = A.asciiRender(s, 100, 30, 0);
    const xs = A.asciiCells(cv0).map(e => e[0]);
    check("saver starts with Jackson at his place", xs.length > 40 && Math.min(...xs) >= 29 && Math.max(...xs) <= 51);
    check("he stands still while the screen fades", A.asciiLines(A.asciiRender(s, 100, 30, 0.7)).join("\n") === A.asciiLines(cv0).join("\n"));
    const eyeAt = t => A.asciiLines(A.asciiRender(new A.AsciiEye({ hud: false, night: false, sprite: imp }), 100, 30, t)).join("\n");
    check("after the morph it is the eye", A.asciiLines(A.asciiRender(s, 100, 30, 0.8 + 1.8 + 1.0)).join("\n") === eyeAt(1.0));
    const film = A.asciiLines(A.asciiRender(s, 100, 30, 0.8 + 1.8 + 20 + 7.3)).join("\n");
    const story = A.asciiLines(A.asciiRender(new A.AsciiEye({ story: true, night: false, sprite: imp }), 100, 30, 7.3)).join("\n");
    check("the film plays after storyEvery seconds", film === story);
    check("tiny screens still draw", A.asciiCells(A.asciiRender(new A.AsciiSaver({ sprite: imp, from: { x: 1, y: 1, cols: 8 } }), 20, 6, 3)).length > 0);
}
// fast enough for a 1080p lock screen and a live wallpaper: what stands still (the eye's white, the
// planet, its ring) is kept between frames. Node is faster than the shell's QML engine; the shell's
// timer slows a frame down rather than spend more than a third of a core (AsciiView.qml).
{
    const timed = (fx, w, h, t0) => {
        for (let n = 0; n < 5; n++) { const cv = A.asciiCanvas(w, h); fx.draw(cv, t0 + n / 24); A.asciiLayers(cv); }
        const start = Date.now();
        for (let n = 0; n < 48; n++) { const cv = A.asciiCanvas(w, h); fx.draw(cv, t0 + 1 + n / 24); A.asciiLayers(cv); }
        return (Date.now() - start) / 48;
    };
    const saver = timed(new A.AsciiSaver({ sprite: imp, from: { x: 90, y: 20, cols: 24 } }), 228, 63, 12);
    const planet = timed(new A.AsciiPlanets({ hud: false }), 179, 48, 3);
    if (process.env.SOS_ASCII_TIMES) console.log(`saver ${saver.toFixed(1)} ms, planet ${planet.toFixed(1)} ms`);
    check(`a 228×63 screensaver frame in ${saver.toFixed(1)} ms (< 20)`, saver < 20);
    check(`a 179×48 planet frame in ${planet.toFixed(1)} ms (< 12)`, planet < 12);
}

// the Firefox autoconfig (assets/firefox/sos.cfg): the SOS page and frame only with Phosphor
function runCfg(themeJson, shellJson) {
    const prefs = {}, sheets = [];
    let newTab = null;
    const files = { "/home/u/.local/state/svoya/theme.json": themeJson };
    if (shellJson !== undefined) files["/home/u/.config/svoya/shell.json"] = shellJson;
    const fake = {
        "@mozilla.org/process/environment;1": { get: k => ({ HOME: "/home/u" })[k] || "" },
        "@mozilla.org/file/local;1": { initWithPath(p) { this.p = p; }, exists() { return this.p in files; } },
        "@mozilla.org/network/file-input-stream;1": { init(f) { this.f = f; } },
        "@mozilla.org/intl/converter-input-stream;1": {
            init(raw) { this.left = files[raw.f.p]; }, readString(n, out) { out.value = this.left; const k = this.left.length; this.left = ""; return k; }, close() {} },
        "@mozilla.org/observer-service;1": { addObserver() {}, removeObserver() {} },
        "@mozilla.org/content/style-sheet-service;1": { USER_SHEET: 2, sheetRegistered: () => false, loadAndRegisterSheet: (u) => sheets.push(u) },
        "@mozilla.org/network/io-service;1": { newURI: s => decodeURIComponent(s.replace(/^data:text\/css;charset=utf-8,/, "")) },
    };
    const classes = new Proxy({}, { get: (o, k) => ({ getService: () => fake[k], createInstance: () => Object.create(fake[k]) }) });
    const errors = [];
    const Components = { classes, interfaces: new Proxy({}, { get: (o, k) => k }), utils: { reportError: e => errors.push(String(e)) } };
    const ChromeUtils = { importESModule: () => ({ AboutNewTab: { set newTabURL(v) { newTab = v; } } }) };
    new Function("defaultPref", "ChromeUtils", "Components", fs.readFileSync(path.join(root, "shell", "assets", "firefox", "sos.cfg"), "utf8"))(
        (k, v) => { prefs[k] = v; }, ChromeUtils, Components);
    return { prefs, sheets, newTab, errors };
}
{
    const phosphor = JSON.stringify({ id: "phosphor", mode: "dark", accent: "#ff3cffd0", wall: "#ff0a0a0a", text: "#ffceffef", textFaint: "#ff5a5a5a", mono: "IBM Plex Mono" });
    const ph = runCfg(phosphor);
    check("phosphor: no errors in sos.cfg " + ph.errors.join(" "), ph.errors.length === 0);
    check("phosphor: the new tab is the SOS page, a plain address (Firefox then leaves the address bar empty)",
          ph.newTab === "file:///usr/share/svoya/shell/assets/newtab/index.html" && ph.prefs["browser.startup.homepage"] === ph.newTab);
    check("phosphor: the page gets the theme's colors from the sheet",
          /@-moz-document url-prefix\("file:\/\/\/usr\/share\/svoya\/shell\/assets\/newtab\/index\.html"\) \{\s*:root \{ --fg: #3cffd0 !important; --bg: #0a0a0a !important; --noise: #5a5a5a !important; \}/.test(ph.sheets[0] || ""));
    check("phosphor: theme images and gradients are painted over", /#navigator-toolbox, #titlebar, #TabsToolbar, #toolbar-menubar \{ background: rgba\(10, 10, 10, 1\.000\) !important;/.test(ph.sheets[0] || ""));
    check("phosphor: Firefox's dark theme underneath", ph.prefs["extensions.activeThemeID"] === "firefox-compact-dark@mozilla.org");
    check("the symbol style off: Firefox as it is", runCfg(phosphor, JSON.stringify({ asciiStyle: "off" })).newTab === null);
    check("without the browser part: Firefox as it is", runCfg(phosphor, JSON.stringify({ asciiParts: ["widgets"] })).sheets.length === 0);
    const paper = runCfg(JSON.stringify({ id: "paper", mode: "light", accent: "#ff0b6e5a", wall: "#fff2efe8" }), JSON.stringify({ asciiStyle: "always" }));
    check("always + paper: a light page, no dark Firefox theme", /--alive: #d6246e !important; color-scheme: light !important;/.test(paper.sheets[0] || "")
          && /--bg: #f2efe8 !important/.test(paper.sheets[0] || "") && !("extensions.activeThemeID" in paper.prefs));
    check("phosphor: the frame is themed", ph.sheets.length === 1 && ph.sheets[0].includes("--toolbar-bgcolor") && ph.sheets[0].includes("rgba(10, 10, 10, 1.000)") && ph.sheets[0].includes('"IBM Plex Mono"'));
    const gr = runCfg(JSON.stringify({ id: "graphite", accent: "#ffffb547" }));
    check("graphite: Firefox as it is", gr.newTab === null && Object.keys(gr.prefs).length === 0 && gr.sheets.length === 0 && gr.errors.length === 0);
    const none = runCfg("");
    check("no theme.json: Firefox as it is", none.newTab === null && none.sheets.length === 0 && none.errors.length === 0);
    check("the page exists", fs.existsSync(path.join(root, "shell", "assets", "newtab", "index.html")) &&
          fs.readFileSync(path.join(root, "shell", "assets", "newtab", "index.html"), "utf8").includes('src="../../components/ascii.js"'));
}

console.log(`test_ascii: ${checked} checks (golden frames, layers, morph, saver, Firefox), ${failed} failed`);
process.exit(failed ? 1 : 0);
