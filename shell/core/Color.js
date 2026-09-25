.pragma library
// Color math shared by the theme (accent preview, contrast badge) and the mascot sprites.
// SPDX-License-Identifier: Apache-2.0
//
// Mirrors the CLI (cli/svoya_cli/theme/accents.py, colors.py) so a hover preview shows what
// `sos theme accent …` will write: WCAG contrast, OKLCH lightness moves that keep hue and chroma,
// accentSoft = 14 % (dark) / 9 % (light) alpha, accentStrong = OKLCH L ±0.06, accentInk = #141518
// or #ffffff, whichever contrasts more. The mascot outfit/detail derivations are the reference
// runtime's (design/mascot/jackson.js, DESIGN §13). Plain ES2016: no newer library calls.

var ACCENTS = [
    { id: "signal", ru: "Сигнал", en: "Signal", dark: "#ffb547", light: "#2b3af7" },
    { id: "amber", ru: "Янтарь", en: "Amber", dark: "#ffb547", light: "#9a5200" },
    { id: "ink", ru: "Чернила", en: "Ink", dark: "#8f9dff", light: "#2b3af7" },
    { id: "phosphor", ru: "Фосфор", en: "Phosphor", dark: "#5cf08f", light: "#0f7a3a" },
    { id: "ice", ru: "Лёд", en: "Ice", dark: "#62d4f2", light: "#006f8e" },
    { id: "lilac", ru: "Сирень", en: "Lilac", dark: "#bba4ff", light: "#6a3fd6" },
    { id: "rose", ru: "Роза", en: "Rose", dark: "#ff82b2", light: "#b8185a" },
    { id: "mono", ru: "Моно", en: "Mono", dark: "#ebe8e1", light: "#151515" }
];

var MIN_CONTRAST = 4.5;
var INK_DARK = "#141518";
var INK_LIGHT = "#ffffff";

function accentById(id) {
    for (var i = 0; i < ACCENTS.length; i++) {
        if (ACCENTS[i].id === id)
            return ACCENTS[i];
    }
    return null;
}

// ---- hex <-> rgb ---------------------------------------------------------------------------------
// Accepts "#rrggbb", "rrggbb" and QML's "#aarrggbb" (the alpha is dropped).
function parse(hex) {
    var h = String(hex || "").replace("#", "");
    if (h.length === 8)
        h = h.slice(2);
    if (!/^[0-9a-fA-F]{6}$/.test(h))
        return null;
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

function isHex(text) {
    return /^#?[0-9a-fA-F]{6}$/.test(String(text || "").trim());
}

function normalize(text) {
    var t = String(text || "").trim().toLowerCase();
    if (/^#?[0-9a-f]{3}$/.test(t)) {
        var s = t.replace("#", "");
        t = "#" + s[0] + s[0] + s[1] + s[1] + s[2] + s[2];
    }
    if (t.length > 0 && t[0] !== "#")
        t = "#" + t;
    return /^#[0-9a-f]{6}$/.test(t) ? t : "";
}

function byte2(v) {
    var s = Math.round(Math.max(0, Math.min(255, v))).toString(16);
    return s.length < 2 ? "0" + s : s;
}

function toHex(rgb) {
    return "#" + byte2(rgb[0]) + byte2(rgb[1]) + byte2(rgb[2]);
}

function withAlpha(hex, a) {
    var rgb = parse(hex);
    return rgb ? "#" + byte2(a * 255) + byte2(rgb[0]) + byte2(rgb[1]) + byte2(rgb[2]) : hex;
}

// ---- WCAG ---------------------------------------------------------------------------------------
function luminance(hex) {
    var rgb = parse(hex);
    if (!rgb)
        return 0;
    var ch = function (c) {
        var v = c / 255;
        return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * ch(rgb[0]) + 0.7152 * ch(rgb[1]) + 0.0722 * ch(rgb[2]);
}

function contrast(a, b) {
    var x = luminance(a), y = luminance(b);
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

function ink(hex) {
    return contrast(hex, INK_DARK) >= contrast(hex, INK_LIGHT) ? INK_DARK : INK_LIGHT;
}

// ---- OKLCH (Björn Ottosson's OKLab) -----------------------------------------------------------------
function lin(c) {
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

function gam(c) {
    return c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
}

function oklch(hex) {
    var rgb = parse(hex) || [0, 0, 0];
    var r = lin(rgb[0] / 255), g = lin(rgb[1] / 255), b = lin(rgb[2] / 255);
    var l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    var m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    var s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    var L = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s;
    var A = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
    var B = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
    return [L, Math.hypot(A, B), ((Math.atan2(B, A) * 180) / Math.PI + 360) % 360];
}

function toLinear(L, C, H) {
    var a = C * Math.cos((H * Math.PI) / 180), b = C * Math.sin((H * Math.PI) / 180);
    var l = Math.pow(L + 0.3963377774 * a + 0.2158037573 * b, 3);
    var m = Math.pow(L - 0.1055613458 * a - 0.0638541728 * b, 3);
    var s = Math.pow(L - 0.0894841775 * a - 1.291485548 * b, 3);
    return [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s];
}

function inGamut(v) {
    return v[0] >= -1e-4 && v[0] <= 1 + 1e-4 && v[1] >= -1e-4 && v[1] <= 1 + 1e-4 && v[2] >= -1e-4 && v[2] <= 1 + 1e-4;
}

// OKLCH -> "#rrggbb"; out of gamut: chroma shrinks (hue and lightness kept).
// `steps`: bisection steps (24 = the mascot reference runtime, 32 = the CLI).
function fromOklch(L, C, H, steps) {
    L = Math.max(0, Math.min(1, L));
    C = Math.max(0, C);
    var rgb = toLinear(L, C, H);
    if (!inGamut(rgb)) {
        var lo = 0, hi = C, n = steps || 24;
        for (var i = 0; i < n; i++) {
            var mid = (lo + hi) / 2;
            if (inGamut(toLinear(L, mid, H)))
                lo = mid;
            else
                hi = mid;
        }
        rgb = toLinear(L, lo, H);
    }
    return toHex([0, 1, 2].map(function (k) {
        return Math.min(1, Math.max(0, gam(Math.min(1, Math.max(0, rgb[k]))))) * 255;
    }));
}

// ---- accent resolution (preview; the CLI writes the real tokens) --------------------------------------------
// Keep hue and chroma, move lightness just far enough for `minimum` contrast against `surface`.
function fitContrast(hex, surface, minimum) {
    var min = minimum || MIN_CONTRAST;
    if (contrast(hex, surface) >= min)
        return { color: hex, adjusted: false };
    var lch = oklch(hex);
    var lighterFirst = contrast(surface, "#ffffff") >= contrast(surface, "#000000");
    var best = hex;
    var dirs = [lighterFirst, !lighterFirst];
    for (var d = 0; d < 2; d++) {
        var end = dirs[d] ? 1 : 0;
        var endColor = fromOklch(end, lch[1], lch[2], 32);
        if (contrast(endColor, surface) < min) {
            if (contrast(endColor, surface) > contrast(best, surface))
                best = endColor;
            continue;
        }
        var lo = lch[0], hi = end;
        for (var i = 0; i < 40; i++) {
            var mid = (lo + hi) / 2;
            if (contrast(fromOklch(mid, lch[1], lch[2], 32), surface) >= min)
                hi = mid;
            else
                lo = mid;
        }
        return { color: fromOklch(hi, lch[1], lch[2], 32), adjusted: true };
    }
    return { color: best, adjusted: true };
}

function strong(hex, mode) {
    var lch = oklch(hex);
    var step = mode === "light" ? -0.06 : 0.06;
    if (lch[0] + step < 0 || lch[0] + step > 1)
        step = -step;
    return fromOklch(lch[0] + step, lch[1], lch[2], 32);
}

// choice: an accent id or "#rrggbb"; surface: the base theme's `surface` color.
function resolveAccent(choice, mode, surface) {
    var known = accentById(choice);
    var requested = known ? (mode === "light" ? known.light : known.dark) : normalize(choice);
    if (!requested)
        requested = mode === "light" ? ACCENTS[0].light : ACCENTS[0].dark;
    var fit = fitContrast(requested, surface, MIN_CONTRAST);
    return {
        id: known ? known.id : "custom",
        requested: requested,
        color: fit.color,
        adjusted: fit.adjusted,
        contrast: contrast(fit.color, surface),
        soft: withAlpha(fit.color, mode === "light" ? 0.09 : 0.14),
        strong: strong(fit.color, mode),
        ink: ink(fit.color)
    };
}

// ---- mascot (design/mascot/jackson.js, DESIGN §13) --------------------------------------------------------
var OUTFIT_L = { dark: [0.32, 0.25, 0.40], light: [0.45, 0.36, 0.56] };
var OUTFIT_CMAX = { dark: 0.075, light: 0.11 };

// dark oranges/yellows turn to mud-brown: up to 40 % less chroma, a smooth dip around hue 75° (±40°)
function outfitCmax(H, mode) {
    var d = ((H - 75 + 180) % 360 + 360) % 360 - 180;
    var band = Math.abs(d) < 40 ? Math.cos((d / 40) * Math.PI / 2) : 0;
    return OUTFIT_CMAX[mode] * (1 - 0.4 * band);
}

function outfitFor(hex, mode) {
    var lch = oklch(hex);
    var c = Math.min(lch[1], outfitCmax(lch[2], mode));
    var l = OUTFIT_L[mode];
    return {
        outfit: fromOklch(l[0], c, lch[2], 24),
        outfitShade: fromOklch(l[1], c, lch[2], 24),
        outfitLight: fromOklch(l[2], c, lch[2], 24)
    };
}

function detailFor(hex) {
    var lch = oklch(hex);
    var L = lch[0];
    return {
        detail: hex,
        detailShade: fromOklch(Math.max(0, L + (L > 0.45 ? -0.13 : -0.08)), lch[1], lch[2], 24),
        detailLight: fromOklch(L + Math.min(0.12, 0.97 - L), lch[1], lch[2], 24)
    };
}
