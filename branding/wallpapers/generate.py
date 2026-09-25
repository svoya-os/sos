#!/usr/bin/env python3
"""SOS wallpapers — «Сигнал / Signal»: a quiet horizon line that carries one Morse «СОС».

Reproduces the wallpaper of the approved mockup (design/mockups/desktop.{html,css}) exactly — same
gradients, grain filter, horizon fade, burst geometry, colophon — for every target size:

* the composition is defined in a 900-unit-tall space (the mockup's CSS pixels) and rendered by
  headless Chromium at device scale H/900, so 2880×1800 is pixel-identical to the mockup and the
  16:9 sizes are the same picture, a little wider (x positions are relative to the width);
* Paper's dot grid is snapped to whole device pixels (every dot identical at any scale);
* Phosphor's scanlines are applied afterwards on exact pixel rows (no moiré at fractional scales),
  keeping the mockup's average darkening (22 % on one row in three).

    python3 branding/wallpapers/generate.py                 # everything
    python3 branding/wallpapers/generate.py graphite 1920x1080
    python3 branding/wallpapers/generate.py --html          # dump the HTML sources for a browser

SPDX-License-Identifier: Apache-2.0
The images it produces are licensed CC BY-SA 4.0.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import brand  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
THEMES = ["graphite", "paper", "phosphor"]
SIZES = [(1920, 1080), (2560, 1440), (2880, 1800), (3840, 2160)]
UNIT_H = 900                               # the mockup's CSS height
NAME = {"en": "Signal", "ru": "Сигнал"}
AUTHOR = "SOS design team (Svoya Operating System)"
LICENSE = "CC-BY-SA-4.0"

# Signal geometry from design/mockups/desktop.html (1440×900 space): y = 700, u = 6.5, h = 14, x0 = 1030
SIGNAL_Y = 700.0
SIGNAL_U = 6.5
SIGNAL_H = 14.0
SIGNAL_X0_REL = 1030.0 / 1440.0            # burst start, relative to the width (≈ 0.715)
SIGNAL_LEAD = 70.0

# Per-theme surface recipe (values from design/mockups/desktop.css; colors from themes/*.toml)
def surface_css(theme_id: str, dpr: float) -> str:
    c = brand.theme(theme_id)["color"]
    if theme_id == "graphite":
        return (f"radial-gradient(1100px 620px at 12% -6%, {brand.rgba_css(c['accent'], 0.075)}, transparent 62%),\n"
                f"    radial-gradient(900px 700px at 104% 108%, {brand.rgba_css(c['cloud'], 0.045)}, transparent 60%),\n"
                f"    linear-gradient(180deg, #0f1012 0%, #0b0c0e 100%)")
    if theme_id == "paper":
        # 22 px dot grid, snapped so that one cell is a whole number of device pixels
        cell = round(22 * dpr) / dpr
        k = cell / 22
        return (f"radial-gradient(circle, {brand.rgba_css(c['text'], 0.13)} {0.9 * k:.4f}px, transparent {1.25 * k:.4f}px) "
                f"{cell / 2:.4f}px {cell / 2:.4f}px / {cell:.4f}px {cell:.4f}px,\n"
                f"    linear-gradient(180deg, #edeae3 0%, #e6e3da 100%)")
    if theme_id == "phosphor":
        return (f"radial-gradient(1200px 520px at 50% 118%, {brand.rgba_css(c['accent'], 0.10)}, transparent 65%),\n"
                f"    radial-gradient(900px 500px at 0% 0%, {brand.rgba_css(c['accent'], 0.035)}, transparent 60%),\n"
                f"    {c['wall']}")
    raise KeyError(theme_id)


GLOW = {  # --glow in design/mockups/tokens.css (dark themes only)
    "graphite": "drop-shadow(0 0 6px rgba(255, 181, 71, 0.45))",
    "paper": "none",
    "phosphor": "drop-shadow(0 0 7px rgba(92, 240, 143, 0.55))",
}
GRAIN_BLEND = {"graphite": "overlay", "paper": "multiply", "phosphor": "overlay"}
BASE_OPACITY = {"graphite": 0.22, "paper": 0.4, "phosphor": 0.22}
GRAIN_SVG = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='220' height='220'>"
             "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' "
             "stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 .5  0 0 0 0 .5  0 0 0 0 .5  0 0 0 1.4 -.2'/>"
             "</filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>")


ALL_LAYERS = frozenset({"surface", "base", "pulse", "tick", "grain", "colophon"})


def page_html(theme_id: str, width_units: float, dpr: float, lock: bool, layers=ALL_LAYERS) -> str:
    """layers: which parts to draw (the GRUB theme renders the surface and the signal separately)."""
    t = brand.theme(theme_id)
    c = t["color"]
    y, u, h = SIGNAL_Y, SIGNAL_U, SIGNAL_H
    x0 = SIGNAL_X0_REL * width_units
    d, x_end = brand.burst_path(x0, y, u, h, SIGNAL_LEAD)
    colophon = "" if lock or "colophon" not in layers else (
        f'<div class="colophon"><b>{brand.NAME}</b> {brand.VERSION} · {brand.CODENAME_RU.lower()}</div>')
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>SOS wallpaper — {theme_id}{' lock' if lock else ''}</title>
<style>
{brand.font_face_css()}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: {width_units:.4f}px; height: {UNIT_H}px; overflow: hidden; background: {c['wall'] if 'surface' in layers else 'transparent'}; }}
body {{ -webkit-font-smoothing: antialiased; text-rendering: geometricPrecision; font-feature-settings: "ss02", "zero"; }}
.wallpaper {{ position: absolute; inset: 0; background:
    {surface_css(theme_id, dpr) if 'surface' in layers else 'transparent'}; }}
svg.signal {{ position: absolute; inset: 0; width: {width_units:.4f}px; height: {UNIT_H}px; }}
.signal .base {{ fill: none; stroke-width: 1; opacity: {BASE_OPACITY[theme_id]}; }}
.signal .pulse {{ fill: none; stroke-width: 1.4; stroke-linejoin: round; stroke-linecap: round; opacity: 0.9; filter: {GLOW[theme_id]}; }}
.signal .tick {{ fill: {c['textFaint']}; font: 400 10px "Plex Mono"; letter-spacing: 0.3em; opacity: 0.8; }}
.grain {{ position: absolute; inset: 0; opacity: {t['effects']['grain']}; mix-blend-mode: {GRAIN_BLEND[theme_id]};
  background-image: url("{GRAIN_SVG}"); }}
.colophon {{ position: absolute; right: 28px; bottom: 22px; font: 400 10px/1.5 "Plex Mono"; letter-spacing: 0.14em;
  text-transform: uppercase; color: {c['textFaint']}; text-align: right; }}
.colophon b {{ color: {c['textDim']}; font-weight: 500; }}
</style></head>
<body><div class="wallpaper">
<svg class="signal" viewBox="0 0 {width_units:.4f} {UNIT_H}">
  <defs>
    <linearGradient id="fade" x1="0" x2="{width_units:.4f}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{c['accent']}" stop-opacity="0"/>
      <stop offset=".22" stop-color="{c['accent']}" stop-opacity=".9"/>
      <stop offset=".86" stop-color="{c['accent']}" stop-opacity=".9"/>
      <stop offset="1" stop-color="{c['accent']}" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="burst" x1="{x0 - SIGNAL_LEAD:.3f}" x2="{x_end + SIGNAL_LEAD:.3f}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{c['accent']}" stop-opacity="0"/>
      <stop offset=".18" stop-color="{c['accent']}" stop-opacity="1"/>
      <stop offset=".82" stop-color="{c['accent']}" stop-opacity="1"/>
      <stop offset="1" stop-color="{c['accent']}" stop-opacity="0"/>
    </linearGradient>
  </defs>
  {f'<path class="base" d="M 0 {y} L {width_units:.4f} {y}" stroke="url(#fade)"/>' if "base" in layers else ""}
  {f'<path class="pulse" d="{d}" stroke="url(#burst)"/>' if "pulse" in layers else ""}
  {f'<text class="tick" x="{x0:.3f}" y="{y + 26}">··· ——— ···</text>' if "tick" in layers else ""}
</svg>
{'<div class="grain"></div>' if "grain" in layers else ""}
{colophon}
</div></body></html>
"""


def scanlines(img: Image.Image, dpr: float) -> Image.Image:
    """Phosphor scanlines on exact device rows: one dark band per period, same mean darkening as the mockup."""
    period = max(3, round(3 * dpr))
    dark = max(1, round(period / 3))
    alpha = (0.22 / 3) * period / dark        # keep the mockup's average (0.22 on 1 row of 3)
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    rows = np.arange(a.shape[0]) % period >= period - dark
    a[rows] *= (1.0 - alpha)
    return Image.fromarray(np.clip(np.rint(a), 0, 255).astype(np.uint8))


def out_path(theme_id: str, w: int, h: int, lock: bool) -> pathlib.Path:
    name = f"signal-{theme_id}{'-lock' if lock else ''}-{w}x{h}.png"
    return HERE / theme_id / name


def render(r: brand.Renderer, theme_id: str, w: int, h: int, lock: bool) -> pathlib.Path:
    dpr = h / UNIT_H
    width_units = w / dpr
    html = page_html(theme_id, width_units, dpr, lock)
    target = out_path(theme_id, w, h, lock)
    tmp = brand.OUT / "wallpapers" / f".{target.stem}.png"
    page = r.page(round(width_units), UNIT_H, dpr)
    src = brand.write(brand.OUT / "wallpapers" / f".{target.stem}.html", html)
    try:
        page.goto(src.as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(120)
        page.screenshot(path=str(tmp), clip={"x": 0, "y": 0, "width": width_units, "height": UNIT_H})
    finally:
        page.context.close()
        src.unlink(missing_ok=True)
    img = Image.open(tmp).convert("RGB")
    tmp.unlink(missing_ok=True)
    if img.size != (w, h):                        # guard against rounding of the clip rectangle
        img = img.resize((w, h), Image.LANCZOS)
    if brand.theme(theme_id)["effects"].get("scanlines"):
        img = scanlines(img, dpr)
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(target, optimize=True)
    return target


def write_index() -> pathlib.Path:
    entries = []
    for theme_id in THEMES:
        t = brand.theme(theme_id)
        for lock in (False, True):
            sizes = {}
            for w, h in SIZES:
                p = out_path(theme_id, w, h, lock)
                if p.exists():
                    sizes[f"{w}x{h}"] = str(p.relative_to(HERE))
            entries.append({
                "id": f"signal-{theme_id}{'-lock' if lock else ''}",
                "theme": theme_id,
                "mode": t["mode"],
                "variant": "lock" if lock else "desktop",
                "name": {"en": f"{NAME['en']} · {t['name']['en']}", "ru": f"{NAME['ru']} · {t['name']['ru']}"},
                "description": {
                    "en": "A quiet horizon line carrying one Morse «СОС» burst" + ("" if lock else "; colophon bottom right"),
                    "ru": "Тихая линия горизонта с одним сигналом «СОС» азбукой Морзе" + ("" if lock else "; колофон справа внизу"),
                },
                "sizes": sizes,
                "author": AUTHOR,
                "license": LICENSE,
                "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0/",
            })
    index = {
        "schema": 1,
        "installDir": "/usr/share/svoya/wallpapers",
        "default": {"graphite": "signal-graphite", "paper": "signal-paper", "phosphor": "signal-phosphor"},
        "lock": {"graphite": "signal-graphite-lock", "paper": "signal-paper-lock", "phosphor": "signal-phosphor-lock"},
        "pick": "choose the size whose aspect ratio matches the output, then the smallest size ≥ the output resolution; scale to cover",
        "wallpapers": entries,
    }
    path = HERE / "wallpapers.json"
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str]) -> None:
    if "--html" in argv:
        for theme_id in THEMES:
            p = brand.write(brand.OUT / "wallpapers" / f"{theme_id}.html", page_html(theme_id, 1440, 2.0, False))
            print(brand.rel(p))
        return
    themes = [a for a in argv if a in THEMES] or THEMES
    sizes = [tuple(map(int, a.split("x"))) for a in argv if "x" in a and a[0].isdigit()] or SIZES
    with brand.Renderer() as r:
        for theme_id in themes:
            for w, h in sizes:
                for lock in (False, True):
                    p = render(r, theme_id, w, h, lock)
                    print(f"{brand.rel(p)}  {p.stat().st_size / 1e6:.1f} MB")
    print(brand.rel(write_index()))


if __name__ == "__main__":
    main(sys.argv[1:])
