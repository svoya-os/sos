#!/usr/bin/env python3
"""SOS GRUB theme «svoya»: assets, theme.txt (ru) + theme-en.txt (en), and a PNG preview.

    python3 branding/grub/generate.py

Design (1920×1080 reference, positions are GRUB proportional specs so they hold at other sizes):
* background   the Graphite wallpaper surface (gradients + grain) without the signal;
* horizon      the wallpaper's horizon line and Morse burst as components anchored at 78 %, so the
               timeout highlight (a __timeout__ progress bar on the same anchor) always sits on it:
               the line brightens toward the burst while GRUB counts down;
* menu         left-aligned IBM Plex Mono (as PFF2 "Svoya Mono", see make-fonts.sh), the selected
               entry in `text` with a Morse dash in `text` as the marker; static texts (caption, key hints) are
               PNGs so they keep the brand's tracking and keycaps.

Neutral by rule (design/DESIGN.md §12): no accent anywhere, only Graphite text tones, so the boot
menu can never clash with the accent a user picks later.

GRUB parses integer percentages only ("78%-2" is fine, "77.8%" would hang its parser).

SPDX-License-Identifier: Apache-2.0
The assets it produces are licensed CC BY-SA 4.0.
"""
from __future__ import annotations

import html
import math
import pathlib
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "wallpapers"))
import brand  # noqa: E402
import generate as wallpapers  # noqa: E402  (branding/wallpapers/generate.py)
from brand import MARK, face, mark_elements  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
THEME = HERE / "svoya"
C = brand.theme("graphite")["color"]
W, H = 1920, 1080
DPR = H / wallpapers.UNIT_H
FONT = "Svoya Mono Regular"          # PFF2 family made by make-fonts.sh from IBM Plex Mono (OFL RFN: no "Plex")
ANCHOR = "78%"                        # the horizon: 700/900 of the height in the wallpaper
MARGIN = "8%+7"                       # 160 px at 1920
MARKER_W = 28                         # left pad of menu items; the selected one shows a Morse dash there
ITEM_H, ITEM_GAP, ITEM_FONT = 44, 6, 24

TEXT = {
    "ru": {"caption": f"{brand.NAME} {brand.VERSION} · {brand.CODENAME_RU.upper()}",
           "timeout": "загрузка через %d с",
           "hints": [("↑ ↓", "выбрать"), ("Enter", "загрузить"), ("E", "изменить"), ("C", "консоль")],
           "entries": [f"{brand.NAME}", f"{brand.NAME} · снимок 24 сен 18:02", "Дополнительные параметры для SOS",
                       "Настройки прошивки UEFI"]},
    "en": {"caption": f"{brand.NAME} {brand.VERSION} · {brand.CODENAME_EN.upper()}",
           "timeout": "booting in %d s",
           "hints": [("↑ ↓", "select"), ("Enter", "boot"), ("E", "edit"), ("C", "console")],
           "entries": [f"{brand.NAME}", f"{brand.NAME} · snapshot Sep 24 18:02", "Advanced options for SOS",
                       "UEFI Firmware Settings"]},
}


def spec(value: str, total: int) -> int:
    """Evaluate a GRUB proportional spec the way theme_loader.c does (integer % + px terms)."""
    out, frac, num, sign, i = 0, 0.0, "", 1, 0
    terms = value.replace("-", "+-").split("+")
    for term in terms:
        term = term.strip()
        if not term:
            continue
        neg = term.startswith("-")
        term = term.lstrip("-")
        if term.endswith("%"):
            frac += (-1 if neg else 1) * int(term[:-1]) / 100
        else:
            out += (-1 if neg else 1) * int(term)
    return max(0, int(total * frac) + out)


# ───────────────────────────── raster assets ─────────────────────────────

def render_layers(r: brand.Renderer):
    """Background (surface + grain) and the signal pieces, from the wallpaper generator itself."""
    width_units = W / DPR
    jobs = {
        "background": {"surface", "grain"},
        "base": {"base"},
        "pulse": {"pulse", "tick"},
    }
    out = {}
    for name, layers in jobs.items():
        doc = wallpapers.page_html("graphite", width_units, DPR, True, layers=layers, accent=C["text"])
        tmp = brand.OUT / "grub" / f".{name}.png"
        r.html(doc, round(width_units), wallpapers.UNIT_H, tmp, scale=DPR, transparent=name != "background",
               wait_ms=120)
        out[name] = Image.open(tmp).convert("RGBA" if name != "background" else "RGB")
        tmp.unlink()
    return out


def bbox_alpha(img: Image.Image, pad: int = 2):
    a = np.asarray(img)[..., 3]
    ys, xs = np.nonzero(a > 0)
    return max(0, xs.min() - pad), max(0, ys.min() - pad), min(img.width, xs.max() + 1 + pad), min(img.height, ys.max() + 1 + pad)


def rgba(alpha: np.ndarray, color) -> Image.Image:
    h, w = alpha.shape
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = color
    out[..., 3] = np.clip(np.rint(alpha * 255), 0, 255)
    return Image.fromarray(out, "RGBA")


def make_rasters(r: brand.Renderer) -> dict:
    THEME.mkdir(parents=True, exist_ok=True)
    layers = render_layers(r)
    layers["background"].save(THEME / "background.png", optimize=True)
    horizon_y = round(wallpapers.SIGNAL_Y * DPR)                # 840: the line's first device row
    anchor = spec(ANCHOR, H)                                    # 842
    # horizon: full-width band around the line (scaled horizontally by GRUB, never vertically)
    band = layers["base"].crop((0, horizon_y - 4, W, horizon_y + 5))
    band.save(THEME / "horizon.png", optimize=True)
    # burst + its tick caption, native size
    x0, y0, x1, y1 = bbox_alpha(layers["pulse"])
    layers["pulse"].crop((x0, y0, x1, y1)).save(THEME / "burst.png", optimize=True)
    geo = {"horizon_top": f"{ANCHOR}-{anchor - (horizon_y - 4)}", "burst": (x0, y0, x1 - x0, y1 - y0)}
    pct = int(x0 / W * 100)
    geo["burst_left"] = f"{pct}%+{x0 - int(W * pct / 100)}"
    geo["burst_top"] = f"{ANCHOR}-{anchor - y0}"
    # timeout highlight: 5 rows, core on the line row; fade in from the left, soft head at the right
    prof = np.array([0.10, 0.34, 1.0, 0.34, 0.10])
    acc = brand.rgb(C["text"])                                  # neutral: the signal is drawn in `text`
    rgba(prof[:, None] * 0.95, acc).save(THEME / "timeout_hl_c.png")
    ramp = np.linspace(0, 1, 240) ** 1.6
    rgba(prof[:, None] * ramp[None, :] * 0.95, acc).save(THEME / "timeout_hl_w.png")
    head = np.linspace(1, 0, 36) ** 2
    rgba(prof[:, None] * head[None, :] * 0.95, acc).save(THEME / "timeout_hl_e.png")
    rgba(np.zeros((5, 1)), acc).save(THEME / "timeout_bar_c.png")
    geo["timeout_top"] = f"{ANCHOR}-{anchor - (horizon_y - 2)}"
    geo["timeout_width"] = f"{pct}%+{x0 - int(W * pct / 100)}"      # ends where the burst's lead-in begins
    # menu marker: a Morse dash (the signal color), and an invisible spacer of the same width
    marker = np.zeros((ITEM_H, MARKER_W))
    rgba(marker, acc).save(THEME / "item_w.png")
    ss = 4
    dash_w, dash_h = 11, 4
    yy, xx = np.mgrid[0:ITEM_H * ss, 0:MARKER_W * ss] / ss
    cy = ITEM_H / 2
    inside = (np.abs(yy - cy) <= dash_h / 2) & (xx >= 2) & (xx <= 2 + dash_w)
    rr = dash_h / 2
    caps = (np.hypot(xx - (2 + rr), yy - cy) <= rr) | (np.hypot(xx - (2 + dash_w - rr), yy - cy) <= rr)
    core = ((xx >= 2 + rr) & (xx <= 2 + dash_w - rr) & (np.abs(yy - cy) <= rr)) | caps
    a = core.reshape(ITEM_H, ss, MARKER_W, ss).mean(axis=(1, 3))
    rgba(a, acc).save(THEME / "select_w.png")
    # terminal box (GRUB console): surface with a 1 px lineStrong border and radius 11, as 9 slices
    n, rad = 12, 11.0
    yy, xx = (np.mgrid[0:2 * n * ss, 0:2 * n * ss] + 0.5) / ss
    dist = np.hypot(xx - np.clip(xx, rad, 2 * n - rad), yy - np.clip(yy, rad, 2 * n - rad))
    shape = (dist <= rad).reshape(2 * n, ss, 2 * n, ss).mean(axis=(1, 3))
    fill = (dist <= rad - 1).reshape(2 * n, ss, 2 * n, ss).mean(axis=(1, 3))
    border = shape - fill
    surf, line = np.array(brand.rgb(C["surface"]), float), np.array(brand.rgb(C["lineStrong"]), float)
    col = (surf * fill[..., None] + line * border[..., None]) / np.maximum(shape, 1e-6)[..., None]
    full = Image.fromarray(np.dstack([np.clip(np.rint(col), 0, 255), np.rint(shape * 255)]).astype(np.uint8), "RGBA")
    parts = {"nw": (0, 0, n, n), "ne": (n, 0, 2 * n, n), "sw": (0, n, n, 2 * n), "se": (n, n, 2 * n, 2 * n),
             "n": (n - 1, 0, n, n), "s": (n - 1, n, n, 2 * n), "w": (0, n - 1, n, n), "e": (n, n - 1, 2 * n, n),
             "c": (n - 1, n - 1, n, n)}
    for k, box in parts.items():
        full.crop(box).save(THEME / f"terminal_{k}.png")
    return geo


def text_png(r: brand.Renderer, text: str, size: float, color: str, tracking: float, out: pathlib.Path,
             weight: int = 400) -> tuple[int, int]:
    f = face("mono", weight)
    x0, _y0, x1, _y1 = f.ink_bounds(text, size, tracking)
    asc, desc = f.ascender / f.upm * size, -f.descender / f.upm * size
    w, h = math.ceil(x1 - x0) + 4, math.ceil(asc + desc) + 4
    d, _ = f.path_d(text, size, x=2 - x0, baseline=2 + asc, tracking_em=tracking)
    r.svg(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><path d="{d}" fill="{color}"/></svg>',
          w, h, out)
    return w, h


def hints_png(r: brand.Renderer, hints, out: pathlib.Path) -> tuple[int, int]:
    """Key hints with keycaps, exactly like the shell's kbd style (mono 10.5, radius 5, 2 px bottom border)."""
    items = "".join(f'<span class="k"><kbd>{html.escape(k)}</kbd>{html.escape(v)}</span>' for k, v in hints)
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>{brand.font_face_css()}
      html,body{{margin:0;background:transparent}}
      .row{{display:inline-flex;gap:22px;padding:2px;font:400 13px/1 "Plex Mono";color:{C['textFaint']};
            -webkit-font-smoothing:antialiased}}
      .k{{display:inline-flex;align-items:center;gap:8px}}
      kbd{{font:500 12px/1 "Plex Mono";color:{C['textDim']};padding:4px 7px 5px;border:1px solid {C['lineStrong']};
           border-bottom-width:2px;border-radius:5px;background:{C['surface']}}}
    </style></head><body><div class="row" id="r">{items}</div></body></html>"""
    page = r.page(900, 60, 1)
    tmp = brand.write(brand.OUT / "grub" / ".hints.html", doc)
    page.goto(tmp.as_uri())
    page.evaluate("document.fonts.ready")
    box = page.eval_on_selector("#r", "e => { const b = e.getBoundingClientRect(); return [b.width, b.height]; }")
    w, h = math.ceil(box[0]), math.ceil(box[1])
    page.screenshot(path=str(out), omit_background=True, clip={"x": 0, "y": 0, "width": w, "height": h})
    page.context.close()
    tmp.unlink()
    return w, h


def mark_png(r: brand.Renderer, out: pathlib.Path, d: float = 5.0) -> tuple[int, int]:
    w = math.ceil(MARK.width * d) + 2
    h = math.ceil(d) + 2
    rects = "".join(f'<rect x="{x + 1:.2f}" y="1" width="{ew:.2f}" height="{eh:.2f}" rx="{eh / 2:.2f}" '
                    f'fill="{C["text"]}"/>'
                    for x, _y, ew, eh, dash, _ in mark_elements(d))
    r.svg(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">{rects}</svg>', w, h, out)
    return w, h


# ───────────────────────────── theme.txt ─────────────────────────────

def theme_txt(lang: str, geo: dict, sizes: dict) -> str:
    t = TEXT[lang]
    bx, by, bw, bh = geo["burst"]
    mw, mh = sizes["mark"]
    cw, ch = sizes[f"caption-{lang}"]
    hw, hh = sizes[f"hints-{lang}"]
    return f"""# SOS («СОС», Svoya Operating System) GRUB theme «svoya» — {'Russian' if lang == 'ru' else 'English'} texts.
# Generated by branding/grub/generate.py; fonts by branding/grub/make-fonts.sh (PFF2 "{FONT.rsplit(' ', 1)[0]}").
# SPDX-License-Identifier: CC-BY-SA-4.0

title-text: ""
desktop-image: "background.png"
desktop-image-scale-method: "stretch"
desktop-color: "{C['wall']}"
terminal-font: "{FONT} 16"
terminal-box: "terminal_*.png"
terminal-left: "8%"
terminal-top: "10%"
terminal-width: "84%"
terminal-height: "76%"
terminal-border: "0"

# the Morse mark and the colophon line
+ image {{ left = {MARGIN} top = 24% width = {mw} height = {mh} file = "mark.png" }}
+ image {{ left = {MARGIN} top = 24%+20 width = {cw} height = {ch} file = "caption-{lang}.png" }}

# the menu: text aligns with the mark, the Morse-dash marker hangs in the margin; neutral (no accent)
+ boot_menu {{
    left = 8%-{MARKER_W - 7}
    top = 33%
    width = 56%
    height = 40%
    item_font = "{FONT} {ITEM_FONT}"
    selected_item_font = "{FONT} {ITEM_FONT}"
    item_color = "{C['textDim']}"
    selected_item_color = "{C['text']}"
    item_height = {ITEM_H}
    item_spacing = {ITEM_GAP}
    item_padding = 0
    icon_width = 0
    icon_height = 0
    item_icon_space = 0
    item_pixmap_style = "item_*.png"
    selected_item_pixmap_style = "select_*.png"
    scrollbar = false
}}

# the horizon of the wallpaper; while GRUB counts down it brightens toward the burst
+ image {{ left = 0 top = {geo['horizon_top']} width = 100% height = 9 file = "horizon.png" }}
+ image {{ left = {geo['burst_left']} top = {geo['burst_top']} width = {bw} height = {bh} file = "burst.png" }}
+ progress_bar {{
    id = "__timeout__"
    left = 0
    top = {geo['timeout_top']}
    width = {geo['timeout_width']}
    height = 5
    bar_style = "timeout_bar_*.png"
    highlight_style = "timeout_hl_*.png"
    text = ""
}}
+ label {{
    id = "__timeout__"
    left = {MARGIN}
    top = {ANCHOR}+18
    width = 40%
    height = 20
    align = "left"
    font = "{FONT} 16"
    color = "{C['textFaint']}"
    text = "{t['timeout']}"
}}

# keys
+ image {{ left = {MARGIN} top = 90% width = {hw} height = {hh} file = "hints-{lang}.png" }}
"""


def grub_ascent(size: int) -> int:
    """PFF2 ascent as grub-mkfont stores it (FreeType size metrics from the hhea table), rounded."""
    f = face("mono", 400)
    return round(f.font["hhea"].ascent / f.upm * size)


def grub_baseline(size: int, item_h: int) -> int:
    f = face("mono", 400)
    asc = round(f.font["hhea"].ascent / f.upm * size)
    desc = round(-f.font["hhea"].descent / f.upm * size)
    return (item_h - (asc + desc)) // 2 + asc          # gui_list.c: text_top_offset


def text_path(text: str, size: int, x: float, baseline: float, color: str) -> str:
    f = face("mono", 400)
    d, w = f.path_d(text, size, x=0, baseline=0)
    return (f'<svg style="position:absolute;left:{x}px;top:{baseline - size * 1.2:.1f}px;overflow:visible" '
            f'width="{w + 4:.0f}" height="{size * 1.6:.0f}"><path transform="translate(0 {size * 1.2:.1f})" '
            f'd="{d}" fill="{color}"/></svg>')


# ───────────────────────────── preview ─────────────────────────────

def preview(r: brand.Renderer, lang: str, geo: dict, sizes: dict, out: pathlib.Path, selected: int = 0,
            countdown: float = 0.4) -> None:
    """HTML emulation of GRUB's gfxmenu for this theme at 1920×1080 (positions via the same specs)."""
    t = TEXT[lang]
    L = spec(MARGIN, W)
    menu_left, menu_top = spec(f"8%-{MARKER_W - 7}", W), spec("33%", H)
    rows = []
    for i, e in enumerate(t["entries"]):
        y = menu_top + i * (ITEM_H + ITEM_GAP)
        sel = i == selected
        if sel:
            rows.append(f'<img src="{(THEME / "select_w.png").as_uri()}" style="left:{menu_left}px;top:{y}px">')
        base = y + grub_baseline(ITEM_FONT, ITEM_H)
        rows.append(text_path(e, ITEM_FONT, menu_left + MARKER_W, base, C["text"] if sel else C["textDim"]))
    bx, by, bw, bh = geo["burst"]
    tw = spec(geo["timeout_width"], W)
    hl_w = int(tw * countdown)
    hl = (f'<div style="position:absolute;left:0;top:{spec(geo["timeout_top"], H)}px;width:{hl_w}px;height:5px;display:flex">'
          f'<img src="{(THEME / "timeout_hl_w.png").as_uri()}" style="position:static;width:240px;height:5px">'
          f'<img src="{(THEME / "timeout_hl_c.png").as_uri()}" style="position:static;flex:1;height:5px;min-width:0">'
          f'<img src="{(THEME / "timeout_hl_e.png").as_uri()}" style="position:static;width:36px;height:5px"></div>') if hl_w >= 276 else ""
    secs = max(1, round(5 * (1 - countdown)))
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>{brand.font_face_css()}
      html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:{C['wall']}}}
      .abs{{position:absolute}} img{{position:absolute;image-rendering:auto}}
      .item{{position:absolute;height:{ITEM_H}px;line-height:{ITEM_H}px;font:400 {ITEM_FONT}px "Plex Mono";
             -webkit-font-smoothing:antialiased;white-space:pre}}
      .t{{position:absolute;font:400 16px/20px "Plex Mono";color:{C['textFaint']};-webkit-font-smoothing:antialiased}}
    </style></head><body>
    <img src="{(THEME / 'background.png').as_uri()}" style="left:0;top:0;width:{W}px;height:{H}px">
    <img src="{(THEME / 'mark.png').as_uri()}" style="left:{L}px;top:{spec('24%', H)}px">
    <img src="{(THEME / f'caption-{lang}.png').as_uri()}" style="left:{L}px;top:{spec('24%+20', H)}px">
    {''.join(rows)}
    <img src="{(THEME / 'horizon.png').as_uri()}" style="left:0;top:{spec(geo['horizon_top'], H)}px;width:{W}px;height:9px">
    <img src="{(THEME / 'burst.png').as_uri()}" style="left:{spec(geo['burst_left'], W)}px;top:{spec(geo['burst_top'], H)}px">
    {hl}
    {text_path(t['timeout'].replace('%d', str(secs)), 16, L, spec(ANCHOR + '+18', H) + grub_ascent(16), C['textFaint'])}
    <img src="{(THEME / f'hints-{lang}.png').as_uri()}" style="left:{L}px;top:{spec('90%', H)}px">
    </body></html>"""
    r.html(doc, W, H, out, wait_ms=150)


def main() -> None:
    with brand.Renderer() as r:
        geo = make_rasters(r)
        sizes = {"mark": mark_png(r, THEME / "mark.png")}
        for lang in TEXT:
            sizes[f"caption-{lang}"] = text_png(r, TEXT[lang]["caption"], 11, C["textFaint"], 0.16,
                                                THEME / f"caption-{lang}.png")
            sizes[f"hints-{lang}"] = hints_png(r, TEXT[lang]["hints"], THEME / f"hints-{lang}.png")
        brand.write(THEME / "theme.txt", theme_txt("ru", geo, sizes))
        brand.write(THEME / "theme-en.txt", theme_txt("en", geo, sizes))
        preview(r, "ru", geo, sizes, HERE / "preview.png", selected=0, countdown=0.4)
        preview(r, "en", geo, sizes, HERE / "preview-en.png", selected=1, countdown=0.8)
        shutil.copy(HERE / "preview.png", brand.OUT / "grub-preview.png")
    print("theme:", brand.rel(THEME), "·", len(list(THEME.glob("*.png"))), "PNGs · previews:", brand.rel(HERE / "preview.png"))


if __name__ == "__main__":
    main()
