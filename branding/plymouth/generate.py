#!/usr/bin/env python3
"""Svoya OS Plymouth theme «svoya-signal»: sprites, geometry block, preview frames.

    python3 branding/plymouth/generate.py            # sprites + script geometry + preview frames
    python3 branding/plymouth/generate.py --no-frames

* sprites      branding/plymouth/svoya-signal/*.png (1× logical px; Plymouth upscales on HiDPI)
* script       the block between `# @generated-begin/end` in svoya-signal.script is rewritten from
               GEOMETRY below, so sprites, script and preview share one set of numbers
* preview      branding/plymouth/preview.html (JS simulation of the script with the same sprites)
               → branding/plymouth/frames/*.png and branding/out/plymouth-frames.png

SPDX-License-Identifier: Apache-2.0 (code) · sprites CC BY-SA 4.0
"""
from __future__ import annotations

import json
import math
import pathlib
import re
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import brand  # noqa: E402
from brand import MORSE, face  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
THEME_DIR = HERE / "svoya-signal"
FRAMES_DIR = HERE / "frames"
C = brand.theme("graphite")["color"]
ACCENT = brand.rgb(C["accent"])
HOT = brand.rgb(brand.mix(C["accent"], "#ffffff", 0.5))
TEXT = brand.rgb(C["text"])
DIM = brand.rgb(C["textDim"])
FAINT = brand.rgb(C["textFaint"])

# ───────────────────────────── geometry (single source) ─────────────────────────────
U = 7            # Morse unit of the burst, px (the wallpaper uses 6.5 css px ≈ 7.8 px at 1080p)
PULSE_H = 15     # height of a pulse
STROKE = 1.6
PAD = 14         # glow margin inside burst/flare sprites
LEAD = 12        # solid baseline before the first pulse (joins the lit line)
TAIL = 64        # fade-out of the burst's baseline into the dim line
LINE_H = 15      # height of line sprites; the 1 px core sits on row LINE_CORE
LINE_CORE = 7

KEY_ON = []      # (x offset of pulse from burst sprite left, width, start unit, length units)
_x, _unit = LEAD, 0
for li, letter in enumerate(MORSE):
    for si, sym in enumerate(letter):
        n = 1 if sym == "." else 3
        KEY_ON.append((_x, n * U, _unit, n))
        _x += n * U
        _unit += n
        if si < len(letter) - 1:
            _x += U
            _unit += 1
    if li < len(MORSE) - 1:
        _x += 3 * U
        _unit += 3
BODY_END = _x                       # x where the last pulse ends
BURST_W = BODY_END + TAIL           # sprite width
BURST_BASE = PAD + PULSE_H          # baseline row inside burst/flare sprites
KEY_PERIOD = _unit + 7              # 27 units of «СОС» + 7-unit word gap

GEOMETRY = {
    "FPS": 50,
    "LINE_FRAC": 0.62, "LINE_MAX": 1180, "LINE_Y_FRAC": 0.46, "FADE_FRAC": 0.2,
    "LINE_CORE": LINE_CORE,
    "BURST_W": BURST_W, "BURST_BASE": BURST_BASE, "BURST_LEAD": LEAD, "BURST_TAIL": TAIL,
    "FLARE_PAD": PAD, "FLARE_BASE": BURST_BASE,
    "N_SYMBOLS": len(KEY_ON),
    "KEY_UNIT": 0.1, "KEY_PERIOD": KEY_PERIOD,
    "BASE_OPACITY": 0.34, "BURST_REST": 0.72,
    "T_SPOT": 0.18, "T_HOLD": 0.16, "T_STRETCH": 0.42, "T_SETTLE": 0.3, "T_BURST": 0.26, "T_WORD": 0.4,
    "WORD_GAP": 58, "CAPTION_GAP": 14, "PROMPT_GAP": 54, "FIELD_W": 380, "BULLET_PITCH": 11,
    "MSG_BOTTOM": 64, "MSG_LINE": 22,
    "FONT_MONO": "IBM Plex Mono 13px", "FONT_MONO_SMALL": "IBM Plex Mono 12px",
}
BG_TOP, BG_BOTTOM = (15, 16, 18), (11, 12, 14)   # the wallpaper's linear gradient (#0f1012 → #0b0c0e)

CAPTIONS = {   # name: (ru, en, color)
    "boot": ("СВОЯ ОПЕРАЦИОННАЯ СИСТЕМА", "YOUR OWN OPERATING SYSTEM", FAINT),
    "shutdown": ("ВЫКЛЮЧЕНИЕ", "POWERING OFF", DIM),
    "reboot": ("ПЕРЕЗАГРУЗКА", "RESTARTING", DIM),
    "updates": ("УСТАНОВКА ОБНОВЛЕНИЙ", "INSTALLING UPDATES", DIM),
    "upgrade": ("ОБНОВЛЕНИЕ СИСТЕМЫ", "UPGRADING THE SYSTEM", DIM),
    "firmware": ("ОБНОВЛЕНИЕ ПРОШИВКИ", "UPDATING FIRMWARE", DIM),
    "reset": ("СБРОС СИСТЕМЫ", "RESETTING THE SYSTEM", DIM),
    "unlock": ("КЛЮЧ ДИСКА", "DISK PASSPHRASE", FAINT),
    "question": ("ВОПРОС", "QUESTION", FAINT),
    "keepon": ("НЕ ВЫКЛЮЧАЙТЕ КОМПЬЮТЕР", "DO NOT TURN OFF THE COMPUTER", FAINT),
}


def script_block() -> str:
    g = GEOMETRY
    lines = []
    for k, v in g.items():
        if k == "N_SYMBOLS":
            lines.append(f"{k} = {v};")
            for i, (x, w, on, n) in enumerate(KEY_ON):
                lines.append(f"SYMBOL_X[{i}] = {x}; SYMBOL_W[{i}] = {w}; SYMBOL_ON[{i}] = {on}; SYMBOL_LEN[{i}] = {n};")
            continue
        lines.append(f'{k} = "{v}";' if isinstance(v, str) else f"{k} = {v:g};")

    def trip(name, c):
        r, gg, b = (round(x / 255, 3) for x in c)
        return f"{name}_R = {r:g}; {name}_G = {gg:g}; {name}_B = {b:g};"
    lines += [trip("BG_TOP", BG_TOP), trip("BG_BOTTOM", BG_BOTTOM), trip("TEXT", TEXT), trip("DIM", DIM), trip("FAINT", FAINT)]
    return "\n".join(lines)


def update_script() -> pathlib.Path:
    path = THEME_DIR / "svoya-signal.script"
    src = path.read_text(encoding="utf-8")
    new = re.sub(r"(# @generated-begin\n).*?(# @generated-end)", lambda m: m.group(1) + script_block() + "\n" + m.group(2),
                 src, flags=re.S)
    path.write_text(new, encoding="utf-8")
    return path


# ───────────────────────────── raster helpers ─────────────────────────────

def rgba_image(alpha: np.ndarray, rgb) -> Image.Image:
    """Straight-alpha RGBA from an alpha map (0..1) and a color (tuple or HxWx3 array)."""
    h, w = alpha.shape
    out = np.zeros((h, w, 4), np.float32)
    out[..., :3] = np.asarray(rgb, np.float32) if np.ndim(rgb) == 1 else rgb
    out[..., 3] = np.clip(alpha, 0, 1) * 255
    return Image.fromarray(np.clip(np.rint(out), 0, 255).astype(np.uint8), "RGBA")


def dither(a: np.ndarray, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return a + (rng.random(a.shape) - 0.5) / 255.0


def vertical_profile(h: int, core: int, glow_peak: float, sigma: float) -> np.ndarray:
    y = np.arange(h)
    d = np.abs(y - core)
    prof = glow_peak * np.exp(-(d ** 2) / (2 * sigma ** 2))
    prof[core] = 1.0
    return prof


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def make_line_sprites():
    # base line: 1 px core, faint glow, fades at both ends (like the wallpaper horizon)
    w = 1024
    x = (np.arange(w) + 0.5) / w
    f = GEOMETRY["FADE_FRAC"]
    ramp = np.minimum(smoothstep(x / f), smoothstep((1 - x) / f))
    prof = vertical_profile(LINE_H, LINE_CORE, 0.22, 1.5)
    rgba_image(prof[:, None] * ramp[None, :], ACCENT).save(THEME_DIR / "line.png", optimize=True)
    # lit segment (one column, scaled by the script) and its fade-in
    lit = vertical_profile(LINE_H, LINE_CORE, 0.42, 2.0)
    rgba_image(lit[:, None], ACCENT).save(THEME_DIR / "lit.png", optimize=True)
    w2 = 256
    ramp2 = smoothstep((np.arange(w2) + 0.5) / w2)
    rgba_image(lit[:, None] * ramp2[None, :], ACCENT).save(THEME_DIR / "lit-fade.png", optimize=True)
    # streak: the spot being pulled into a line — hot core, wide glow, soft ends
    w3, h3 = 256, 31
    xs = (np.arange(w3) + 0.5) / w3 * 2 - 1
    ends = np.clip(1 - xs ** 2, 0, 1) ** 0.7
    ys = np.arange(h3) - h3 // 2
    core = np.exp(-(ys ** 2) / (2 * 0.8 ** 2))
    glow = 0.55 * np.exp(-(ys ** 2) / (2 * 4.0 ** 2))
    a = np.maximum(core, glow)[:, None] * ends[None, :]
    t = (core / (core + glow + 1e-6))[:, None, None]
    col = np.asarray(HOT, np.float32) * t + np.asarray(ACCENT, np.float32) * (1 - t)
    col = np.broadcast_to(col, (h3, w3, 3))
    rgba_image(a, col).save(THEME_DIR / "streak.png", optimize=True)


def make_spot():
    n = 72
    c = (n - 1) / 2
    yy, xx = np.mgrid[0:n, 0:n]
    r = np.hypot(xx - c, yy - c)
    core = np.clip(3.2 - r, 0, 1)                         # crisp 3 px core
    glow = 0.62 * np.exp(-(r ** 2) / (2 * 7.5 ** 2)) + 0.12 * np.exp(-(r ** 2) / (2 * 16 ** 2))
    a = np.maximum(core, glow)
    t = (core / (core + glow + 1e-6))[..., None]
    col = np.asarray(HOT, np.float32) * t + np.asarray(ACCENT, np.float32) * (1 - t)
    rgba_image(dither(a), col).save(THEME_DIR / "spot.png", optimize=True)


def make_haze():
    w, h = 720, 216
    yy, xx = np.mgrid[0:h, 0:w]
    dx = (xx + 0.5 - w / 2) / (w / 2)
    dy = (yy + 0.5 - h / 2) / (h / 2)
    r2 = dx ** 2 + dy ** 2
    a = 0.085 * np.exp(-r2 * 3.2) * np.clip(1 - r2, 0, 1)
    rgba_image(dither(a, 3), ACCENT).save(THEME_DIR / "haze.png", optimize=True)


def make_small():
    # bullet: a Morse dot in the text color (6 px)
    n = 6
    yy, xx = np.mgrid[0:n, 0:n]
    ss = 4
    acc = np.zeros((n, n))
    for sy in range(ss):
        for sx in range(ss):
            r = np.hypot(xx + (sx + 0.5) / ss - n / 2, yy + (sy + 0.5) / ss - n / 2)
            acc += (r <= n / 2)
    rgba_image(acc / ss ** 2, TEXT).save(THEME_DIR / "bullet.png", optimize=True)
    # cursor: an amber block, terminal style
    rgba_image(np.ones((16, 8)), ACCENT).save(THEME_DIR / "cursor.png", optimize=True)
    # rule under the input line: one pixel of lineStrong, scaled by the script
    rgba_image(np.ones((1, 1)), brand.rgb(C["lineStrong"])).save(THEME_DIR / "rule.png", optimize=True)


# ───────────────────────────── vector sprites (Chromium) ─────────────────────────────

def burst_svg(flare_index: int | None = None) -> tuple[str, int, int]:
    """The square-wave «СОС» as on the wallpaper; or one pulse of it, hotter, for keying flares."""
    acc = C["accent"]
    base = BURST_BASE + 0.5
    top = base - PULSE_H
    if flare_index is None:
        w, h = BURST_W, BURST_BASE + PAD
        d = f"M 0 {base}"
        for x, pw, _on, _n in KEY_ON:
            d += f" L {x} {base} L {x} {top} L {x + pw} {top} L {x + pw} {base}"
        d += f" L {BURST_W} {base}"
        grad = (f'<linearGradient id="g" x1="0" x2="{w}" gradientUnits="userSpaceOnUse">'
                f'<stop offset="0" stop-color="{acc}"/><stop offset="{BODY_END / w:.4f}" stop-color="{acc}"/>'
                f'<stop offset="1" stop-color="{acc}" stop-opacity="0"/></linearGradient>')
        body = (f'<defs>{grad}<filter id="f" x="-10%" y="-60%" width="120%" height="220%">'
                f'<feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="{acc}" flood-opacity=".45"/></filter></defs>'
                f'<path d="{d}" fill="none" stroke="url(#g)" stroke-width="{STROKE}" stroke-linejoin="round" '
                f'stroke-linecap="butt" filter="url(#f)"/>')
    else:
        _x, pw, _on, _n = KEY_ON[flare_index]
        w, h = pw + 2 * PAD, BURST_BASE + PAD
        x0 = PAD
        hot = "#%02x%02x%02x" % HOT
        d = f"M {x0} {base} L {x0} {top} L {x0 + pw} {top} L {x0 + pw} {base}"
        body = (f'<defs><filter id="f" x="-50%" y="-50%" width="200%" height="200%">'
                f'<feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="{acc}" flood-opacity=".85"/></filter></defs>'
                f'<path d="{d}" fill="none" stroke="{hot}" stroke-width="{STROKE}" stroke-linejoin="round" '
                f'stroke-linecap="round" filter="url(#f)"/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{body}</svg>', w, h


def text_svg(text: str, kind: str, weight: int, size: float, color, tracking: float = 0.0,
             pad: int = 2) -> tuple[str, int, int]:
    f = face(kind, weight)
    x0, y0, x1, y1 = f.ink_bounds(text, size, tracking)
    asc = f.ascender / f.upm * size
    desc = -f.descender / f.upm * size
    w = math.ceil(x1 - x0) + 2 * pad
    h = math.ceil(asc + desc) + 2 * pad
    d, _ = f.path_d(text, size, x=pad - x0, baseline=pad + asc, tracking_em=tracking)
    fill = "#%02x%02x%02x" % tuple(color)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<path d="{d}" fill="{fill}"/></svg>', w, h)


def chevron_svg() -> tuple[str, int, int]:
    w, h = 10, 18
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<path d="M 2.5 4.5 L 7 9 L 2.5 13.5" fill="none" stroke="{C["accent"]}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>', w, h)


def render_vectors(r: brand.Renderer):
    jobs = {"burst.png": burst_svg(None), "chevron.png": chevron_svg()}
    dot_i = next(i for i, k in enumerate(KEY_ON) if k[3] == 1)
    dash_i = next(i for i, k in enumerate(KEY_ON) if k[3] == 3)
    jobs["flare-dot.png"] = burst_svg(dot_i)
    jobs["flare-dash.png"] = burst_svg(dash_i)
    jobs["wordmark-ru.png"] = text_svg("СОС", "sans", 600, 22, TEXT, 0.2)
    jobs["wordmark-en.png"] = text_svg("Svoya OS", "sans", 600, 20, TEXT, 0.0)
    for name, (ru, en, col) in CAPTIONS.items():
        jobs[f"caption-{name}-ru.png"] = text_svg(ru, "mono", 400, 10.5, col, 0.16)
        jobs[f"caption-{name}-en.png"] = text_svg(en, "mono", 400, 10.5, col, 0.16)
    jobs["caps-ru.png"] = text_svg("CAPS LOCK", "mono", 500, 10, brand.rgb(C["accent"]), 0.14)
    jobs["caps-en.png"] = jobs["caps-ru.png"]
    for fn, (svg, w, h) in jobs.items():
        r.svg(svg, w, h, THEME_DIR / fn)


def write_plymouth_file() -> pathlib.Path:
    text = """[Plymouth Theme]
Name=Svoya Signal
Description=Svoya OS boot splash: a phosphor spot warms up into a line that carries the Morse «СОС».
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/svoya-signal
ScriptFile=/usr/share/plymouth/themes/svoya-signal/svoya-signal.script
# Read by plymouth-populate-initrd (dracut): the matching font files are copied into the initrd,
# so Image.Text (password prompt, messages) renders in IBM Plex with full Cyrillic.
TitleFont=IBM Plex Sans 13px
MonospaceFont=IBM Plex Mono 13px

[script-env-vars]
# ru | en — language of the captions baked into the sprites; the installer may rewrite this line.
svoya_lang=ru
"""
    return brand.write(THEME_DIR / "svoya-signal.plymouth", text)


# ───────────────────────────── preview frames ─────────────────────────────

FRAMES = [
    # file, caption, simulation state (see preview.html)
    ("1-power-on", "0,10 с — точка", {"t": 0.10}),
    ("2-warm-up", "0,52 с — точка растягивается в линию", {"t": 0.52}),
    ("3-boot-24", "загрузка · 24 %", {"t": 1.93, "progress": 0.24}),
    ("4-boot-71-message", "загрузка · 71 % · сообщение", {"t": 5.21, "progress": 0.71,
                                                           "messages": ["Проверка файловой системы на /dev/nvme0n1p2 — 37 %"]}),
    ("5-unlock", "ключ диска (LUKS)", {"t": 7.64, "progress": 0.31, "password": 9,
                                       "prompt": "Please enter passphrase for disk Samsung SSD 990 PRO (luks-3f1c)"}),
    ("6-shutdown", "выключение", {"t": 2.43, "mode": "shutdown"}),
]


def render_frames(r: brand.Renderer) -> list[pathlib.Path]:
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for name, caption, state in FRAMES:
        page = r.page(1920, 1080, 1)
        q = json.dumps(state, ensure_ascii=False)
        page.goto((HERE / "preview.html").as_uri() + "#" + q)
        page.wait_for_function("window.__ready === true", timeout=20000)
        target = FRAMES_DIR / f"frame-{name}.png"
        page.screenshot(path=str(target), clip={"x": 0, "y": 0, "width": 1920, "height": 1080})
        page.context.close()
        out.append(target)
    # a review strip for the contact sheet
    thumbs = [Image.open(p).convert("RGB").resize((640, 360), Image.LANCZOS) for p in out]
    strip = Image.new("RGB", (640 * 3 + 16 * 2, 360 * 2 + 16), (40, 40, 40))
    for i, t in enumerate(thumbs):
        strip.paste(t, ((i % 3) * 656, (i // 3) * 376))
    strip_path = brand.OUT / "plymouth-frames.png"
    strip.save(strip_path, optimize=True)
    out.append(strip_path)
    return out


def write_preview_data() -> pathlib.Path:
    data = {"geometry": GEOMETRY, "symbols": KEY_ON, "bg": [BG_TOP, BG_BOTTOM],
            "text": TEXT, "dim": DIM, "faint": FAINT, "frames": [[n, c, s] for n, c, s in FRAMES]}
    return brand.write(HERE / "preview-data.js", "// generated by generate.py — do not edit\nwindow.SVOYA_PLYMOUTH = "
                       + json.dumps(data, ensure_ascii=False, indent=1) + ";\n")


def main(argv):
    THEME_DIR.mkdir(parents=True, exist_ok=True)
    make_line_sprites()
    make_spot()
    make_haze()
    make_small()
    with brand.Renderer() as r:
        render_vectors(r)
        write_plymouth_file()
        update_script()
        write_preview_data()
        if "--no-frames" not in argv:
            for p in render_frames(r):
                print(brand.rel(p))
    print("sprites:", len(list(THEME_DIR.glob("*.png"))), "· burst", BURST_W, "px · key period", KEY_PERIOD, "units")


if __name__ == "__main__":
    main(sys.argv[1:])
