#!/usr/bin/env python3
"""SOS (Svoya Operating System) branding toolkit: shared constants and helpers for every generator
in branding/.

* tokens      read from themes/*.toml (single source of truth, never duplicated here)
* Morse mark  geometry of `··· ——— ···` (the mark, the burst on the wallpaper, the stacked icon form)
* type        IBM Plex glyph outlines -> SVG paths (fontTools, with GPOS pair kerning), so every
              SVG we ship renders without the fonts installed
* render      headless Chromium (Playwright) for SVG/HTML -> PNG

SPDX-License-Identifier: Apache-2.0
"""
from __future__ import annotations

import contextlib
import functools
import math
import pathlib
import tomllib
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parents[2]
BRANDING = ROOT / "branding"
FONTS = ROOT / "design" / "fonts"
THEMES_DIR = ROOT / "themes"
OUT = BRANDING / "out"

MORSE = ["...", "---", "..."]          # С О С / S O S — identical in Russian and international Morse
NAME = "SOS"                           # product name (Latin)
NAME_RU = "СОС"                        # product name (Cyrillic)
TAGLINE_EN = "Svoya Operating System"
TAGLINE_RU = "Своя Операционная Система"
VERSION = "26.10"
CODENAME_RU = "Первый сигнал"
CODENAME_EN = "First Signal"

FONT_FILES = {
    ("sans", 300): "IBMPlexSans-Light.ttf",
    ("sans", 400): "IBMPlexSans-Regular.ttf",
    ("sans", 500): "IBMPlexSans-Medium.ttf",
    ("sans", 600): "IBMPlexSans-SemiBold.ttf",
    ("sans", 700): "IBMPlexSans-Bold.ttf",
    ("mono", 300): "IBMPlexMono-Light.ttf",
    ("mono", 400): "IBMPlexMono-Regular.ttf",
    ("mono", 500): "IBMPlexMono-Medium.ttf",
    ("mono", 600): "IBMPlexMono-SemiBold.ttf",
    ("pixel", 400): "DepartureMono-Regular.otf",
}


# ───────────────────────────── tokens ─────────────────────────────

@functools.cache
def theme(theme_id: str) -> dict:
    with open(THEMES_DIR / f"{theme_id}.toml", "rb") as fh:
        return tomllib.load(fh)


def color(theme_id: str, key: str) -> str:
    """#rrggbb for a color token (ARGB tokens such as accentSoft are returned as #aarrggbb)."""
    return theme(theme_id)["color"][key]


def rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 8:          # tokens use ARGB (alpha first) for translucent values
        h = h[2:]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def argb_alpha(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16) / 255 if len(h) == 8 else 1.0


def rgba_css(hex_color: str, alpha: float) -> str:
    r, g, b = rgb(hex_color)
    return f"rgba({r}, {g}, {b}, {alpha:g})"


def mix(a: str, b: str, t: float) -> str:
    """Blend two #rrggbb colors in sRGB: t=0 -> a, t=1 -> b."""
    ra, ga, ba = rgb(a)
    rb, gb, bb = rgb(b)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in ((ra, rb), (ga, gb), (ba, bb)))


# ───────────────────────────── Morse ─────────────────────────────

@dataclass(frozen=True)
class MarkGeometry:
    """Proportions of the brand mark, in units of the dot diameter.

    These are the proportions of the approved bar mark (design/mockups/desktop.html: dot 3.2,
    dash 8, gap 2.4, letter gap 2.4+3.2) — the mark is the same object at every size.
    """
    dot: float = 1.0
    dash: float = 2.5
    gap: float = 0.75
    letter_gap: float = 1.75

    @property
    def width(self) -> float:
        n_dots = sum(letter.count(".") for letter in MORSE)
        n_dashes = sum(letter.count("-") for letter in MORSE)
        n_gaps = sum(len(letter) - 1 for letter in MORSE)
        return n_dots * self.dot + n_dashes * self.dash + n_gaps * self.gap + (len(MORSE) - 1) * self.letter_gap


MARK = MarkGeometry()


def mark_elements(d: float, x0: float = 0.0, y0: float = 0.0, geo: MarkGeometry = MARK):
    """Yield (x, y, w, h, is_dash, letter_index) for the linear mark with dot diameter d."""
    x = x0
    for li, letter in enumerate(MORSE):
        for si, sym in enumerate(letter):
            w = (geo.dot if sym == "." else geo.dash) * d
            yield x, y0, w, d, sym == "-", li
            x += w
            if si < len(letter) - 1:
                x += geo.gap * d
        if li < len(MORSE) - 1:
            x += geo.letter_gap * d


def burst_path(x0: float, y: float, u: float, h: float, lead: float = 70.0) -> tuple[str, float]:
    """The wallpaper's square-wave Morse burst (as in design/mockups/desktop.html).

    International timing: dot = 1u, dash = 3u, gap = 1u, letter gap = 3u.
    Returns (svg path d, x_end) where x_end is the end of the burst (before the trailing lead).
    """
    x = x0
    d = f"M {x0 - lead:.3f} {y:.3f} L {x0:.3f} {y:.3f}"
    for li, letter in enumerate(MORSE):
        for si, sym in enumerate(letter):
            w = (1 if sym == "." else 3) * u
            d += f" L {x:.3f} {y - h:.3f} L {x + w:.3f} {y - h:.3f} L {x + w:.3f} {y:.3f}"
            x += w
            if si < len(letter) - 1:
                d += f" L {x + u:.3f} {y:.3f}"
                x += u
        if li < len(MORSE) - 1:
            d += f" L {x + 3 * u:.3f} {y:.3f}"
            x += 3 * u
    d += f" L {x + lead:.3f} {y:.3f}"
    return d, x


BURST_UNITS = 27  # width of the burst in u (5 + 11 + 5 + 2*3)


# ───────────────────────────── type → paths ─────────────────────────────

class Face:
    """One font file; converts text to SVG path data with GPOS pair kerning."""

    def __init__(self, filename: str):
        from fontTools.ttLib import TTFont
        self.path = FONTS / filename
        self.font = TTFont(self.path)
        self.upm = self.font["head"].unitsPerEm
        self.cmap = self.font.getBestCmap()
        self.glyphset = self.font.getGlyphSet()
        self.hmtx = self.font["hmtx"]
        os2 = self.font["OS/2"]
        self.cap_height = getattr(os2, "sCapHeight", 0) or 700
        self.x_height = getattr(os2, "sxHeight", 0) or 500
        self.ascender = os2.sTypoAscender
        self.descender = os2.sTypoDescender
        self._kern = self._load_kerning()

    # GPOS 'kern' PairPos (formats 1 and 2, through Extension lookups)
    def _load_kerning(self):
        pairs: dict[tuple[str, str], int] = {}
        class_subtables = []
        if "GPOS" not in self.font:
            return pairs, class_subtables
        gpos = self.font["GPOS"].table
        kern_lookups = set()
        for fr in gpos.FeatureList.FeatureRecord:
            if fr.FeatureTag == "kern":
                kern_lookups.update(fr.Feature.LookupListIndex)
        for li in sorted(kern_lookups):
            lookup = gpos.LookupList.Lookup[li]
            for st in lookup.SubTable:
                if lookup.LookupType == 9:
                    st = st.ExtSubTable
                if getattr(st, "LookupType", 2) != 2 and lookup.LookupType not in (2, 9):
                    continue
                if st.Format == 1:
                    for first, pset in zip(st.Coverage.glyphs, st.PairSet):
                        for rec in pset.PairValueRecord:
                            v = getattr(rec.Value1, "XAdvance", 0) if rec.Value1 else 0
                            pairs.setdefault((first, rec.SecondGlyph), v)
                elif st.Format == 2:
                    class_subtables.append(st)
        return pairs, class_subtables

    def kerning(self, left: str, right: str) -> int:
        pairs, class_subtables = self._kern
        if (left, right) in pairs:
            return pairs[(left, right)]
        for st in class_subtables:
            if left not in st.Coverage.glyphs:
                continue
            c1 = st.ClassDef1.classDefs.get(left, 0)
            c2 = st.ClassDef2.classDefs.get(right, 0)
            rec = st.Class1Record[c1].Class2Record[c2]
            v = getattr(rec.Value1, "XAdvance", 0) if rec.Value1 else 0
            if v:
                return v
        return 0

    def glyph_name(self, ch: str) -> str:
        return self.cmap[ord(ch)]

    def layout(self, text: str, size: float, tracking_em: float = 0.0, kern: bool = True):
        """Return [(glyph_name, x_in_px)] and total advance (without trailing tracking)."""
        scale = size / self.upm
        x = 0.0
        out = []
        names = [self.glyph_name(c) for c in text]
        for i, g in enumerate(names):
            out.append((g, x))
            adv = self.hmtx[g][0] * scale
            if kern and i + 1 < len(names):
                adv += self.kerning(g, names[i + 1]) * scale
            if i + 1 < len(names):
                adv += tracking_em * size
            x += adv
        return out, x

    def path_d(self, text: str, size: float, x: float = 0.0, baseline: float = 0.0,
               tracking_em: float = 0.0, kern: bool = True, precision: int = 2) -> tuple[str, float]:
        """SVG path data for text set at `size` px with its baseline at y=baseline. Returns (d, width)."""
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.pens.transformPen import TransformPen
        scale = size / self.upm
        glyphs, width = self.layout(text, size, tracking_em, kern)
        parts = []
        for g, gx in glyphs:
            pen = SVGPathPen(self.glyphset, ntos=lambda v: f"{v:.{precision}f}".rstrip("0").rstrip("."))
            tpen = TransformPen(pen, (scale, 0, 0, -scale, x + gx, baseline))
            self.glyphset[g].draw(tpen)
            parts.append(pen.getCommands())
        return " ".join(p for p in parts if p), width

    def ink_bounds(self, text: str, size: float, tracking_em: float = 0.0):
        """(xmin, ymin, xmax, ymax) of the inked outline in px, y down, baseline at 0."""
        from fontTools.pens.boundsPen import BoundsPen
        scale = size / self.upm
        glyphs, _ = self.layout(text, size, tracking_em)
        xmin = ymin = math.inf
        xmax = ymax = -math.inf
        for g, gx in glyphs:
            bp = BoundsPen(self.glyphset)
            self.glyphset[g].draw(bp)
            if bp.bounds is None:
                continue
            bx0, by0, bx1, by1 = bp.bounds
            xmin = min(xmin, gx + bx0 * scale)
            xmax = max(xmax, gx + bx1 * scale)
            ymin = min(ymin, -by1 * scale)
            ymax = max(ymax, -by0 * scale)
        return xmin, ymin, xmax, ymax


@functools.cache
def face(kind: str = "sans", weight: int = 400) -> Face:
    return Face(FONT_FILES[(kind, weight)])


def font_face_css(prefix: str = "") -> str:
    """@font-face rules for HTML previews (fonts are referenced from design/fonts, never copied)."""
    rules = []
    for (kind, weight), fn in FONT_FILES.items():
        fam = {"sans": "Plex Sans", "mono": "Plex Mono", "pixel": "Departure"}[kind]
        rules.append(f'@font-face {{ font-family: "{fam}"; src: url("{(FONTS / fn).as_uri()}"); font-weight: {weight}; }}')
    return "\n".join(rules)


# ───────────────────────────── rendering ─────────────────────────────

class Renderer:
    """Headless Chromium for SVG/HTML -> PNG. Use as a context manager."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch()
        return self

    def __exit__(self, *exc):
        self.browser.close()
        self._pw.stop()

    def page(self, width: int, height: int, scale: float = 1.0):
        ctx = self.browser.new_context(viewport={"width": int(width), "height": int(height)},
                                       device_scale_factor=scale)
        return ctx.new_page()

    def html(self, html: str, width: int, height: int, out: pathlib.Path | str, scale: float = 1.0,
             transparent: bool = False, base: pathlib.Path | None = None, wait_ms: int = 60) -> pathlib.Path:
        out = pathlib.Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        page = self.page(width, height, scale)
        tmp = (base or OUT) / f".render-{out.stem}.html"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(html, encoding="utf-8")
        try:
            page.goto(tmp.as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(wait_ms)
            page.screenshot(path=str(out), omit_background=transparent,
                            clip={"x": 0, "y": 0, "width": width, "height": height})
        finally:
            page.context.close()
            with contextlib.suppress(FileNotFoundError):
                tmp.unlink()
        return out

    def svg(self, svg: str, width: int, height: int, out, scale: float = 1.0, background: str | None = None):
        bg = f"background:{background};" if background else "background:transparent;"
        doc = (f"<!doctype html><html><head><meta charset='utf-8'><style>html,body{{margin:0;padding:0;{bg}"
               f"width:{width}px;height:{height}px;overflow:hidden}} svg{{display:block;width:{width}px;"
               f"height:{height}px}}</style></head><body>{svg}</body></html>")
        return self.html(doc, width, height, out, scale=scale, transparent=background is None)


def write(path: pathlib.Path | str, text: str) -> pathlib.Path:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def rel(path: pathlib.Path) -> str:
    return str(pathlib.Path(path).resolve().relative_to(ROOT))
