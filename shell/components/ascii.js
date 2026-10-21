// SPDX-License-Identifier: Apache-2.0
// SOS ASCII in JavaScript: the twin of cli/svoya_cli/ascii (engine.py, eye.py, planets.py,
// jackson.py) for the shell (AsciiView.qml) and the browser (assets/newtab). Same hash, same
// curves, same frames: shell/tools/test_ascii.js draws them against the Python golden frames in
// cli/tests/golden/ascii. Plain functions, no modules and no `.pragma`, so one file loads in QML
// (import "ascii.js" as Ascii) and in a page (<script src="…/components/ascii.js">).
//
// A canvas is {w, h, ch: [chars], co: Uint8Array} with color slots 0 empty, 1 phosphor,
// 2 the alive accent (the pupil's rim, Jackson's eyes, an error), 3 grey noise.

var ASCII_ASPECT = 2.0;
var ASCII_RAMP = " .:-=+*#%@";
var ASCII_FINE = " .,:;-~=+*xoO#%@";
var ASCII_GLYPHS = "01<>/\\{}[]#$%&*+=?~^";
var ASCII_STROKE = "-\\|/";
var BG = 0, FG = 1, ACCENT = 2, NOISE = 3;
var ASCII_STORY_LEN = 14.0;
var ASCII_STORY_LINE = "> LOOK CLOSER";
var ASCII_ZOOM_MAX = 22.0;
var ASCII_FLASH_GAP = 0.5;

function asciiTrunc(x) { return x < 0 ? Math.ceil(x) : Math.floor(x); }
function asciiMod(a, b) { return ((a % b) + b) % b; }
function asciiClamp(v, lo, hi) {
    if (lo === undefined) lo = 0.0;
    if (hi === undefined) hi = 1.0;
    return v < lo ? lo : v > hi ? hi : v;
}
function asciiEase(t) { t = asciiClamp(t); return t * t * (3.0 - 2.0 * t); }
function asciiEaseIn(t) { t = asciiClamp(t); return t * t * t; }
function asciiEaseOut(t) { t = 1.0 - asciiClamp(t); return 1.0 - t * t * t; }

function asciiHash(i, j, k) {
    var h = (Math.imul(i, 374761393) + Math.imul(j, 668265263) + Math.imul(k || 0, 2246822519 | 0)) >>> 0;
    h = Math.imul(h ^ (h >>> 13), 1274126177) >>> 0;
    return (h ^ (h >>> 16)) >>> 0;
}
function asciiRnd(i, j, k) { return (asciiHash(i, j, k) & 0xFFFF) / 65536.0; }

// ---- canvas ------------------------------------------------------------------------------------
function asciiCanvas(w, h) {
    var c = { w: w, h: h, ch: new Array(w * h), co: new Uint8Array(w * h) };
    for (var k = 0; k < w * h; k++) c.ch[k] = " ";
    return c;
}
function asciiFill(cv, ch, co) {
    var n = cv.w * cv.h;
    for (var k = 0; k < n; k++) {
        cv.ch[k] = ch ? ch[k] : " ";
        cv.co[k] = co ? co[k] : BG;
    }
}
function asciiPut(cv, x, y, c, slot) {
    if (x >= 0 && x < cv.w && y >= 0 && y < cv.h) {
        var i = y * cv.w + x;
        cv.ch[i] = c;
        cv.co[i] = c !== " " ? (slot === undefined ? FG : slot) : BG;
    }
}
function asciiText(cv, x, y, s, slot) {
    for (var k = 0; k < s.length; k++) asciiPut(cv, x + k, y, s[k], slot);
}
function asciiLines(cv) {
    var out = [];
    for (var r = 0; r < cv.h; r++) out.push(cv.ch.slice(r * cv.w, (r + 1) * cv.w).join(""));
    return out;
}
function asciiColorLines(cv) {
    var letters = " fan", out = [];
    for (var r = 0; r < cv.h; r++) {
        var s = "";
        for (var i = r * cv.w; i < (r + 1) * cv.w; i++) s += letters[cv.co[i]];
        out.push(s);
    }
    return out;
}
// runs of one color in a row, for a renderer that draws text: [[x, "text", slot], ...]
function asciiRuns(cv, r) {
    var runs = [], start = -1, slot = -1, text = "";
    for (var x = 0; x < cv.w; x++) {
        var i = r * cv.w + x, c = cv.ch[i], s = cv.co[i];
        if (c === " ") {
            if (start >= 0) { runs.push([start, text, slot]); start = -1; }
            continue;
        }
        if (start >= 0 && s === slot) { text += c; continue; }
        if (start >= 0) runs.push([start, text, slot]);
        start = x; slot = s; text = c;
    }
    if (start >= 0) runs.push([start, text, slot]);
    return runs;
}

function asciiStroke(theta) {
    return ASCII_STROKE[asciiTrunc((asciiMod(theta, Math.PI) + Math.PI / 8) / (Math.PI / 4)) % 4];
}
function asciiBisectRight(a, x) {
    var lo = 0, hi = a.length;
    while (lo < hi) { var mid = (lo + hi) >> 1; if (x < a[mid]) hi = mid; else lo = mid + 1; }
    return lo;
}

// ---- Jackson in symbols (jackson.py) -----------------------------------------------------------
var ASCII_ROLE = {
    outline: [0.50, FG], skin: [0.62, FG], skinLight: [0.78, FG], skinShade: [0.46, FG],
    outfit: [0.30, FG], outfitLight: [0.42, FG], outfitShade: [0.20, FG], undershirt: [0.55, FG],
    detail: [0.86, FG], detailLight: [0.96, FG], detailShade: [0.70, FG],
    headphones: [0.28, FG], headphonesLight: [0.42, FG], led: [0.90, ACCENT],
    white: [0.95, FG], mouth: [0.55, ACCENT], tongue: [0.70, ACCENT], blush: [0.45, ACCENT],
    eyesTinted: [0.85, ACCENT], frame: [0.40, FG], lens: [0.12, FG], lensGlint: [0.95, FG],
    lensHighlight: [0.80, FG], sweat: [0.80, FG]
};
var ASCII_EDGE = {
    "1100": '"', "0011": "_", "1010": "|", "0101": "|", "1001": "\\", "0110": "/", "0111": "/",
    "1011": "\\", "1101": "\\", "1110": "/", "1000": "'", "0100": "'", "0010": ",", "0001": "."
};

function asciiCompose(data, opts, state) {
    var n = data.size, o = {}, key, k;
    for (key in data.defaults) o[key] = data.defaults[key];
    for (key in (opts || {})) if (key in data.defaults) o[key] = opts[key];
    o.state = state;
    var derive = data.derive || {};
    for (key in derive) {
        var rules = derive[key];
        for (k = 0; k < rules.length; k++) {
            var when = rules[k].when || {}, ok = true;
            for (var wk in when) if (o[wk] !== when[wk]) { ok = false; break; }
            if (ok) { o[key] = rules[k].value; break; }
        }
    }
    var skins = data.skins, skin = skins[o.skin];
    if (!skin) for (key in skins) { skin = skins[key]; break; }
    var grid = [];
    for (var y = 0; y < n; y++) { grid.push(new Array(n)); for (var x = 0; x < n; x++) grid[y][x] = null; }
    function fmt(s) { return s.replace(/\{(\w+)\}/g, function (m, name) { return String(o[name]); }); }
    function match(when) {
        for (var wk in when) {
            var v = when[wk];
            if (Array.isArray(v) ? v.indexOf(o[wk]) < 0 : o[wk] !== v) return false;
        }
        return true;
    }
    function draw(rows) {
        for (var yy = 0; yy < rows.length; yy++)
            for (var xx = 0; xx < rows[yy].length; xx++)
                if (rows[yy][xx] !== ".") grid[yy][xx] = rows[yy][xx];
    }
    for (var s = 0; s < data.compose.length; s++) {
        var step = data.compose[s];
        if (step.when && !match(step.when)) continue;
        if (step.skinFlag && (skin.flags || []).indexOf(step.skinFlag) < 0) continue;
        if (step.outline) {
            var add = [];
            for (var yy = 0; yy < n; yy++) for (var xx = 0; xx < n; xx++) {
                if (grid[yy][xx] !== null) continue;
                if ((xx + 1 < n && grid[yy][xx + 1] !== null) || (xx > 0 && grid[yy][xx - 1] !== null) ||
                    (yy + 1 < n && grid[yy + 1][xx] !== null) || (yy > 0 && grid[yy - 1][xx] !== null))
                    add.push([xx, yy]);
            }
            for (k = 0; k < add.length; k++) grid[add[k][1]][add[k][0]] = step.outline;
        } else if (step.state) {
            draw(data.states[state] || data.states.idle);
        } else if (step.tint) {
            var layer = data.layers[fmt(step.tint)];
            if (layer) {
                var keys = data.tint.keys, to = data.tint.to;
                for (var ty = 0; ty < layer.length; ty++)
                    for (var tx = 0; tx < layer[ty].length; tx++) {
                        var c = layer[ty][tx];
                        if (c !== ".") grid[ty][tx] = keys.indexOf(grid[ty][tx]) >= 0 ? to : c;
                    }
            }
        } else {
            var name = fmt(step.layer);
            if (data.layers[name]) draw(data.layers[name]);
        }
    }
    return grid;
}

function asciiJackson(data, opts, state, cols) {
    var grid = asciiCompose(data, opts, state), n = grid.length, x, y;
    var cov = [], lum = [], slot = [];
    for (y = 0; y < n; y++) {
        cov.push(new Array(n).fill(0.0)); lum.push(new Array(n).fill(0.0)); slot.push(new Array(n).fill(FG));
        for (x = 0; x < n; x++) {
            var key = grid[y][x];
            if (key === null) continue;
            var name = data.slots[key] || "", role = ASCII_ROLE[name] || [0.5, FG], v = role[0], s = role[1];
            if (name === "outline" && x + 1 < n && x > 0 && y + 1 < n && y > 0 && grid[y][x + 1] !== null &&
                grid[y][x - 1] !== null && grid[y + 1][x] !== null && grid[y - 1][x] !== null) {
                v = 0.85; s = ACCENT;
            }
            cov[y][x] = 1.0; lum[y][x] = v; slot[y][x] = s;
        }
    }
    function at(m, yy, xx) { return m[Math.min(n - 1, Math.max(0, yy))][Math.min(n - 1, Math.max(0, xx))]; }
    var smooth = cov;
    if (cols > n * 0.75) {
        var hz = [], kk = [0.25, 0.5, 0.25];
        for (y = 0; y < n; y++) { hz.push([]); for (x = 0; x < n; x++) hz[y].push(kk[0] * at(cov, y, x - 1) + kk[1] * at(cov, y, x) + kk[2] * at(cov, y, x + 1)); }
        smooth = [];
        for (y = 0; y < n; y++) { smooth.push([]); for (x = 0; x < n; x++) smooth[y].push(kk[0] * at(hz, y - 1, x) + kk[1] * at(hz, y, x) + kk[2] * at(hz, y + 1, x)); }
    }
    var rows = Math.max(1, Math.floor(cols / 2)), sx = n / cols, sy = n / rows, out = [];
    function sample(m, fx, fy) {
        var xx = Math.min(n - 1.001, Math.max(0.0, fx - 0.5)), yy = Math.min(n - 1.001, Math.max(0.0, fy - 0.5));
        var x0 = asciiTrunc(xx), y0 = asciiTrunc(yy), ax = xx - x0, ay = yy - y0;
        return m[y0][x0] * (1 - ax) * (1 - ay) + m[y0][x0 + 1] * ax * (1 - ay) + m[y0 + 1][x0] * (1 - ax) * ay + m[y0 + 1][x0 + 1] * ax * ay;
    }
    var pts = [[0.25, 0.25], [0.75, 0.25], [0.25, 0.75], [0.75, 0.75]];
    for (var r = 0; r < rows; r++) for (var c = 0; c < cols; c++) {
        var x0 = c * sx, y0 = r * sy, q = "", any = false, all = true;
        for (var p = 0; p < 4; p++) {
            var on = sample(smooth, x0 + pts[p][0] * sx, y0 + pts[p][1] * sy) > 0.5;
            q += on ? "1" : "0"; any = any || on; all = all && on;
        }
        if (!any) continue;
        var px = Math.min(n - 1, asciiTrunc(x0 + sx / 2)), py = Math.min(n - 1, asciiTrunc(y0 + sy / 2));
        var ch;
        if (all) {
            var lv = cov[py][px] ? lum[py][px] : 0.5;
            ch = ASCII_FINE[Math.max(1, asciiTrunc(lv * 15.999))];
        } else {
            ch = ASCII_EDGE[q] || ".";
        }
        out.push([c, r, ch, cov[py][px] ? slot[py][px] : FG]);
    }
    return out;
}

// ---- the eye (eye.py) --------------------------------------------------------------------------
// opts: {state, hud, seed, night, story, clock, sprite (Jackson's JSON), look}
function AsciiEye(opts) {
    opts = opts || {};
    var state = opts.state || "idle", seed = opts.seed === undefined ? 7 : opts.seed;
    this.mode = (state === "idle" || state === "thinking" || state === "listening") ? state : "idle";
    this.recurring = (state === "done" || state === "error") ? state : null;
    this.story = !!opts.story;
    this.hud = opts.hud !== false && !this.story;
    this.duration = this.story ? ASCII_STORY_LEN : null;
    this.stillAt = this.story ? 2.4 : 2.2;
    this.night = !!opts.night;
    this.clock = opts.clock || null;
    this.sprite = opts.sprite || null;
    this.look = opts.look || {};
    this.jcache = {};
    this.events = [];
    this.mouse = null;
    this.gCur = [0.0, 0.0];
    this.lastT = null;
    this.wantsMouse = true;
    this.blinks = [];
    var t = 1.5, k = 0;
    while (t < 3600) { this.blinks.push(t); t += 4.0 + 3.0 * asciiRnd(k, seed, 31); k++; }
    this.saccades = [[0.0, [0.0, 0.0]]];
    t = 0.8; k = 0;
    while (t < 3600) {
        var tgt;
        if (asciiRnd(k, seed, 32) < 0.35) {
            tgt = [-0.15 + 0.3 * asciiRnd(k, seed, 33), -0.15 + 0.3 * asciiRnd(k, seed, 34)];
        } else {
            var ang = 2 * Math.PI * asciiRnd(k, seed, 35), rad = 0.45 + 0.55 * asciiRnd(k, seed, 36);
            tgt = [Math.cos(ang) * rad, Math.sin(ang) * rad * 0.8];
        }
        this.saccades.push([t, tgt]);
        t += 0.9 + 2.3 * asciiRnd(k, seed, 37);
        k++;
    }
    this.saccadeT = this.saccades.map(function (s) { return s[0]; });
    this.w = this.h = 0;
}

AsciiEye.prototype.resize = function (w, h) {
    this.w = w; this.h = h;
    this.tiny = w < 24 || h < 9;
    this.narrow = w < 80;
    this.top = this.hud && !this.tiny ? 1 : 0;
    var rows = h - 2 * this.top, n = w * h;
    this.cx = w / 2.0;
    this.cy = (this.top + rows / 2.0) * ASCII_ASPECT;
    this.b = Math.min(rows * ASCII_ASPECT * 0.40, w * 0.45 * 0.46);
    this.a = this.b / 0.46;
    this.R = this.b * 0.86;
    this.r0 = this.R * 0.36;
    this.gmax = [Math.max(0.0, this.a - this.R * 1.15), this.b * 0.32];
    this.bgCh = new Array(n); this.bgCo = new Uint8Array(n);
    this.grain = new Float64Array(n);
    for (var i = 0; i < n; i++) {
        this.bgCh[i] = " ";
        this.grain[i] = asciiRnd(i, 7, 2);
        if (!this.narrow && !this.story) {
            var v = asciiRnd(i, 3, 1);
            if (v < 0.02) { this.bgCh[i] = v < 0.013 ? "·" : "."; this.bgCo[i] = NOISE; }
        }
    }
    this.scratch = asciiCanvas(w, h);
};

AsciiEye.prototype.key = function (k, t) {
    if (k === "1" || k === "2" || k === "3") this.mode = ["idle", "thinking", "listening"][parseInt(k) - 1];
    else if (k === "4" || k === "5" || k === "enter") this.trigger(k === "5" ? "error" : "done", t);
    else if (k === "b" || k === "B" || k === "и" || k === "И" || k === "space") this.events.push(["blink", t]);
    else return ["q", "Q", "esc", "й", "Й"].indexOf(k) < 0;
    return true;
};
AsciiEye.prototype.trigger = function (kind, t) {
    for (var i = 0; i < this.events.length; i++) {
        var e = this.events[i];
        if ((e[0] === "done" || e[0] === "error") && t - e[1] >= 0 && t - e[1] < ASCII_FLASH_GAP) return false;
    }
    this.events.push([kind, t]);
    return true;
};
AsciiEye.prototype.pointer = function (x, y, t) { this.mouse = [x + 0.5, (y + 0.5) * ASCII_ASPECT, t]; };
AsciiEye.prototype.lastEvent = function (kind, t) {
    var best = null;
    for (var i = 0; i < this.events.length; i++) {
        var e = this.events[i];
        if (e[0] === kind && e[1] <= t && (best === null || e[1] > best)) best = e[1];
    }
    if (this.recurring === kind && t >= 1.0) {
        var te = 1.0 + 4.0 * Math.floor((t - 1.0) / 4.0);
        best = best === null ? te : Math.max(best, te);
    }
    return best === null ? null : t - best;
};
function asciiBlinkShape(p) {
    return p < 0.11 ? 1 - asciiEaseIn(p / 0.11) : p < 0.15 ? 0.0 : asciiEaseOut((p - 0.15) / 0.15);
}
AsciiEye.prototype.openness = function (t) {
    var times = [], k = asciiBisectRight(this.blinks, t), i;
    if (k) times.push(this.blinks[k - 1]);
    for (i = 0; i < this.events.length; i++) if (this.events[i][0] === "blink") times.push(this.events[i][1]);
    var d = this.lastEvent("done", t);
    if (d !== null) times.push(t - d + 0.42);
    var o = 1.0;
    for (i = 0; i < times.length; i++) {
        var p = t - times[i];
        if (p >= 0 && p < 0.30) o = Math.min(o, asciiBlinkShape(p));
    }
    return o;
};
AsciiEye.prototype.gaze = function (t) {
    var gx = this.gmax[0], gy = this.gmax[1];
    if (this.mouse && t - this.mouse[2] >= 0 && t - this.mouse[2] < 4.0) {
        var nx = asciiClamp((this.mouse[0] - this.cx) / Math.max(1.0, this.a * 0.8), -1.0, 1.0);
        var ny = asciiClamp((this.mouse[1] - this.cy) / Math.max(1.0, this.b * 1.2), -1.0, 1.0);
        var step = this.lastT === null ? 1.0 : asciiClamp((t - this.lastT) * 14.0);
        this.gCur = [this.gCur[0] + (nx * gx - this.gCur[0]) * step, this.gCur[1] + (ny * gy - this.gCur[1]) * step];
        return this.gCur;
    }
    var k = asciiBisectRight(this.saccadeT, t) - 1;
    var t0 = this.saccades[k][0], p1 = this.saccades[k][1], p0 = k ? this.saccades[k - 1][1] : p1;
    var e = asciiEase((t - t0) / 0.16), jx = 0.25 * Math.sin(t * 7.1) * Math.sin(t * 2.3);
    this.gCur = [(p0[0] + (p1[0] - p0[0]) * e) * gx + jx, (p0[1] + (p1[1] - p0[1]) * e) * gy];
    return this.gCur;
};
AsciiEye.prototype.storyAt = function (t) {
    var s = { open: 1.0, g: [0.0, 0.0], z: 1.0, inside: 0.0, cat: 0.0, pose: "idle", text: 0, textFade: 0.0 };
    var gx = this.gmax[0], gy = this.gmax[1];
    s.open = asciiEase((t - 0.3) / 1.0);
    [3.1, 12.5].forEach(function (tb) {
        var p = t - tb;
        if (p >= 0 && p < 0.30) s.open = Math.min(s.open, asciiBlinkShape(p));
    });
    if (t >= 13.25) s.open = 1 - asciiEase((t - 13.25) / 0.45);
    var look = [[0.0, [0.35, -0.1]], [1.0, [0.0, 0.0]], [2.0, [-0.5, 0.25]], [2.6, [0.0, 0.0]]], k = 0;
    for (var i = 0; i < look.length; i++) if (look[i][0] <= Math.max(t, 0.0)) k = i;
    var p0 = k ? look[k - 1][1] : look[0][1], e = asciiEase((t - look[k][0]) / 0.16);
    s.g = [(p0[0] + (look[k][1][0] - p0[0]) * e) * gx, (p0[1] + (look[k][1][1] - p0[1]) * e) * gy];
    if (t >= 3.7 && t < 6.0) {
        s.z = Math.exp(Math.log(ASCII_ZOOM_MAX) * asciiEaseIn((t - 3.7) / 2.3));
    } else if (t >= 6.0 && t < 10.0) {
        s.z = ASCII_ZOOM_MAX;
        s.inside = Math.min(asciiEase((t - 6.0) / 0.4), 1 - asciiEase((t - 9.6) / 0.4));
        s.cat = Math.min(asciiEase((t - 6.4) / 0.6), 1 - asciiEase((t - 9.3) / 0.5));
        if (t >= 7.1 && t < 7.35) s.pose = "blink";
        else if (t >= 7.5 && t < 8.7) s.pose = asciiTrunc((t - 7.5) / 0.14) % 2 === 0 ? "talk1" : "talk2";
        else if (t >= 8.7) s.pose = "happy";
    } else if (t >= 10.0 && t < 12.0) {
        s.z = Math.exp(Math.log(ASCII_ZOOM_MAX) * (1 - asciiEaseOut((t - 10.0) / 2.0)));
    }
    if (t < 1.6) {
        var n = ASCII_STORY_LINE.length;
        s.text = t > 0.05 ? Math.min(n, asciiTrunc(Math.max(0.0, t - 0.05) / 0.055) + 1) : 0;
        s.textFade = asciiEase((t - 1.25) / 0.35);
    }
    return s;
};
AsciiEye.prototype.pupil = function (t) {
    var r = this.r0 * (this.night ? 1.22 : 1.0);
    if (this.mode === "listening" && !this.story) {
        var env = asciiClamp(0.5 + 0.5 * Math.sin(t * 7.3) * Math.sin(t * 2.1 + 1.0) + 0.2 * Math.sin(t * 13.7));
        r *= 1.0 + 0.16 * env;
    }
    var d = this.lastEvent("done", t);
    if (d !== null && d < 1.6) r *= 1.0 - 0.28 * (d < 0.15 ? asciiEase(d / 0.15) : 1 - asciiEase((d - 0.15) / 1.45));
    return r;
};
AsciiEye.prototype.draw = function (cv, t) {
    if (cv.w !== this.w || cv.h !== this.h) this.resize(cv.w, cv.h);
    asciiFill(cv, this.bgCh, this.bgCo);
    if (this.tiny) { this.drawTiny(cv, t); this.lastT = t; return; }
    var frame = asciiTrunc(t * 30);
    if (this.story) {
        var s = this.storyAt(t);
        if (s.inside > 0 || (t >= 6.0 && t < 10.0)) this.drawInside(cv, t, s);
        else this.drawEye(cv, t, frame, s.open, s.g, this.pupil(t), s.z, false);
        if (s.text) this.drawLine(cv, s);
        this.lastT = t;
        return;
    }
    var op = this.openness(t), g = this.gaze(t), rp = this.pupil(t), err = this.lastEvent("error", t);
    if (err !== null && err < 1.25) {
        this.drawError(cv, t, frame, err, op, g, rp);
    } else {
        this.drawEye(cv, t, frame, op, g, rp, 1.0, this.mode === "thinking");
        var done = this.lastEvent("done", t);
        if (done !== null && done < 0.35) this.flash(cv, g, rp, 1 - asciiEase(done / 0.35));
    }
    if (this.hud) this.drawHud(cv, t);
    this.lastT = t;
};
AsciiEye.prototype.drawEye = function (cv, t, frame, op, g, rp, z, thinking) {
    var w = cv.w, h = cv.h, ch = cv.ch, co = cv.co, A = ASCII_ASPECT;
    var cx = this.cx, cy = this.cy, a = this.a * z, b = this.b * z, R = this.R * z;
    rp *= z;
    var icx = cx + g[0] * z, icy = cy + g[1] * z;
    var breath = 1.0 + 0.07 * Math.sin(t * 2 * Math.PI / 6.4), narrow = this.narrow;
    var up = new Array(w), lo = new Array(w), i, j, k, u, y;
    for (i = Math.max(0, asciiTrunc(cx - a)); i < Math.min(w, asciiTrunc(cx + a) + 1); i++) {
        u = (i + 0.5 - cx) / a;
        if (u * u >= 1) continue;
        var sh = Math.pow(1 - u * u, 0.8), yc = cy + b * 0.30 * sh;
        up[i] = yc + (cy - b * sh - yc) * op;
        lo[i] = yc + (cy + b * 0.88 * sh - yc) * op;
    }
    var grain = this.grain;
    for (i = 0; i < w; i++) {
        var yu = up[i];
        if (yu === undefined) continue;
        var yl = lo[i], span = yl - yu;
        if (span <= 0.5) continue;
        u = (i + 0.5 - cx) / a;
        var side = Math.pow(1 - u * u, 0.5);
        for (j = Math.max(0, asciiTrunc(yu / A)); j < Math.min(h - 1, asciiTrunc(yl / A)) + 1; j++) {
            y = (j + 0.5) * A;
            if (!(yu < y && y < yl)) continue;
            k = j * w + i;
            var v = (0.10 + 0.24 * side * Math.pow(Math.sin(Math.PI * (y - yu) / span), 0.7)) * breath + (grain[k] - 0.5) * 0.14;
            if (v > 0.2) { ch[k] = ASCII_FINE[Math.min(5, asciiTrunc(v * 15.999))]; co[k] = NOISE; }
        }
    }
    var rot = thinking ? t * 0.9 : 0.0, fa = narrow ? 19 : 34, fb = narrow ? 5 : 7;
    var rc = R ? rp / R + 0.16 : 0.5, ring = 1.6 * Math.max(1.0, Math.pow(z, 0.5));
    var hx = icx - 0.30 * R, hy = icy - 0.34 * R, hr = Math.max(1.3, 0.15 * R);
    var ia = Math.max(0, asciiTrunc(icx - R)), ib = Math.min(w, asciiTrunc(icx + R) + 2);
    var ja = Math.max(0, asciiTrunc((icy - R) / A)), jb = Math.min(h, asciiTrunc((icy + R) / A) + 2), R2 = R * R;
    for (j = ja; j < jb; j++) {
        y = (j + 0.5) * A;
        var dy = y - icy, dy2 = dy * dy, base = j * w;
        for (i = ia; i < ib; i++) {
            var yu2 = up[i];
            if (yu2 === undefined || !(yu2 < y && y < lo[i])) continue;
            var dx = i + 0.5 - icx, d2 = dx * dx + dy2;
            if (d2 > R2) continue;
            k = base + i;
            var hd = Math.sqrt((i + 0.5 - hx) * (i + 0.5 - hx) + (y - hy) * (y - hy));
            if (hd < hr) { ch[k] = hd < hr * 0.45 ? "@" : hd < hr * 0.75 ? "O" : "o"; co[k] = FG; continue; }
            var d = Math.sqrt(d2);
            if (d < rp) { ch[k] = " "; co[k] = BG; continue; }
            if (d < rp + ring) {
                var q = (d - rp) / ring;
                ch[k] = q < 0.4 ? "#" : q < 0.75 ? "*" : "+"; co[k] = ACCENT;
                continue;
            }
            var rho = d / R;
            if (rho > 0.9) {
                var vv = asciiRnd(i, j, asciiTrunc(frame / 3));
                ch[k] = vv < 0.4 ? ":" : vv < 0.75 ? "." : " "; co[k] = FG;
                continue;
            }
            var th = Math.atan2(dy, dx);
            var f = 0.5 + 0.5 * Math.sin(th * fa + 1.5 * Math.sin(th * fb + rho * 4.0) + rot);
            var f2 = narrow ? 0.5 : 0.5 + 0.5 * Math.sin(th * 53 - rho * 9.0 - rot * 0.6);
            var fib = (0.72 * f + 0.28 * f2) * breath * (1.0 - 0.35 * asciiClamp((rho - 0.65) / 0.25));
            if (Math.abs(rho - rc) < 0.05) { ch[k] = fib > 0.45 ? "o" : "*"; co[k] = FG; }
            else if (fib > 0.6) { ch[k] = asciiStroke(th); co[k] = FG; }
            else if (fib > 0.36) { ch[k] = ASCII_FINE[3 + asciiTrunc((fib - 0.36) / 0.24 * 4.99)]; co[k] = FG; }
            else if (fib > 0.24) { ch[k] = "."; co[k] = FG; }
            else { ch[k] = " "; co[k] = BG; }
        }
    }
    if (op > 0.5) asciiPut(cv, asciiTrunc(icx + 0.40 * R), asciiTrunc((icy + 0.30 * R) / A), ".", FG);
    if (thinking) this.thinkingRing(cv, t, icx, icy, R, up, lo);
    var lash = !narrow && z < 1.5, crease = !narrow && z < 1.5 && op > 0.3;
    for (i = 0; i < w; i++) {
        var yu3 = up[i];
        if (yu3 === undefined) continue;
        u = (i + 0.5 - cx) / a;
        var yl3 = lo[i];
        var su = ((up[i + 1] !== undefined ? up[i + 1] : yu3) - (up[i - 1] !== undefined ? up[i - 1] : yu3)) / (2 * A);
        var sl = ((lo[i + 1] !== undefined ? lo[i + 1] : yl3) - (lo[i - 1] !== undefined ? lo[i - 1] : yl3)) / (2 * A);
        var corner = Math.abs(u) > 0.965 ? (u < 0 ? "<" : ">") : null;
        asciiLidmark(cv, i, yu3, su, "upper", corner, corner === "<" ? ACCENT : FG);
        if (op > 0.08 && !corner) asciiLidmark(cv, i, yl3, sl, "lower", null, FG);
        if (crease && Math.abs(u) < 0.7) {
            var yk = yu3 - (b * 0.20 * Math.pow(1 - u * u, 0.5) + 2.4) * (0.6 + 0.4 * op);
            asciiLidmark(cv, i, yk, su * 0.9, "crease", null, NOISE);
        }
        if (lash && i % 3 === 0 && Math.abs(u) > 0.25 && Math.abs(u) < 0.92) {
            var nl = 1 + (Math.abs(u) > 0.40 && Math.abs(u) < 0.85 ? 1 : 0);
            var top = asciiTrunc(yu3 / A) - 1, lean = u < -0.22 ? -1 : u > 0.22 ? 1 : 0;
            var lc = lean < 0 ? "\\" : lean > 0 ? "/" : "|";
            for (var m = 0; m < nl; m++) asciiPut(cv, i + lean * m, top - m, lc, FG);
        }
        if (asciiRnd(i, frame, 5) < 0.08) {
            var jj = asciiTrunc(yu3 / A) - 2 - asciiTrunc(asciiRnd(i, frame, 6) * 3);
            if (jj >= 0 && jj < h && ch[jj * w + i] === " ") { ch[jj * w + i] = "."; co[jj * w + i] = NOISE; }
        }
    }
};
function asciiLidmark(cv, i, y, slope, kind, corner, slot) {
    var j = asciiTrunc(y / ASCII_ASPECT), frac = y / ASCII_ASPECT - j, c;
    if (corner) c = corner;
    else if (Math.abs(slope) >= 1.4) c = "|";
    else if (Math.abs(slope) >= 0.32) c = slope < 0 ? "/" : "\\";
    else if (kind === "upper") c = frac > 0.62 ? "_" : frac > 0.3 ? "=" : '"';
    else c = frac > 0.62 ? "_" : frac > 0.3 ? "-" : "`";
    asciiPut(cv, i, j, c, slot);
}
AsciiEye.prototype.thinkingRing = function (cv, t, icx, icy, R, up, lo) {
    var r = R + 2.0, n = Math.max(12, asciiTrunc(2 * Math.PI * r / 2.4)), head = asciiMod(t * 2.4, 2 * Math.PI);
    for (var k = 0; k < n; k++) {
        var ang = 2 * Math.PI * k / n, dlt = asciiMod(head - ang, 2 * Math.PI);
        if (dlt > 2.8) continue;
        var i = asciiTrunc(icx + Math.cos(ang) * r), y = icy + Math.sin(ang) * r, yu = up[i];
        if (yu === undefined || !(yu < y && y < lo[i])) continue;
        var v = 1 - dlt / 2.8;
        var c = v > 0.55 ? ASCII_GLYPHS[(k + asciiTrunc(t * 12)) % ASCII_GLYPHS.length] : ASCII_RAMP[3 + asciiTrunc(v * 6)];
        asciiPut(cv, i, asciiTrunc(y / ASCII_ASPECT), c, FG);
    }
};
AsciiEye.prototype.flash = function (cv, g, rp, amount) {
    var icx = this.cx + g[0], icy = this.cy + g[1];
    for (var j = Math.max(0, asciiTrunc((icy - rp) / ASCII_ASPECT)); j < Math.min(cv.h, asciiTrunc((icy + rp) / ASCII_ASPECT) + 2); j++)
        for (var i = Math.max(0, asciiTrunc(icx - rp)); i < Math.min(cv.w, asciiTrunc(icx + rp) + 2); i++) {
            var d = Math.hypot(i + 0.5 - icx, (j + 0.5) * ASCII_ASPECT - icy);
            if (d < rp) {
                var c = ASCII_FINE[asciiTrunc(asciiClamp(amount * (1.0 - 0.55 * d / rp)) * 15.999)];
                if (c !== " ") asciiPut(cv, i, j, c, ACCENT);
            }
        }
};
AsciiEye.prototype.drawError = function (cv, t, frame, dt, op, g, rp) {
    var sc = this.scratch, w = cv.w, h = cv.h, k, j;
    asciiFill(sc);
    this.drawEye(sc, t, frame, op, g, rp, 1.0, false);
    if (dt < 0.067) {
        for (j = 0; j < h; j++) {
            if (asciiRnd(j, frame, 11) >= 0.45) continue;
            var off = asciiTrunc((asciiRnd(j, frame, 12) - 0.5) * 16);
            if (!off) continue;
            var row = sc.ch.slice(j * w, (j + 1) * w), cols = Array.prototype.slice.call(sc.co, j * w, (j + 1) * w);
            for (var x = 0; x < w; x++) {
                var from = asciiMod(x - off, w);
                sc.ch[j * w + x] = row[from]; sc.co[j * w + x] = cols[from];
            }
        }
        for (k = 0; k < w * h; k++) {
            if (sc.ch[k] === " ") continue;
            if (asciiRnd(k, frame, 13) < 0.08) {
                sc.ch[k] = ASCII_GLYPHS[asciiTrunc(asciiRnd(k, frame, 14) * ASCII_GLYPHS.length)]; sc.co[k] = ACCENT;
            }
            cv.ch[k] = sc.ch[k]; cv.co[k] = sc.co[k];
        }
        return;
    }
    var p = (dt - 0.067) / 1.18, amp = Math.pow(Math.sin(Math.PI * asciiClamp(p)), 1.4);
    for (k = 0; k < w * h; k++) {
        var c = sc.ch[k];
        if (c === " ") continue;
        var i = k % w; j = Math.floor(k / w);
        var dx = i + 0.5 - this.cx, dy = (j + 0.5) * ASCII_ASPECT - this.cy, dist = Math.hypot(dx, dy) || 1.0;
        var push = amp * (5.0 + 16.0 * asciiRnd(i, j, 5)), jx = (asciiRnd(i, j, 8) - 0.5) * 0.9;
        var nx = asciiTrunc(i + 0.5 + (dx / dist + jx) * push);
        var ny = asciiTrunc(((j + 0.5) * ASCII_ASPECT + (dy / dist + jx) * push) / ASCII_ASPECT);
        var slot = sc.co[k];
        if (amp > 0.25 && asciiRnd(i, j, Math.floor(frame / 3)) < amp * 0.45) {
            c = ASCII_GLYPHS[asciiTrunc(asciiRnd(i, j, Math.floor(frame / 2)) * ASCII_GLYPHS.length)];
            slot = asciiRnd(i, j, 21) < 0.12 ? ACCENT : FG;
        }
        asciiPut(cv, nx, ny, c, slot);
    }
};
AsciiEye.prototype.drawInside = function (cv, t, s) {
    var w = cv.w, h = cv.h, f = 0.32 * Math.min(w, h * ASCII_ASPECT), cx = w / 2.0, cy = h * ASCII_ASPECT / 2.0;
    var n = Math.max(40, Math.floor(w * h / 16));
    for (var k = 0; k < n; k++) {
        if (asciiRnd(k, 1, 4) > s.inside) continue;
        var sx = asciiRnd(k, 2, 4) * 2 - 1, sy = asciiRnd(k, 3, 4) * 2 - 1;
        var z = asciiMod(asciiRnd(k, 4, 4) - 0.22 * (t - 6.0), 1.0) + 0.03;
        var i = asciiTrunc(cx + sx * f / z * 1.6), j = asciiTrunc((cy + sy * f / z) / ASCII_ASPECT);
        if (i >= 0 && i < w && j >= 0 && j < h)
            asciiPut(cv, i, j, z < 0.25 ? "*" : z < 0.5 ? "+" : z < 0.8 ? "·" : ".", z < 0.35 ? FG : NOISE);
    }
    if (s.cat > 0 && this.sprite) {
        var cols = Math.max(16, Math.floor(Math.min(asciiTrunc(w * 0.36), asciiTrunc(h * ASCII_ASPECT * 0.72)) / 2) * 2);
        var key = cols + ":" + s.pose;
        if (!(key in this.jcache)) this.jcache[key] = asciiJackson(this.sprite, this.look, s.pose, cols);
        var body = this.jcache[key], x0 = asciiTrunc(cx - cols / 2), y0 = asciiTrunc(cy / ASCII_ASPECT - cols / 4);
        for (var b = 0; b < body.length; b++) {
            var e = body[b];
            if (asciiRnd(x0 + e[0], y0 + e[1], 9) < s.cat) asciiPut(cv, x0 + e[0], y0 + e[1], e[2], e[3]);
        }
    }
};
AsciiEye.prototype.drawLine = function (cv, s) {
    var text = ASCII_STORY_LINE.slice(0, s.text);
    var x0 = Math.floor((cv.w - ASCII_STORY_LINE.length) / 2), y = Math.max(1, Math.floor(cv.h / 8));
    for (var k = 0; k < text.length; k++)
        if (text[k] !== " " && asciiRnd(k, 1, 17) >= s.textFade) asciiPut(cv, x0 + k, y, text[k], FG);
    if (s.text < ASCII_STORY_LINE.length || s.textFade === 0.0) asciiPut(cv, x0 + text.length, y, "█", FG);
};
AsciiEye.prototype.drawHud = function (cv, t) {
    var w = cv.w, h = cv.h, state = this.mode, kinds = ["error", "done"];
    for (var i = 0; i < kinds.length; i++) {
        var d = this.lastEvent(kinds[i], t);
        if (d !== null && d < 1.2) { state = kinds[i]; break; }
    }
    var label = state.toUpperCase(), dash = new Array(Math.max(0, w - 4) + 1).join("─");
    asciiText(cv, 0, 0, "┌─" + dash + "─┐", NOISE);
    asciiText(cv, 2, 0, this.narrow ? " EYE " : " JACKSON::EYE ", FG);
    asciiText(cv, w - label.length - 4, 0, " " + label + " ", state === "error" ? ACCENT : FG);
    asciiText(cv, 0, h - 1, "└─" + dash + "─┘", NOISE);
    asciiText(cv, 2, h - 1, this.narrow ? " Q QUIT " : " 1-5 STATE · B BLINK · Q QUIT ", NOISE);
    if (this.clock && !this.narrow) {
        var hhmm = this.clock();
        asciiText(cv, w - hhmm.length - 9, h - 1, " " + hhmm + " TLN ", FG);
    }
};
AsciiEye.prototype.drawTiny = function (cv, t) {
    var shut = this.openness(t) < 0.5, s = shut ? "<(---)>" : "<( @ )>";
    var x = Math.max(0, Math.floor((cv.w - s.length) / 2)), y = Math.floor(cv.h / 2);
    asciiText(cv, x, y, s, FG);
    if (!shut) asciiPut(cv, x + 3, y, "@", ACCENT);
};

// ---- planets (planets.py) ----------------------------------------------------------------------
function AsciiPlanets(opts) {
    opts = opts || {};
    this.hud = opts.hud !== false;
    this.seed = opts.seed === undefined ? 3 : opts.seed;
    this.stillAt = 5.6;
    this.duration = null;
    this.wantsMouse = false;
    this.w = this.h = 0;
}
AsciiPlanets.prototype.resize = function (w, h) {
    this.w = w; this.h = h;
    this.tiny = w < 24 || h < 9;
    this.narrow = w < 80;
    this.top = this.hud && !this.tiny ? 1 : 0;
    var rows = h - 2 * this.top, hu = rows * ASCII_ASPECT;
    this.rb = Math.min(w * 0.20, hu * 0.30);
    this.px = w / 2.0 + w * 0.06;
    this.py = (this.top + rows / 2.0) * ASCII_ASPECT + hu * 0.04;
    this.rm = this.rb * 0.38;
    this.d = this.rb * 2.35;
    this.tilt = -0.22;
    var n = Math.max(12, Math.floor(w * h / (this.narrow ? 44 : 30))), s = this.seed;
    this.dust = [];
    for (var k = 0; k < n; k++)
        this.dust.push([asciiRnd(k, s, 1), asciiRnd(k, s, 2), 0.002 + 0.006 * asciiRnd(k, s, 3), (asciiRnd(k, s, 4) - 0.5) * 0.002,
                        1.0 + 3.0 * asciiRnd(k, s, 5), 6.28 * asciiRnd(k, s, 6), asciiRnd(k, s, 7)]);
};
AsciiPlanets.prototype.key = function (k) { return ["q", "Q", "esc", "й", "Й"].indexOf(k) < 0; };
AsciiPlanets.prototype.pointer = function () {};
AsciiPlanets.prototype.moon = function (t) {
    var phi = 2 * Math.PI * (t - 5.5) / 12.0 + Math.PI / 2;
    var ex = this.d * Math.cos(phi), ey = this.d * 0.22 * Math.sin(phi), ca = Math.cos(this.tilt), sa = Math.sin(this.tilt);
    return [this.px + ex * ca - ey * sa, this.py + ex * sa + ey * ca, Math.sin(phi) > 0];
};
AsciiPlanets.prototype.draw = function (cv, t) {
    if (cv.w !== this.w || cv.h !== this.h) this.resize(cv.w, cv.h);
    asciiFill(cv);
    if (this.tiny) { asciiText(cv, Math.max(0, Math.floor(cv.w / 2) - 4), Math.floor(cv.h / 2), "( O )  o", FG); return; }
    var w = cv.w, h = cv.h;
    for (var k = 0; k < this.dust.length; k++) {
        var p = this.dust[k];
        var i = asciiTrunc(asciiMod(p[0] - p[2] * t, 1.0) * w);
        var j = this.top + asciiTrunc(asciiMod(p[1] + p[3] * t, 1.0) * (h - 2 * this.top));
        var b = 0.5 + 0.5 * Math.sin(t * p[4] + p[5]);
        var c = b < 0.35 ? "." : b < 0.7 ? "·" : (b < 0.93 || p[6] < 0.8) ? "+" : "*";
        asciiPut(cv, i, j, c, p[6] > 0.85 ? FG : NOISE);
    }
    var m = this.moon(t), mx = m[0], my = m[1], front = m[2];
    if (!front) this.sphere(cv, mx, my, this.rm, t, true, null);
    this.ring(cv, true);
    this.sphere(cv, this.px, this.py, this.rb, t, false, front ? [mx, my] : null);
    this.ring(cv, false);
    if (front) { this.cutout(cv, mx, my, this.rm + 1.2); this.sphere(cv, mx, my, this.rm, t, true, null); }
    if (this.hud) {
        var eclipse = front && Math.abs(mx - this.px) < this.rb + this.rm, dash = new Array(Math.max(0, w - 4) + 1).join("─");
        asciiText(cv, 0, 0, "┌─" + dash + "─┐", NOISE);
        asciiText(cv, 2, 0, this.narrow ? " PLANETS " : " SOS::ART::PLANETS ", FG);
        var label = eclipse ? "ECLIPSE" : "ORBIT";
        asciiText(cv, w - label.length - 4, 0, " " + label + " ", FG);
        asciiText(cv, 0, h - 1, "└─" + dash + "─┘", NOISE);
        asciiText(cv, 2, h - 1, " Q QUIT ", NOISE);
        var stamp = "T+" + ("00000" + asciiMod(t, 100).toFixed(1)).slice(-5);
        asciiText(cv, w - stamp.length - 4, h - 1, " " + stamp + " ", NOISE);
    }
};
AsciiPlanets.prototype.sphere = function (cv, ox, oy, r, t, moon, shadow) {
    var w = cv.w, h = cv.h, ch = cv.ch, co = cv.co, lx = -0.35, ly = -0.30, lz = 0.89;
    var tb = Math.sin(0.35), cb = Math.cos(0.35), spin = t * 0.35, sr = this.rm * 1.1;
    var sx = shadow ? shadow[0] + 0.30 * this.rb : 0, sy = shadow ? shadow[1] + 0.22 * this.rb : 0;
    for (var j = Math.max(0, asciiTrunc((oy - r) / ASCII_ASPECT)); j < Math.min(h, asciiTrunc((oy + r) / ASCII_ASPECT) + 2); j++) {
        var y = (j + 0.5) * ASCII_ASPECT, ny = (y - oy) / r, base = j * w;
        for (var i = Math.max(0, asciiTrunc(ox - r)); i < Math.min(w, asciiTrunc(ox + r) + 2); i++) {
            var nx = (i + 0.5 - ox) / r, r2 = nx * nx + ny * ny;
            if (r2 > 1.0) continue;
            var nz = Math.sqrt(1.0 - r2), lam = nx * lx + ny * ly + nz * lz, inten;
            if (moon) {
                inten = Math.max(0.0, lam) * (0.72 + 0.28 * Math.sin(nx * 7.0 + 1.3) * Math.sin(ny * 6.0 - 0.7)) + 0.03;
            } else {
                var lat = -nx * tb + ny * cb, lon = Math.atan2(nx * cb + ny * tb, nz) + spin;
                inten = Math.max(0.0, lam) * (0.86 + 0.14 * Math.sin(lat * 9.0 + 1.6 * Math.sin(lon * 2.0 + lat * 4.0)));
                inten += 0.35 * Math.pow(1.0 - nz, 4) * Math.max(0.0, -nx * 0.6 - ny * 0.4 + 0.2);
                if (shadow && (i + 0.5 - sx) * (i + 0.5 - sx) + (y - sy) * (y - sy) < sr * sr) inten *= 0.12;
            }
            var k = base + i;
            if (inten < 0.07) { ch[k] = r2 > 0.86 && !moon ? "." : " "; co[k] = NOISE; }
            else { ch[k] = ASCII_RAMP[asciiTrunc(asciiClamp(inten) * 9.999)]; co[k] = FG; }
        }
    }
};
AsciiPlanets.prototype.cutout = function (cv, ox, oy, r) {
    for (var j = Math.max(0, asciiTrunc((oy - r) / ASCII_ASPECT)); j < Math.min(cv.h, asciiTrunc((oy + r) / ASCII_ASPECT) + 2); j++)
        for (var i = Math.max(0, asciiTrunc(ox - r)); i < Math.min(cv.w, asciiTrunc(ox + r) + 2); i++)
            if ((i + 0.5 - ox) * (i + 0.5 - ox) + ((j + 0.5) * ASCII_ASPECT - oy) * ((j + 0.5) * ASCII_ASPECT - oy) < r * r)
                asciiPut(cv, i, j, " ", BG);
};
AsciiPlanets.prototype.ring = function (cv, back) {
    var w = cv.w, h = cv.h, rb = this.rb, ox = this.px, oy = this.py, ca = Math.cos(this.tilt), sa = Math.sin(this.tilt);
    var ro = 1.82 * rb, kq = 0.28, span = ro * Math.abs(sa) + ro * kq * ca + 1, cells = [], i, j;
    for (j = Math.max(0, asciiTrunc((oy - span) / ASCII_ASPECT)); j < Math.min(h, asciiTrunc((oy + span) / ASCII_ASPECT) + 2); j++) {
        var y = (j + 0.5) * ASCII_ASPECT - oy;
        for (i = Math.max(0, asciiTrunc(ox - ro - 1)); i < Math.min(w, asciiTrunc(ox + ro) + 2); i++) {
            var x = i + 0.5 - ox, xr = x * ca + y * sa, yr = -x * sa + y * ca;
            if ((yr > 0) === back) continue;
            var rho = Math.sqrt(xr * xr + (yr / kq) * (yr / kq)) / rb, c, slot;
            if (rho >= 1.38 && rho <= 1.53) { c = xr < 0.3 * rb ? "=" : "-"; slot = FG; }
            else if (rho >= 1.62 && rho <= 1.82) { c = xr < 0.3 * rb ? "-" : "."; slot = this.narrow || xr > 0 ? NOISE : FG; }
            else continue;
            cells.push([i, j, c, slot]);
        }
    }
    if (!back) {
        var spanJ = {}, order = [];
        cells.forEach(function (e) {
            if (!(e[0] in spanJ)) { spanJ[e[0]] = [e[1], e[1]]; order.push(e[0]); }
            spanJ[e[0]][0] = Math.min(spanJ[e[0]][0], e[1]); spanJ[e[0]][1] = Math.max(spanJ[e[0]][1], e[1]);
        });
        order.forEach(function (ci) {
            [spanJ[ci][0] - 1, spanJ[ci][1] + 1].forEach(function (jj) {
                var ax = (ci + 0.5 - ox) / rb, ay = ((jj + 0.5) * ASCII_ASPECT - oy) / rb;
                if (ax * ax + ay * ay < 1) asciiPut(cv, ci, jj, " ", BG);
            });
        });
    }
    cells.forEach(function (e) { asciiPut(cv, e[0], e[1], e[2], e[3]); });
};

// ---- for the shell and the page: text layers, cells, the morph, the screensaver ---------------------
// One string per color slot, rows joined by "\n", other slots' cells as spaces and no spaces at the
// end of a row: a QML Text (or a <pre>) per slot draws a whole frame in three layouts.
function asciiLayers(cv) {
    var out = ["", "", "", ""], w = cv.w;
    for (var s = 1; s <= 3; s++) {
        var rows = [];
        for (var r = 0; r < cv.h; r++) {
            var line = "", gap = "";
            for (var i = r * w, e = i + w; i < e; i++) {
                if (cv.co[i] === s) { line += gap + cv.ch[i]; gap = ""; } else gap += " ";
            }
            rows.push(line);
        }
        out[s] = rows.join("\n");
    }
    return out;
}
// what a canvas shows, cell by cell: [[x, y, character, slot], ...]
function asciiCells(cv) {
    var out = [];
    for (var i = 0; i < cv.w * cv.h; i++)
        if (cv.ch[i] !== " " && cv.co[i] !== BG) out.push([i % cv.w, Math.floor(i / cv.w), cv.ch[i], cv.co[i]]);
    return out;
}
function asciiAngleOrder(cells) {
    var cx = 0, cy = 0, n = cells.length;
    cells.forEach(function (e) { cx += e[0]; cy += e[1] * ASCII_ASPECT; });
    cx /= Math.max(1, n); cy /= Math.max(1, n);
    return cells.map(function (e) { return [Math.atan2(e[1] * ASCII_ASPECT - cy, e[0] - cx), e]; })
        .sort(function (a, b) { return a[0] - b[0]; }).map(function (p) { return p[1]; });
}

// A transformation: the cells of one picture fly to the cells of another (Jackson into the eye, the
// eye back into Jackson). Both are ordered by angle around their middle and paired along that order,
// so the shape turns into the other one instead of scrambling. Every cell leaves a little late (its
// own hash), flies on an eased curve showing ramp characters, and lands as the target's character;
// targets nobody flies to fade in at the end. Pink stays only on what was or becomes alive.
function AsciiMorph(from, to, dur) {
    this.dur = dur || 1.8;
    var a = asciiAngleOrder(from), b = asciiAngleOrder(to), na = a.length, nb = b.length;
    this.pairs = [];
    this.extra = [];
    var hit = new Uint8Array(nb);
    for (var i = 0; i < na; i++) {
        var j = nb ? Math.min(nb - 1, Math.floor(i * nb / na)) : -1;
        if (j >= 0) hit[j] = 1;
        this.pairs.push([a[i], j >= 0 ? b[j] : null, 0.35 * asciiRnd(i, 5, 11)]);
    }
    for (var k = 0; k < nb; k++) if (!hit[k]) this.extra.push([b[k], 0.55 + 0.4 * asciiRnd(k, 6, 11)]);
    this.w = this.h = 0;
}
AsciiMorph.prototype.resize = function (w, h) { this.w = w; this.h = h; };
AsciiMorph.prototype.pointer = function () {};
AsciiMorph.prototype.key = function () { return true; };
AsciiMorph.prototype.draw = function (cv, t) {
    var q = asciiClamp(t / this.dur), frame = asciiTrunc(t * 30), i;
    for (i = 0; i < this.extra.length; i++) {
        var x = this.extra[i];
        if (q >= x[1]) asciiPut(cv, x[0][0], x[0][1], q > 0.97 ? x[0][2] : ASCII_RAMP[1 + asciiTrunc(asciiRnd(i, frame, 12) * 4)],
                                q > 0.97 ? x[0][3] : NOISE);
    }
    for (i = 0; i < this.pairs.length; i++) {
        var p = this.pairs[i], src = p[0], dst = p[1] || src;
        var u = asciiClamp((q - p[2]) / 0.65), e = asciiEase(u);
        if (!p[1] && u >= 1) continue;
        var px = Math.round(src[0] + (dst[0] - src[0]) * e), py = Math.round(src[1] + (dst[1] - src[1]) * e);
        var c, slot;
        if (u <= 0.02) { c = src[2]; slot = src[3]; }
        else if (u >= 0.98) { c = dst[2]; slot = dst[3]; }
        else {
            c = ASCII_FINE[2 + asciiTrunc(asciiRnd(i, frame >> 1, 13) * 12)];
            slot = u < 0.5 ? (src[3] === ACCENT ? ACCENT : FG) : (dst[3] === ACCENT ? ACCENT : FG);
        }
        if (!p[1] && u > 0.5) slot = NOISE;
        asciiPut(cv, px, py, c, slot);
    }
};

// The screensaver (the lock screen after a while, or called up): Jackson, standing where he stood,
// turns into his eye; the eye looks around and blinks, follows the pointer, and every few minutes
// the short film plays (it looks closer: Jackson is inside). opts: {sprite, look, from: {x, y, cols}
// (where Jackson stands, in cells), hold (seconds he stands still first, while the screen fades),
// night, seed, storyEvery (seconds)}.
function AsciiSaver(opts) {
    opts = opts || {};
    this.sprite = opts.sprite || null;
    this.look = opts.look || {};
    this.from = opts.from || null;
    this.morphLen = 1.8;
    this.hold = opts.hold === undefined ? 0.8 : opts.hold;
    this.storyEvery = opts.storyEvery || 240;
    this.eye = new AsciiEye({ hud: false, night: opts.night, seed: opts.seed, sprite: this.sprite, look: this.look });
    this.film = new AsciiEye({ story: true, night: opts.night, seed: opts.seed, sprite: this.sprite, look: this.look });
    this.morph = null;
    this.w = this.h = 0;
}
AsciiSaver.prototype.resize = function (w, h) {
    this.w = w; this.h = h;
    this.eye.resize(w, h);
    this.film.resize(w, h);
    this.morph = null;
    if (this.sprite && this.from && !this.eye.tiny) {
        var f = this.from, cols = Math.max(8, Math.floor(f.cols / 2) * 2);
        var src = asciiJackson(this.sprite, this.look, "idle", cols).map(function (e) { return [e[0] + f.x, e[1] + f.y, e[2], e[3]]; });
        var cv = asciiCanvas(w, h);
        this.eye.draw(cv, 0);
        this.eye.lastT = null;
        this.morph = new AsciiMorph(src, asciiCells(cv), this.morphLen);
    }
};
AsciiSaver.prototype.offset = function () { return this.morph ? this.hold + this.morphLen : 0; };
AsciiSaver.prototype.pointer = function (x, y, t) { this.eye.pointer(x, y, asciiMod(t - this.offset(), 3600)); };
AsciiSaver.prototype.key = function () { return true; };
AsciiSaver.prototype.trigger = function (kind, t) { this.eye.trigger(kind, asciiMod(t - this.offset(), 3600)); };
AsciiSaver.prototype.draw = function (cv, t) {
    if (cv.w !== this.w || cv.h !== this.h) this.resize(cv.w, cv.h);
    var m = this.offset();
    if (t < m) { asciiFill(cv); this.morph.draw(cv, Math.max(0, t - this.hold)); return; }
    var te = t - m, k = asciiMod(te, this.storyEvery + ASCII_STORY_LEN);
    if (k >= this.storyEvery) this.film.draw(cv, k - this.storyEvery);
    else this.eye.draw(cv, asciiMod(te, 3600));
};

function asciiRender(effect, w, h, t) {
    effect.resize(w, h);
    var cv = asciiCanvas(w, h);
    effect.draw(cv, t);
    return cv;
}

if (typeof module !== "undefined" && module.exports) {
    module.exports = { AsciiEye: AsciiEye, AsciiPlanets: AsciiPlanets, asciiRender: asciiRender, asciiCanvas: asciiCanvas,
                       asciiLines: asciiLines, asciiColorLines: asciiColorLines, asciiJackson: asciiJackson,
                       asciiRuns: asciiRuns, asciiHash: asciiHash, asciiLayers: asciiLayers, asciiCells: asciiCells,
                       AsciiMorph: AsciiMorph, AsciiSaver: AsciiSaver, asciiPut: asciiPut, asciiFill: asciiFill };
}
