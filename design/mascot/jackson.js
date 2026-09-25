/*
 * Jackson sprite runtime — reference implementation (JavaScript, no dependencies).
 * Format: design/mascot/FORMAT.md · data: shell/assets/jackson/<character>.json
 * The QML Canvas renderer is a direct port of compose() + palette() + draw().
 *
 *   const grid = JacksonSprite.compose(data, {style: 'jacket', glasses: 'round'}, 'talk1');
 *   const pal  = JacksonSprite.palette(data, opts, 'talk1', 'dark', 'lilac');       // or '#7b61ff'
 *   JacksonSprite.draw(canvas, data, opts, 'talk1', 'dark', 'lilac', 4);           // 128×128, crisp
 */
(function (root) {
  'use strict';

  // ── OKLCH (for custom colours; the 8 accents are precomputed in data.accents) ──
  const lin = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const gam = (c) => (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055);
  function hexToOklch(hex) {
    const [r, g, b] = [1, 3, 5].map((i) => lin(parseInt(hex.slice(i, i + 2), 16) / 255));
    const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    const L = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s;
    const a = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
    const bb = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
    return [L, Math.hypot(a, bb), ((Math.atan2(bb, a) * 180) / Math.PI + 360) % 360];
  }
  function toLinear(L, C, H) {
    const a = C * Math.cos((H * Math.PI) / 180), b = C * Math.sin((H * Math.PI) / 180);
    const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
    const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
    const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
    return [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
      -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
      -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s];
  }
  const inGamut = (v) => v.every((x) => x >= -1e-4 && x <= 1 + 1e-4);
  function oklchToHex(L, C, H) {
    let rgb = toLinear(L, C, H);
    if (!inGamut(rgb)) {                       // reduce chroma until it fits sRGB
      let lo = 0, hi = C;
      for (let i = 0; i < 24; i++) { const mid = (lo + hi) / 2; if (inGamut(toLinear(L, mid, H))) lo = mid; else hi = mid; }
      rgb = toLinear(L, lo, H);
    }
    return '#' + rgb.map((v) => Math.round(Math.min(1, Math.max(0, gam(Math.min(1, Math.max(0, v))))) * 255)
      .toString(16).padStart(2, '0')).join('');
  }
  const OUTFIT_L = { dark: [0.32, 0.25, 0.40], light: [0.45, 0.36, 0.56] };
  const OUTFIT_CMAX = { dark: 0.075, light: 0.11 };
  // dark oranges/yellows turn to mud-brown: up to 40% less chroma, smooth dip centred on hue 75° (±40°)
  function outfitCmax(H, mode) {
    const d = ((H - 75 + 180) % 360 + 360) % 360 - 180;
    const band = Math.abs(d) < 40 ? Math.cos((d / 40) * Math.PI / 2) : 0;
    return OUTFIT_CMAX[mode] * (1 - 0.4 * band);
  }
  function outfitFor(hex, mode) {
    const [, C, H] = hexToOklch(hex), c = Math.min(C, outfitCmax(H, mode));
    const [b, s, l] = OUTFIT_L[mode];
    return { outfit: oklchToHex(b, c, H), outfitShade: oklchToHex(s, c, H), outfitLight: oklchToHex(l, c, H) };
  }
  function detailFor(hex) {
    const [L, C, H] = hexToOklch(hex);
    return { detail: hex, detailShade: oklchToHex(Math.max(0, L + (L > 0.45 ? -0.13 : -0.08)), C, H),
      detailLight: oklchToHex(L + Math.min(0.12, 0.97 - L), C, H) };
  }

  // ── composition ──
  function derive(data, o) {
    for (const [key, rules] of Object.entries(data.derive || {})) {
      for (const rule of rules) {
        if (Object.entries(rule.when || {}).every(([k, v]) => o[k] === v)) { o[key] = rule.value; break; }
      }
    }
    return o;
  }
  const matches = (when, o) => Object.entries(when).every(([k, v]) => (Array.isArray(v) ? v.includes(o[k]) : o[k] === v));
  const fill = (name, o) => name.replace(/\{(\w+)\}/g, (_, k) => String(o[k]));

  function compose(data, opts, state) {
    const n = data.size;
    const o = derive(data, Object.assign({}, data.defaults, opts, { state }));
    const skin = data.skins[o.skin];
    const grid = Array.from({ length: n }, () => new Array(n).fill(null));
    const draw = (rows) => rows.forEach((row, y) => { for (let x = 0; x < n; x++) if (row[x] !== '.') grid[y][x] = row[x]; });
    for (const step of data.compose) {
      if (step.when && !matches(step.when, o)) continue;
      if (step.skinFlag && !(skin.flags || []).includes(step.skinFlag)) continue;
      if (step.outline) {
        const add = [];
        for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
          if (grid[y][x] !== null) continue;
          if ((x > 0 && grid[y][x - 1] !== null) || (x < n - 1 && grid[y][x + 1] !== null) ||
              (y > 0 && grid[y - 1][x] !== null) || (y < n - 1 && grid[y + 1][x] !== null)) add.push([x, y]);
        }
        add.forEach(([x, y]) => { grid[y][x] = step.outline; });
      } else if (step.state) {
        draw(data.states[state]);
      } else if (step.tint) {
        const layer = data.layers[fill(step.tint, o)];
        if (layer) layer.forEach((row, y) => { for (let x = 0; x < n; x++) {
          const c = row[x];
          if (c !== '.') grid[y][x] = data.tint.keys.includes(grid[y][x]) ? data.tint.to : c;
        } });
      } else {
        const layer = data.layers[fill(step.layer, o)];
        if (layer) draw(layer);
      }
    }
    return grid;
  }

  // accent: an id from data.accents or a '#hex' (custom); opts.outfit: 'accent' | accent id | '#hex'
  function palette(data, opts, state, mode, accent) {
    const o = Object.assign({}, data.defaults, opts);
    const acc = data.accents[accent];
    const c = Object.assign({}, data.fixed, data.skins[o.skin].colors);
    Object.assign(c, acc ? { detail: acc[mode].detail, detailShade: acc[mode].detailShade, detailLight: acc[mode].detailLight }
      : detailFor(accent));
    const outfit = o.outfit || 'accent';
    if (outfit === 'accent') Object.assign(c, acc ? pick(acc[mode], ['outfit', 'outfitShade', 'outfitLight']) : outfitFor(accent, mode));
    else if (data.accents[outfit]) Object.assign(c, pick(data.accents[outfit][mode], ['outfit', 'outfitShade', 'outfitLight']));
    else Object.assign(c, outfitFor(outfit, mode));
    for (const [slot, alias] of Object.entries(data.aliases || {})) if (!(slot in c)) c[slot] = c[alias];
    for (const [slot, alias] of Object.entries((data.stateSlots || {})[state] || {})) c[slot] = c[alias];
    return c;
  }
  const pick = (obj, keys) => Object.fromEntries(keys.map((k) => [k, obj[k]]));

  function draw(canvas, data, opts, state, mode, accent, scale) {
    const n = data.size, s = scale || 1;
    const grid = compose(data, opts, state), pal = palette(data, opts, state, mode, accent);
    canvas.width = n * s; canvas.height = n * s;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, n * s, n * s);
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const k = grid[y][x];
      if (k === null) continue;
      ctx.fillStyle = pal[data.slots[k]];
      ctx.fillRect(x * s, y * s, s, s);
    }
    return canvas;
  }

  root.JacksonSprite = { compose, palette, draw, derive, hexToOklch, oklchToHex, outfitFor, detailFor };
})(typeof window !== 'undefined' ? window : this);
