.pragma library
.import "../core/Color.js" as Color
// Jackson sprites (format `sos-jackson/1`, design/mascot/FORMAT.md): compose a 32×32 frame from
// the character's layers and state, and map its keys to colors for the look, the theme mode and
// the system accent. A port of the reference runtime design/mascot/jackson.js (compose, palette).
// SPDX-License-Identifier: Apache-2.0
//
// Composed grids are cached per (character, look, state), palettes per (look, state, mode,
// accent): an accent or theme change only re-maps colors.

var gridCache = {};
var paletteCache = {};
var cacheSize = 0;

function trimCaches() {
    // a handful of looks × 8 states × 2 modes; drop everything when it grows past that
    if (++cacheSize > 600) {
        gridCache = {};
        paletteCache = {};
        cacheSize = 0;
    }
}

function assign(target, source) {
    if (source) {
        for (var k in source)
            target[k] = source[k];
    }
    return target;
}

function derive(data, o) {
    var rules = data.derive || {};
    for (var key in rules) {
        var list = rules[key];
        for (var i = 0; i < list.length; i++) {
            var when = list[i].when || {};
            var ok = true;
            for (var w in when) {
                if (o[w] !== when[w]) {
                    ok = false;
                    break;
                }
            }
            if (ok) {
                o[key] = list[i].value;
                break;
            }
        }
    }
    return o;
}

function matches(when, o) {
    for (var k in when) {
        var v = when[k];
        if (Array.isArray(v) ? v.indexOf(o[k]) < 0 : o[k] !== v)
            return false;
    }
    return true;
}

function fillName(name, o) {
    return name.replace(/\{(\w+)\}/g, function (m, k) {
        return String(o[k]);
    });
}

// Only the options that shape the picture (not the name or the outfit color).
function shapeKey(data, opts, state) {
    var o = assign(assign({}, data.defaults), opts);
    return [data.id, o.skin, o.style, o.hood, o.headphones, o.glasses, state].join("|");
}

// -> 32 strings of keys, "." = transparent
function compose(data, opts, state) {
    var key = shapeKey(data, opts, state);
    if (gridCache[key])
        return gridCache[key];
    var n = data.size;
    var o = derive(data, assign(assign(assign({}, data.defaults), opts), { state: state }));
    var skin = data.skins[o.skin] || {};
    var grid = [];
    var y, x;
    for (y = 0; y < n; y++) {
        var row = [];
        for (x = 0; x < n; x++)
            row.push(null);
        grid.push(row);
    }
    var draw = function (rows) {
        for (var yy = 0; yy < rows.length && yy < n; yy++) {
            var r = rows[yy];
            for (var xx = 0; xx < n; xx++) {
                if (r[xx] !== "." && r[xx] !== undefined)
                    grid[yy][xx] = r[xx];
            }
        }
    };
    for (var s = 0; s < data.compose.length; s++) {
        var step = data.compose[s];
        if (step.when && !matches(step.when, o))
            continue;
        if (step.skinFlag && (skin.flags || []).indexOf(step.skinFlag) < 0)
            continue;
        if (step.outline) {
            var add = [];
            for (y = 0; y < n; y++) {
                for (x = 0; x < n; x++) {
                    if (grid[y][x] !== null)
                        continue;
                    if ((x > 0 && grid[y][x - 1] !== null) || (x < n - 1 && grid[y][x + 1] !== null) || (y > 0 && grid[y - 1][x] !== null) || (y < n - 1 && grid[y + 1][x] !== null))
                        add.push([x, y]);
                }
            }
            for (var a = 0; a < add.length; a++)
                grid[add[a][1]][add[a][0]] = step.outline;
        } else if (step.state) {
            if (data.states[state])
                draw(data.states[state]);
        } else if (step.tint) {
            var layer = data.layers[fillName(step.tint, o)];
            if (layer) {
                for (y = 0; y < layer.length && y < n; y++) {
                    for (x = 0; x < n; x++) {
                        var c = layer[y][x];
                        if (c !== "." && c !== undefined)
                            grid[y][x] = data.tint.keys.indexOf(grid[y][x]) >= 0 && grid[y][x] !== null ? data.tint.to : c;
                    }
                }
            }
        } else if (step.layer) {
            var l = data.layers[fillName(step.layer, o)];
            if (l)
                draw(l);
        }
    }
    var out = [];
    for (y = 0; y < n; y++) {
        var line = "";
        for (x = 0; x < n; x++)
            line += grid[y][x] === null ? "." : grid[y][x];
        out.push(line);
    }
    gridCache[key] = out;
    trimCaches();
    return out;
}

function pick(obj, keys) {
    var out = {};
    for (var i = 0; i < keys.length; i++)
        out[keys[i]] = obj[keys[i]];
    return out;
}

var OUTFIT_KEYS = ["outfit", "outfitShade", "outfitLight"];

// accent: an id from data.accents or "#hex"; opts.outfit: "accent" | accent id | "#hex"
function palette(data, opts, state, mode, accent) {
    var o = assign(assign({}, data.defaults), opts);
    var outfit = o.outfit || "accent";
    var key = [data.id, o.skin, outfit, state, mode, accent].join("|");
    if (paletteCache[key])
        return paletteCache[key];
    var acc = data.accents[accent];
    var c = assign(assign({}, data.fixed), (data.skins[o.skin] || {}).colors);
    if (acc)
        assign(c, { detail: acc[mode].detail, detailShade: acc[mode].detailShade, detailLight: acc[mode].detailLight });
    else
        assign(c, Color.detailFor(accent));
    if (outfit === "accent")
        assign(c, acc ? pick(acc[mode], OUTFIT_KEYS) : Color.outfitFor(accent, mode));
    else if (data.accents[outfit])
        assign(c, pick(data.accents[outfit][mode], OUTFIT_KEYS));
    else
        assign(c, Color.outfitFor(outfit, mode));
    var aliases = data.aliases || {};
    for (var slot in aliases) {
        if (!(slot in c))
            c[slot] = c[aliases[slot]];
    }
    var over = (data.stateSlots || {})[state] || {};
    for (var s in over)
        c[s] = c[over[s]];
    paletteCache[key] = c;
    trimCaches();
    return c;
}

// key -> "#rrggbb" for one frame (what PixelSprite draws)
function colors(data, opts, state, mode, accent) {
    var pal = palette(data, opts, state, mode, accent);
    var out = {};
    for (var k in data.slots)
        out[k] = pal[data.slots[k]];
    return out;
}

// the animation for a shell mood ("idle", "talking", …): {frames, ms, jitter}
function animation(data, name) {
    var anims = data.animations || {};
    var a = anims[name] || anims.idle || { frames: ["idle"], ms: [0] };
    return { frames: a.frames || ["idle"], ms: a.ms || [0], jitter: a.jitter || [] };
}

function hasState(data, state) {
    return !!(data && data.states && data.states[state]);
}
