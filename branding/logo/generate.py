#!/usr/bin/env python3
"""Svoya OS logo system: Morse mark, wordmarks, lockups and the app/distro icon.

All SVGs are self-contained: text is converted to outlines from IBM Plex (fontTools), so they
render identically without the fonts installed. Colors come from themes/*.toml.

    python3 branding/logo/generate.py            # SVGs + icon PNGs + previews in branding/out/logo

Outputs
    branding/logo/svg/svoya-<piece>-<variant>.svg      variant: on-dark | on-light | mono-black | mono-white
    branding/logo/icon/svoya.svg                       scalable icon (512 master geometry)
    branding/logo/icon/svoya-symbolic.svg              16px single-color icon for panels
    branding/logo/icon/src/svoya-<n>.svg               pixel-snapped source for each PNG size
    branding/logo/icon/png/svoya-<n>.png               16 24 32 48 64 128 256 512

SPDX-License-Identifier: Apache-2.0 (code) · artwork CC BY-SA 4.0
"""
from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import brand  # noqa: E402
from brand import MARK, face, mark_elements  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
SVG_DIR = HERE / "svg"
ICON_DIR = HERE / "icon"
PREVIEW_DIR = brand.OUT / "logo"

GRAPHITE = brand.theme("graphite")["color"]
PAPER = brand.theme("paper")["color"]

VARIANTS = {
    # name: (ink for dots and letters, signal color for the dashes, preview background)
    "on-dark": (GRAPHITE["text"], GRAPHITE["accent"], GRAPHITE["wall"]),
    "on-light": (PAPER["text"], PAPER["accent"], PAPER["wall"]),
    "mono-black": ("#000000", "#000000", "#ffffff"),
    "mono-white": ("#ffffff", "#ffffff", "#000000"),
}

# Typography of the wordmarks
WORD_SIZE = 100.0                 # master units: font size 100
RU_TEXT, RU_TRACK = "СОС", 0.20   # IBM Plex Sans SemiBold, generous tracking
EN_TEXT, EN_TRACK = "Svoya OS", 0.0
CAP = face("sans", 600).cap_height / face("sans", 600).upm * WORD_SIZE   # 69.8

# Lockup rules (relative to the cap height of the wordmark)
H_DOT = 0.18 * CAP            # horizontal lockup: dot diameter
H_GAP = 0.62 * CAP            # horizontal lockup: mark → wordmark ink
S_GAP = 0.46 * CAP            # stacked lockup: mark → cap line

LICENSE_NOTE = ("Svoya OS brand artwork · CC BY-SA 4.0 · outlines from IBM Plex Sans "
                "(SIL OFL 1.1, © IBM Corp.)")


def fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def svg_doc(width: float, height: float, body: str, title: str, desc: str = LICENSE_NOTE) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(width)}" height="{fmt(height)}" '
            f'viewBox="0 0 {fmt(width)} {fmt(height)}" role="img" aria-label="{title}">\n'
            f'  <title>{title}</title>\n  <desc>{desc}</desc>\n{body}</svg>\n')


def pill(x: float, y: float, w: float, h: float, fill: str, rx: float | None = None) -> str:
    rx = h / 2 if rx is None else rx
    return (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" '
            f'rx="{fmt(rx)}" fill="{fill}"/>')


def mark_body(d: float, x0: float, y0: float, ink: str, signal: str, indent: str = "  ") -> str:
    """The linear mark: dots in ink, the ——— in the signal color."""
    dots = [pill(x, y, w, h, ink) for x, y, w, h, dash, _ in mark_elements(d, x0, y0) if not dash]
    dashes = [pill(x, y, w, h, signal) for x, y, w, h, dash, _ in mark_elements(d, x0, y0) if dash]
    return (f'{indent}<g id="mark">\n'
            + "".join(f"{indent}  {e}\n" for e in dots + dashes)
            + f"{indent}</g>\n")


@dataclass
class Folded:
    """The mark folded into three lines — С / О / С — used by the icon and avatars.

    All values in px. Dots sit centred over the dashes, so the emblem reads as one 3×3 figure.
    """
    d: float          # element height (dot diameter)
    dash: float       # dash length
    gap: float        # gap between dashes
    row_gap: float    # vertical gap between rows
    round: bool = True

    @property
    def width(self) -> float:
        return 3 * self.dash + 2 * self.gap

    @property
    def height(self) -> float:
        return 3 * self.d + 2 * self.row_gap

    def elements(self, cx: float, cy: float):
        x0 = cx - self.width / 2
        y0 = cy - self.height / 2
        for row in range(3):
            y = y0 + row * (self.d + self.row_gap)
            for i in range(3):
                xc = x0 + self.dash / 2 + i * (self.dash + self.gap)
                if row == 1:
                    yield xc - self.dash / 2, y, self.dash, self.d, True
                else:
                    yield xc - self.d / 2, y, self.d, self.d, False


FOLDED_MASTER = Folded(d=36, dash=90, gap=27, row_gap=45)   # on the 512 canvas


def folded_body(f: Folded, cx: float, cy: float, ink: str, signal: str, indent: str = "  ") -> str:
    rx = None if f.round else 0
    items = [pill(x, y, w, h, signal if dash else ink, rx) for x, y, w, h, dash in f.elements(cx, cy)]
    return f'{indent}<g id="mark">\n' + "".join(f"{indent}  {e}\n" for e in items) + f"{indent}</g>\n"


# ───────────────────────────── pieces ─────────────────────────────

def word_geometry(text: str, tracking: float, size: float = WORD_SIZE):
    f = face("sans", 600)
    x0, y0, x1, y1 = f.ink_bounds(text, size, tracking)
    return f, (x0, y0, x1, y1)


def wordmark(text: str, tracking: float, ink: str, title: str) -> str:
    f, (x0, y0, x1, y1) = word_geometry(text, tracking)
    d, _ = f.path_d(text, WORD_SIZE, x=-x0, baseline=-y0, tracking_em=tracking)
    body = f'  <path id="wordmark" fill="{ink}" d="{d}"/>\n'
    return svg_doc(x1 - x0, y1 - y0, body, title)


def mark_svg(ink: str, signal: str, d: float = 16.0) -> str:
    w = MARK.width * d
    return svg_doc(w, d, mark_body(d, 0, 0, ink, signal), "Svoya OS — ··· ——— ···")


def folded_svg(ink: str, signal: str) -> str:
    f = Folded(d=16, dash=40, gap=12, row_gap=20)
    return svg_doc(f.width, f.height, folded_body(f, f.width / 2, f.height / 2, ink, signal),
                   "Svoya OS — mark, folded (С / О / С)")


def lockup_horizontal(text: str, tracking: float, ink: str, signal: str, title: str) -> str:
    f, (x0, y0, x1, y1) = word_geometry(text, tracking)
    d = H_DOT
    mark_w = MARK.width * d
    word_x = mark_w + H_GAP - x0                      # glyph origin so that ink starts after the gap
    top = min(y0, -CAP / 2 - d / 2)                   # ink top (overshoot) in baseline coords
    bottom = max(y1, -CAP / 2 + d / 2)
    height = bottom - top
    baseline = -top
    word, _ = f.path_d(text, WORD_SIZE, x=word_x, baseline=baseline, tracking_em=tracking)
    body = mark_body(d, 0, baseline - CAP / 2 - d / 2, ink, signal)
    body += f'  <path id="wordmark" fill="{ink}" d="{word}"/>\n'
    return svg_doc(word_x + x1, height, body, title)


def lockup_stacked(text: str, tracking: float, ink: str, signal: str, title: str,
                   match_width: bool = True, dot: float | None = None) -> str:
    f, (x0, y0, x1, y1) = word_geometry(text, tracking)
    ink_w = x1 - x0
    d = ink_w / MARK.width if match_width else dot
    mark_w = MARK.width * d
    width = max(ink_w, mark_w)
    mark_x = (width - mark_w) / 2
    cap_top = d + S_GAP                                # y of the cap line
    baseline = cap_top + CAP
    word_x = (width - ink_w) / 2 - x0
    word, _ = f.path_d(text, WORD_SIZE, x=word_x, baseline=baseline, tracking_em=tracking)
    height = baseline + y1                             # include descenders / overshoot
    body = mark_body(d, mark_x, 0, ink, signal)
    body += f'  <path id="wordmark" fill="{ink}" d="{word}"/>\n'
    return svg_doc(width, height, body, title)


# ───────────────────────────── icon ─────────────────────────────

@dataclass
class IconSpec:
    canvas: int
    inset: float
    radius: float
    folded: Folded
    stroke: float        # 0 = none
    glow: bool
    highlight: bool


def icon_spec(n: int) -> IconSpec:
    """Pixel-snapped geometry per size: rows on whole pixels, dots centred on dashes."""
    hand = {
        16: IconSpec(16, 0, 3, Folded(2, 4, 1, 1, round=False), 0, False, False),
        24: IconSpec(24, 1, 4.25, Folded(2, 4, 2, 2, round=False), 1, False, False),
        32: IconSpec(32, 1, 5.75, Folded(2, 6, 2, 3, round=False), 1, False, False),
        48: IconSpec(48, 1, 8.75, Folded(4, 9, 3, 4), 1, False, False),
        64: IconSpec(64, 2, 11.25, Folded(4, 11, 3.5, 6), 1, True, True),
        128: IconSpec(128, 4, 22.5, Folded(8, 22, 6.5, 11), 1, True, True),
        256: IconSpec(256, 8, 45, Folded(18, 45, 13.5, 22), 1, True, True),
        512: IconSpec(512, 16, 90, FOLDED_MASTER, 2, True, True),
    }
    return hand[n]


def icon_svg(spec: IconSpec, title: str = "Svoya OS") -> str:
    n = spec.canvas
    t = n - 2 * spec.inset
    x = y = spec.inset
    sw = spec.stroke
    ink, signal = GRAPHITE["text"], GRAPHITE["accent"]
    top, bottom = "#1d1f23", "#101114"            # surface-2 → just above wall: matte graphite
    edge = "#2d3036"                              # between line and lineStrong
    defs = [f'    <linearGradient id="tile" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>']
    if spec.highlight:
        defs.append(f'    <linearGradient id="signal-edge" x1="0" y1="0" x2="1" y2="0">'
                    f'<stop offset="0" stop-color="{signal}" stop-opacity="0"/>'
                    f'<stop offset=".5" stop-color="{signal}" stop-opacity=".55"/>'
                    f'<stop offset="1" stop-color="{signal}" stop-opacity="0"/></linearGradient>')
    if spec.glow:
        sd = spec.folded.d * 0.45
        defs.append(f'    <filter id="glow" x="-30%" y="-150%" width="160%" height="400%">'
                    f'<feGaussianBlur stdDeviation="{fmt(sd)}"/></filter>')
    body = ["  <defs>\n" + "\n".join(defs) + "\n  </defs>\n"]
    if sw:
        body.append(f'  <rect x="{fmt(x + sw / 2)}" y="{fmt(y + sw / 2)}" width="{fmt(t - sw)}" '
                    f'height="{fmt(t - sw)}" rx="{fmt(spec.radius - sw / 2)}" fill="url(#tile)" '
                    f'stroke="{edge}" stroke-width="{fmt(sw)}"/>\n')
    else:
        body.append(f'  <rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(t)}" height="{fmt(t)}" '
                    f'rx="{fmt(spec.radius)}" fill="url(#tile)"/>\n')
    if spec.highlight:
        hw = t * 0.56
        hh = max(1.0, n / 256 * 1.5)
        body.append(f'  <rect x="{fmt(n / 2 - hw / 2)}" y="{fmt(y)}" width="{fmt(hw)}" height="{fmt(hh)}" '
                    f'fill="url(#signal-edge)"/>\n')
    f = spec.folded
    if spec.glow:
        glow = [pill(ex, ey, w, h, signal) for ex, ey, w, h, dash in f.elements(n / 2, n / 2) if dash]
        body.append('  <g filter="url(#glow)" opacity=".5">' + "".join(glow) + "</g>\n")
    body.append(folded_body(f, n / 2, n / 2, ink, signal))
    return svg_doc(n, n, "".join(body), title,
                   "Svoya OS icon · graphite tile with the mark folded into С / О / С · CC BY-SA 4.0")


def symbolic_svg() -> str:
    f = Folded(2, 4, 1, 2, round=False)
    items = "".join(pill(x, y, w, h, "#2e3436", 0) for x, y, w, h, _ in f.elements(8, 8))
    return svg_doc(16, 16, f"  <g>{items}</g>\n", "Svoya OS",
                   "Symbolic (single-color) Svoya OS mark for panels and menus · CC BY-SA 4.0")


# ───────────────────────────── build ─────────────────────────────

PIECES = {
    "mark": lambda ink, sig: mark_svg(ink, sig),
    "mark-folded": lambda ink, sig: folded_svg(ink, sig),
    "wordmark-sos": lambda ink, sig: wordmark(RU_TEXT, RU_TRACK, ink, "СОС — Своя Операционная Система"),
    "wordmark-svoya-os": lambda ink, sig: wordmark(EN_TEXT, EN_TRACK, ink, "Svoya OS"),
    "lockup-horizontal-ru": lambda ink, sig: lockup_horizontal(RU_TEXT, RU_TRACK, ink, sig, "СОС"),
    "lockup-horizontal-en": lambda ink, sig: lockup_horizontal(EN_TEXT, EN_TRACK, ink, sig, "Svoya OS"),
    "lockup-stacked-ru": lambda ink, sig: lockup_stacked(RU_TEXT, RU_TRACK, ink, sig, "СОС"),
    "lockup-stacked-en": lambda ink, sig: lockup_stacked(EN_TEXT, EN_TRACK, ink, sig, "Svoya OS",
                                                          match_width=False, dot=0.155 * CAP),
}

ICON_SIZES = [16, 24, 32, 48, 64, 128, 256, 512]


def build_svgs() -> list[pathlib.Path]:
    written = []
    for piece, fn in PIECES.items():
        for variant, (ink, sig, _bg) in VARIANTS.items():
            written.append(brand.write(SVG_DIR / f"svoya-{piece}-{variant}.svg", fn(ink, sig)))
    written.append(brand.write(ICON_DIR / "svoya.svg", icon_svg(icon_spec(512))))
    written.append(brand.write(ICON_DIR / "svoya-symbolic.svg", symbolic_svg()))
    for n in ICON_SIZES:
        written.append(brand.write(ICON_DIR / "src" / f"svoya-{n}.svg", icon_svg(icon_spec(n))))
    return written


def svg_size(path: pathlib.Path) -> tuple[float, float]:
    import re
    head = path.read_text(encoding="utf-8")[:400]
    w = float(re.search(r'width="([\d.]+)"', head).group(1))
    h = float(re.search(r'height="([\d.]+)"', head).group(1))
    return w, h


def render_pngs(r: brand.Renderer) -> None:
    for n in ICON_SIZES:
        svg = (ICON_DIR / "src" / f"svoya-{n}.svg").read_text(encoding="utf-8")
        r.svg(svg, n, n, ICON_DIR / "png" / f"svoya-{n}.png")
    # previews of every lockup on its intended background (2x, generous clear space)
    for piece in PIECES:
        for variant, (_ink, _sig, bg) in VARIANTS.items():
            path = SVG_DIR / f"svoya-{piece}-{variant}.svg"
            w, h = svg_size(path)
            target_h = 120 if piece.startswith("mark") else 160
            k = target_h / h if h > 40 else 36 / h
            if piece == "mark":
                k = 520 / w
            W, H = w * k, h * k
            pad = max(64, H * 0.9)
            doc = (f'<div style="width:{W + 2 * pad:.0f}px;height:{H + 2 * pad:.0f}px;background:{bg};'
                   f'display:grid;place-items:center"><img src="{path.as_uri()}" '
                   f'style="width:{W:.1f}px;height:{H:.1f}px"></div>')
            r.html(f"<!doctype html><body style='margin:0'>{doc}</body>", int(W + 2 * pad), int(H + 2 * pad),
                   PREVIEW_DIR / f"svoya-{piece}-{variant}.png", scale=2)


def main() -> None:
    written = build_svgs()
    with brand.Renderer() as r:
        render_pngs(r)
    print(f"{len(written)} SVGs, {len(ICON_SIZES)} icon PNGs, previews in {brand.rel(PREVIEW_DIR)}")


if __name__ == "__main__":
    main()
