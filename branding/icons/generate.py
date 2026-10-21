#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""SOS-Symbols icon themes: the folders of SOS ASCII, drawn in characters (IBM Plex Mono glyphs
turned into paths, so no font is needed to show them), over Papirus for everything else.

    python3 branding/icons/generate.py            writes branding/icons/SOS-Symbols-Dark and -Light

A folder is drawn on a grid of 16 × 8 cells (twice as tall as wide, like a terminal) with heavy
box-drawing lines — the tab, the body, the front flap — a dim dotted back and a dotted front, so the
silhouette stays a clean outline even at 32 px; the places get a pink mark on the front ([ ~ ] home,
[ ↓ ] downloads, [doc], [img], [mp3], [dsk]…), pink being what is alive in SOS ASCII (and the flap of a
folder a file is dragged onto). 16–24 px are line drawings on the pixel grid: characters do not
survive at that size.

Packaged by svoya-branding into /usr/share/icons; the shell switches GTK to it while the symbol
layer covers folders (Settings.asciiParts), `sos theme apply` agrees (cli/svoya_cli/theme/symbols.py).
"""
from __future__ import annotations

import pathlib
import shutil
import sys

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FONTS = {"regular": ROOT / "design/fonts/IBMPlexMono-Regular.ttf", "bold": ROOT / "design/fonts/IBMPlexMono-SemiBold.ttf"}

PALETTES = {
    "Dark": {"fg": "#3cffd0", "dim": "#1f9e82", "alive": "#ff2e88", "base": "Papirus-Dark"},
    "Light": {"fg": "#0b6b58", "dim": "#4f9686", "alive": "#d6246e", "base": "Papirus-Light"},
}
# name -> the pink mark on the front ("" = none); aliases share a drawing
PLACES = {
    "folder": "", "folder-open": "", "folder-drag-accept": "", "user-home": "~", "user-desktop": "dsk",
    "folder-documents": "doc", "folder-download": "↓", "folder-music": "mp3", "folder-pictures": "img",
    "folder-videos": "vid", "folder-templates": "{}", "folder-publicshare": "pub", "folder-remote": "@",
}
ALIASES = {"inode-directory": "folder", "folder-downloads": "folder-download", "folder-image": "folder-pictures",
           "folder-video": "folder-videos", "folder-documents-open": "folder-open", "user-documents": "folder-documents",
           "user-downloads": "folder-download", "user-music": "folder-music", "user-pictures": "folder-pictures",
           "user-videos": "folder-videos", "folder-network": "folder-remote"}
TRASH_ICONS = ("user-trash", "user-trash-full")

N = 96            # the design canvas (scalable icons)
COLS, ROWS = 16, 8


class Glyphs:
    """Character outlines as SVG path data, one advance = one cell."""

    def __init__(self, path: pathlib.Path):
        self.font = TTFont(str(path))
        self.cmap = self.font.getBestCmap()
        self.gs = self.font.getGlyphSet()
        self.upm = self.font["head"].unitsPerEm
        self.adv = self.font["hmtx"]["M"][0]
        self.cap = getattr(self.font["OS/2"], "sCapHeight", 700) or 700
        self.cache: dict[tuple, str] = {}

    def path(self, ch: str, x: float, y: float, cw: float, ch_h: float) -> str:
        """The glyph `ch` in the cell (x, y, cw × ch_h): one advance wide, caps centered."""
        key = (ch, round(x, 3), round(y, 3), round(cw, 3), round(ch_h, 3))
        if key in self.cache:
            return self.cache[key]
        name = self.cmap.get(ord(ch))
        if not name:
            return ""
        s = cw / self.adv
        base = y + ch_h / 2 + self.cap * s / 2
        pen = SVGPathPen(self.gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        self.gs[name].draw(TransformPen(pen, (s, 0, 0, -s, x, base)))
        d = pen.getCommands()
        self.cache[key] = d
        return d


# ---- drawings -----------------------------------------------------------------------------------
# rows of 16 cells; a letter in LEGEND picks the color of the character under it (default fg)
FOLDER = [
    "┏━━━━━┓         ",
    "┃/////┗━━━━━━━━┓",
    "┃ : : : : : : :┃",
    "┣━━━━━━━━━━━━━━┫",
    "┃ · · · · · · ·┃",
    "┃ · · · · · · ·┃",
    "┃ · · · · · · ·┃",
    "┗━━━━━━━━━━━━━━┛",
]
FOLDER_COLORS = [
    "fffffff         ",
    "fdddddffffffffff",
    "fdddddddddddddff",
    "ffffffffffffffff",
    "fddddddddddddddf",
    "fddddddddddddddf",
    "fddddddddddddddf",
    "ffffffffffffffff",
]
TRASH = [
    "     ┏━━━━┓     ",
    "  ━━━┻━━━━┻━━━  ",
    "   ┃ │ │ │ │ ┃  ",
    "   ┃ │ │ │ │ ┃  ",
    "   ┃ │ │ │ │ ┃  ",
    "   ┃ │ │ │ │ ┃  ",
    "   ┃ │ │ │ │ ┃  ",
    "   ┗━━━━━━━━┛   ",
]
TRASH_COLORS = [
    "     dddddd     ",
    "  ffffffffffff  ",
    "   fdddddddddf  ",
    "   fdddddddddf  ",
    "   fdddddddddf  ",
    "   fdddddddddf  ",
    "   fdddddddddf  ",
    "   ffffffffff   ",
]
LEGEND = {"f": "fg", "d": "dim", "a": "alive"}


def draw(rows, colors):
    cells = {}
    for r, (row, cols) in enumerate(zip(rows, colors)):
        for c, ch in enumerate(row):
            if ch != " ":
                cells[(c, r)] = (ch, LEGEND.get(cols[c], "fg"))
    return cells


def folder(kind: str = "closed"):
    """closed; open (the flap dashed, the front lit); drop (a file is dragged onto it: the flap pink)."""
    cells = draw(FOLDER, FOLDER_COLORS)
    if kind in ("open", "drop"):
        for c in range(1, COLS - 1):
            cells[(c, 3)] = ("╍", "alive" if kind == "drop" else "fg")
        for r in (4, 5, 6):
            for c in range(2, COLS - 1, 2):
                cells[(c, r)] = ("+", "fg")
    return cells


def trash(full: bool):
    cells = draw(TRASH, TRASH_COLORS)
    if full:
        for c, ch in ((1, "%"), (2, "@"), (3, "*"), (12, "#"), (13, "%"), (14, "&")):
            cells[(c, 0)] = (ch, "alive")
        for c in (5, 7, 9, 11):
            for r in (2, 3):
                cells[(c, r)] = ("#" if (c + r) % 2 else "%", "alive")
    return cells


def put_mark(cells, mark: str, row: int):
    """[ mark ] in the middle of the front: brackets in phosphor, the mark pink, air around."""
    if not mark:
        return
    label = "[" + (f" {mark} " if len(mark) == 1 else mark) + "]"
    c0 = (COLS - len(label)) // 2
    for c in range(max(1, c0 - 1), min(COLS - 1, c0 + len(label) + 1)):
        cells.pop((c, row), None)
    for i, ch in enumerate(label):
        cells[(c0 + i, row)] = (ch, "fg" if ch in "[]" else "alive")


# ---- SVG ---------------------------------------------------------------------------------------------
PAD = 6           # air around the drawing, as other icon themes leave


def svg_cells(cells, pal, glyphs, bold) -> str:
    cw, ch = (N - 2 * PAD) / COLS, (N - 2 * PAD) / ROWS
    groups: dict[str, list[str]] = {}
    for (c, r), (char, slot) in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if char == " ":
            continue
        g = bold if slot == "alive" else glyphs
        d = g.path(char, PAD + c * cw, PAD + r * ch, cw, ch)
        if d:
            groups.setdefault(slot, []).append(d)
    body = "".join(f'<path fill="{pal[slot]}" d="{" ".join(ds)}"/>' for slot, ds in groups.items())
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{N}" height="{N}" viewBox="0 0 {N} {N}">{body}</svg>\n'


def svg_small(size: int, pal, mark: bool, kind: str = "folder") -> str:
    """16/22/24 px: a line drawing on the pixel grid (1 px strokes at 16, 1.5 at 22–24)."""
    s = size / 16
    w = 1 if size <= 16 else 1.5
    fg, alive = pal["fg"], pal["alive"]
    h = w / 2

    def p(v):
        return round(v * s * 2) / 2

    if kind == "trash":
        body = (f'<path fill="none" stroke="{fg}" stroke-width="{w}" d="M{p(3)+h} {p(4)+h}H{p(13)-h}M{p(6)+h} {p(4)+h}V{p(2)+h}H{p(10)-h}V{p(4)+h}'
                f'M{p(4)+h} {p(5)+h}L{p(5)+h} {p(14)-h}H{p(11)-h}L{p(12)-h} {p(5)+h}"/>')
        if mark:
            body += f'<rect x="{p(6.5)}" y="{p(7)}" width="{p(3)}" height="{p(2)}" fill="{alive}"/>'
    else:
        body = (f'<path fill="none" stroke="{fg}" stroke-width="{w}" stroke-linejoin="miter" '
                f'd="M{p(1.5)+h} {p(3)+h}H{p(6)}L{p(7.5)} {p(4.5)+h}H{p(14.5)-h}V{p(13)-h}H{p(1.5)+h}Z'
                f'M{p(1.5)+h} {p(6.5)+h}H{p(14.5)-h}"/>')
        if mark:
            body += f'<rect x="{p(6.5)}" y="{p(8.5)}" width="{p(3)}" height="{max(1, p(1.5))}" fill="{alive}"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">{body}</svg>\n'


INDEX = """[Icon Theme]
Name={name}
Comment=SOS ASCII: folders drawn in characters, over {base}
Inherits={base},Papirus,hicolor
Example=folder
Directories=16x16/places,22x22/places,24x24/places,scalable/places,16x16/mimetypes,22x22/mimetypes,24x24/mimetypes,scalable/mimetypes
{dirs}"""


def index_dirs() -> str:
    out = []
    for ctx in ("places", "mimetypes"):
        for size in (16, 22, 24):
            out.append(f"\n[{size}x{size}/{ctx}]\nSize={size}\nContext={ctx.capitalize()}\nType=Fixed\n")
        out.append(f"\n[scalable/{ctx}]\nSize=64\nMinSize=32\nMaxSize=512\nContext={ctx.capitalize()}\nType=Scalable\n")
    return "".join(out)


def build(out_root: pathlib.Path = HERE) -> list[pathlib.Path]:
    glyphs, bold = Glyphs(FONTS["regular"]), Glyphs(FONTS["bold"])
    written = []
    for variant, pal in PALETTES.items():
        name = f"SOS-Symbols-{variant}"
        d = out_root / name
        if d.exists():
            shutil.rmtree(d)
        drawings = {}
        for icon, mark in PLACES.items():
            cells = folder({"folder-open": "open", "folder-drag-accept": "drop"}.get(icon, "closed"))
            put_mark(cells, mark, 5)
            drawings[icon] = (svg_cells(cells, pal, glyphs, bold), {sz: svg_small(sz, pal, bool(mark)) for sz in (16, 22, 24)})
        for icon in TRASH_ICONS:
            cells = trash(icon.endswith("full"))
            drawings[icon] = (svg_cells(cells, pal, glyphs, bold),
                              {sz: svg_small(sz, pal, icon.endswith("full"), "trash") for sz in (16, 22, 24)})
        for icon, (big, small) in drawings.items():
            ctx = "places"
            (d / "scalable" / ctx).mkdir(parents=True, exist_ok=True)
            (d / "scalable" / ctx / f"{icon}.svg").write_text(big, encoding="utf-8")
            for sz, svg in small.items():
                (d / f"{sz}x{sz}" / ctx).mkdir(parents=True, exist_ok=True)
                (d / f"{sz}x{sz}" / ctx / f"{icon}.svg").write_text(svg, encoding="utf-8")
        for alias, target in ALIASES.items():
            ctx = "mimetypes" if alias.startswith("inode-") else "places"
            for sub in ("scalable", "16x16", "22x22", "24x24"):
                (d / sub / ctx).mkdir(parents=True, exist_ok=True)
                link = d / sub / ctx / f"{alias}.svg"
                link.symlink_to(f"{target}.svg" if ctx == "places" else f"../places/{target}.svg")
        (d / "index.theme").write_text(INDEX.format(name=name, base=pal["base"], dirs=index_dirs()), encoding="utf-8")
        written.append(d)
    return written


if __name__ == "__main__":
    for d in build():
        n = sum(1 for _ in d.rglob("*.svg"))
        print(f"{d.relative_to(ROOT)}: {n} icons", file=sys.stderr)
