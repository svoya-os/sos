#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""sos-symbols: the SOS ASCII cursor theme (XCursor), drawn like the rest of the symbol layer.

    python3 branding/cursors/generate.py          writes branding/cursors/sos-symbols

The arrow is near-black with a phosphor edge (seen on dark and on light), the text cursor is a mono
I-beam, a link turns the arrow's edge pink (pink is what is alive), waiting is the terminal spinner
[|] [/] [-] [\\] and working the arrow with a small spinner; a plus for precision, arrows for moving
and resizing, a pink [×] where nothing can go, the arrow with a + to copy or zoom in and a - to
zoom out. 24, 32, 48 and 64 px.

The theme names every shape itself (the CSS names, the X11 ones and their hashes) and inherits
nothing: Hyprland's own XCursor loader keeps a theme's folders in a sorted set, so an inherited
Adwaita ("A" before "s") would win every shape both have, and the symbol cursor would never show.

Packaged by svoya-branding into /usr/share/icons/sos-symbols; the shell sets it (hyprctl setcursor,
gsettings cursor-theme) while the symbol layer covers the cursor (Settings.asciiParts).
"""
from __future__ import annotations

import math
import pathlib
import shutil
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MONO = ROOT / "design/fonts/IBMPlexMono-SemiBold.ttf"
NAME = "sos-symbols"

PHOSPHOR = (60, 255, 208, 255)
PINK = (255, 46, 136, 255)
INK = (10, 10, 10, 255)
SIZES = (24, 32, 48, 64)
SS = 8                       # supersampling
FRAME_MS = 110

# the design grid is 32 units; a size draws it scaled (24 px = 0.75)
ARROW = [(3, 2), (3, 25), (9, 19.5), (13, 28.5), (17.2, 26.8), (13.4, 18), (21, 18)]


def canvas(size: int) -> tuple[Image.Image, ImageDraw.ImageDraw, float]:
    im = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im), size * SS / 32


def finish(im: Image.Image, size: int) -> Image.Image:
    return im.resize((size, size), Image.LANCZOS)


def poly(d, pts, k, fill=None, outline=None, width=0.0):
    p = [(x * k, y * k) for x, y in pts]
    if outline and width:
        d.line(p + [p[0]], fill=outline, width=max(1, round(width * k)), joint="curve")
    if fill:
        d.polygon(p, fill=fill)


def arrow(size: int, edge=PHOSPHOR, extra=None) -> Image.Image:
    im, d, k = canvas(size)
    poly(d, ARROW, k, outline=edge, width=2.6)      # the edge, drawn wide; the fill covers its inner half
    poly(d, ARROW, k, fill=INK)
    # a little texture of symbols inside: three dots down the arrow's spine, like the eye's sclera
    for (x, y) in ((5.4, 9.5), (5.4, 14), (8.6, 14)):
        r = 0.55 * k
        d.ellipse((x * k - r, y * k - r, x * k + r, y * k + r), fill=(edge[0], edge[1], edge[2], 150))
    if extra:
        extra(d, k)
    return finish(im, size)


def glyph(d, ch: str, x: float, y: float, px: float, k: float, fill, stroke=INK):
    font = ImageFont.truetype(str(MONO), max(1, int(px * k)))
    d.text((x * k, y * k), ch, font=font, fill=fill, anchor="mm", stroke_width=max(1, int(0.9 * k)), stroke_fill=stroke)


def spinner_frames(size: int, small: bool) -> list[Image.Image]:
    frames = []
    for i, ch in enumerate("|/-\\"):
        if small:
            def extra(d, k, ch=ch):
                glyph(d, "[" + ch + "]", 22.5, 25.5, 9, k, PHOSPHOR)
            frames.append(arrow(size, extra=extra))
        else:
            im, d, k = canvas(size)
            glyph(d, "[" + ch + "]", 16, 16, 15, k, PHOSPHOR)
            frames.append(finish(im, size))
    return frames


def ibeam(size: int) -> Image.Image:
    im, d, k = canvas(size)
    for color, w in ((INK, 4.2), (PHOSPHOR, 1.8)):
        lw = max(1, round(w * k))
        d.line([(16 * k, 7 * k), (16 * k, 25 * k)], fill=color, width=lw)
        d.line([(12 * k, 6.5 * k), (20 * k, 6.5 * k)], fill=color, width=lw)
        d.line([(12 * k, 25.5 * k), (20 * k, 25.5 * k)], fill=color, width=lw)
    return finish(im, size)


def plus(size: int, arrows: bool) -> Image.Image:
    im, d, k = canvas(size)
    for color, w in ((INK, 4.0), (PHOSPHOR, 1.6)):
        lw = max(1, round(w * k))
        reach = 12 if arrows else 11
        gap = 0 if arrows else 3
        for a in range(4):
            dx, dy = round(math.cos(a * math.pi / 2)), round(math.sin(a * math.pi / 2))
            d.line([((16 + dx * gap) * k, (16 + dy * gap) * k), ((16 + dx * reach) * k, (16 + dy * reach) * k)], fill=color, width=lw)
            if arrows:
                tip = (16 + dx * 13.5, 16 + dy * 13.5)
                left = (16 + dx * 9.5 - dy * 3.5, 16 + dy * 9.5 + dx * 3.5)
                right = (16 + dx * 9.5 + dy * 3.5, 16 + dy * 9.5 - dx * 3.5)
                if color == INK:
                    poly(d, [tip, left, right], k, outline=INK, width=2.4)
                poly(d, [tip, left, right], k, fill=color)
    return finish(im, size)


def double_arrow(size: int, angle_deg: float) -> Image.Image:
    im, d, k = canvas(size)
    a = math.radians(angle_deg)
    ux, uy = math.cos(a), math.sin(a)

    def at(t, s=0.0):
        return (16 + ux * t - uy * s, 16 + uy * t + ux * s)
    for color, w in ((INK, 4.0), (PHOSPHOR, 1.7)):
        d.line([tuple(v * k for v in at(-9)), tuple(v * k for v in at(9))], fill=color, width=max(1, round(w * k)))
    for sign in (1, -1):
        head = [at(sign * 13.5), at(sign * 8.5, 4.2), at(sign * 8.5, -4.2)]
        poly(d, head, k, outline=INK, width=2.4)
        poly(d, head, k, fill=PHOSPHOR)
    return finish(im, size)


def forbidden(size: int) -> Image.Image:
    im, d, k = canvas(size)
    glyph(d, "[×]", 16, 16, 15, k, PINK)
    return finish(im, size)


def help_arrow(size: int) -> Image.Image:
    return glyph_arrow(size, "?")


def glyph_arrow(size: int, ch: str) -> Image.Image:
    return arrow(size, extra=lambda d, k: glyph(d, ch, 23, 24, 12, k, PHOSPHOR))


# cursor -> (drawing for a size [-> list of frames for animations], hotspot in the 32 grid)
CURSORS = {
    "left_ptr": (lambda s: [arrow(s)], (3, 2)),
    "xterm": (lambda s: [ibeam(s)], (16, 16)),
    "hand2": (lambda s: [arrow(s, edge=PINK)], (3, 2)),
    "watch": (lambda s: spinner_frames(s, small=False), (16, 16)),
    "left_ptr_watch": (lambda s: spinner_frames(s, small=True), (3, 2)),
    "crosshair": (lambda s: [plus(s, arrows=False)], (16, 16)),
    "fleur": (lambda s: [plus(s, arrows=True)], (16, 16)),
    "not-allowed": (lambda s: [forbidden(s)], (16, 16)),
    "question_arrow": (lambda s: [help_arrow(s)], (3, 2)),
    "copy": (lambda s: [glyph_arrow(s, "+")], (3, 2)),
    "zoom-out": (lambda s: [glyph_arrow(s, "-")], (3, 2)),
    "sb_h_double_arrow": (lambda s: [double_arrow(s, 0)], (16, 16)),
    "sb_v_double_arrow": (lambda s: [double_arrow(s, 90)], (16, 16)),
    "bd_double_arrow": (lambda s: [double_arrow(s, 45)], (16, 16)),
    "fd_double_arrow": (lambda s: [double_arrow(s, -45)], (16, 16)),
}
ALIASES = {
    "left_ptr": ["default", "arrow", "top_left_arrow", "left-arrow", "context-menu", "alias", "dnd-link",
                 "3085a0e285430894940527032f8b26df", "640fb0e74195791501fd1ed57b41487f", "a2a266d0498c3104214a47bd64ab0fc8"],
    "xterm": ["text", "ibeam", "vertical-text"],
    "hand2": ["pointer", "hand1", "hand", "pointing_hand", "9d800788f1b08800ae810202380a0822", "e29285e634086352946a0e7090d73106"],
    "watch": ["wait"],
    "left_ptr_watch": ["progress", "half-busy", "00000000000000020006000e7e9ffc3f", "08e8e1c95fe2fc01f976f1e063a24ccd",
                       "3ecb610c1bf2410f44200f48c40d3599"],
    "crosshair": ["cross", "tcross", "cross_reverse", "diamond_cross", "cell", "plus"],
    "fleur": ["move", "all-scroll", "all-resize", "size_all", "grabbing", "closedhand", "dnd-move", "grab", "openhand",
              "4498f0e0c1937ffe01fd06f973665830", "9081237383d90e509aa00f00170e968f"],
    "not-allowed": ["crossed_circle", "no-drop", "forbidden", "circle", "dnd-no-drop", "dnd-none", "X_cursor", "pirate",
                    "03b6e0fcb3499374a867c041f52298f0"],
    "copy": ["dnd-copy", "zoom-in", "1081e37283d90000800003c07f3ef6bf", "6407b0e94181790501fd1e167b474872",
             "b66166c04f8c3109214a4fbd64a50fc8"],
    "question_arrow": ["help", "whats_this", "left_ptr_help", "dnd-ask", "5c6cd98b3f3ebcb1f9c7f1c204630408",
                       "d9ce0ab605698f320427677b8b1a4aeb"],
    "sb_h_double_arrow": ["ew-resize", "col-resize", "h_double_arrow", "size_hor", "split_h", "left_side", "right_side",
                          "e-resize", "w-resize", "028006030e0e7ebffc7f7070c0600140", "14fef782d02440884392942c11205230"],
    "sb_v_double_arrow": ["ns-resize", "row-resize", "v_double_arrow", "size_ver", "split_v", "top_side", "bottom_side",
                          "n-resize", "s-resize", "00008160000006810000408080010102", "2870a09082c103050810ffdffffe0204"],
    "bd_double_arrow": ["nwse-resize", "size_fdiag", "top_left_corner", "bottom_right_corner", "nw-resize", "se-resize",
                        "c7088f0f3e6c8088236ef8e1e3e70000"],
    "fd_double_arrow": ["nesw-resize", "size_bdiag", "top_right_corner", "bottom_left_corner", "ne-resize", "sw-resize",
                        "fcf1c3c7cd4491d801f1e1c78f100000"],
}


def premultiplied_argb(im: Image.Image) -> bytes:
    raw = im.convert("RGBA").tobytes()
    out = bytearray()
    for i in range(0, len(raw), 4):
        r, g, b, a = raw[i:i + 4]
        out += struct.pack("<I", (a << 24) | ((r * a // 255) << 16) | ((g * a // 255) << 8) | (b * a // 255))
    return bytes(out)


def xcursor(images: list[tuple[int, int, int, int, Image.Image]]) -> bytes:
    """The XCursor file: [(nominal size, xhot, yhot, delay ms, image)]."""
    header = struct.pack("<4sIII", b"Xcur", 16, 0x10000, len(images))
    toc_len = 12 * len(images)
    pos = 16 + toc_len
    toc, chunks = b"", b""
    for nominal, xh, yh, delay, im in images:
        w, h = im.size
        chunk = struct.pack("<IIIIIIIII", 36, 0xFFFD0002, nominal, 1, w, h, xh, yh, delay) + premultiplied_argb(im)
        toc += struct.pack("<III", 0xFFFD0002, nominal, pos)
        pos += len(chunk)
        chunks += chunk
    return header + toc + chunks


def read_xcursor(data: bytes) -> list[tuple[int, int, int, int, int, int]]:
    """[(nominal, width, height, xhot, yhot, delay)] of a file (for the tests)."""
    magic, hsize, _, n = struct.unpack_from("<4sIII", data, 0)
    assert magic == b"Xcur" and hsize == 16
    out = []
    for i in range(n):
        typ, nominal, pos = struct.unpack_from("<III", data, 16 + 12 * i)
        assert typ == 0xFFFD0002
        hs, t2, sub, ver, w, h, xh, yh, delay = struct.unpack_from("<IIIIIIIII", data, pos)
        assert hs == 36 and t2 == typ and sub == nominal and len(data) >= pos + 36 + 4 * w * h
        out.append((nominal, w, h, xh, yh, delay))
    return out


def build(out_root: pathlib.Path = HERE) -> pathlib.Path:
    d = out_root / NAME
    if d.exists():
        shutil.rmtree(d)
    (d / "cursors").mkdir(parents=True)
    for name, (draw, (hx, hy)) in CURSORS.items():
        images = []
        for size in SIZES:
            frames = draw(size)
            for im in frames:
                images.append((size, round(hx * size / 32), round(hy * size / 32), FRAME_MS if len(frames) > 1 else 0, im))
        (d / "cursors" / name).write_bytes(xcursor(images))
        for alias in ALIASES.get(name, []):
            (d / "cursors" / alias).symlink_to(name)
    (d / "index.theme").write_text(f"[Icon Theme]\nName={NAME}\nComment=SOS ASCII: the cursor of the symbol layer\n",
                                   encoding="utf-8")
    return d


def preview(d: pathlib.Path, path: pathlib.Path) -> None:
    """A sheet of every cursor at 48 px (frames side by side) on dark and on light."""
    names = list(CURSORS)
    tiles = []
    for name in names:
        draw, _ = CURSORS[name]
        tiles.append(draw(48))
    w = 20 + sum(max(1, len(t)) * 52 + 16 for t in tiles)
    sheet = Image.new("RGBA", (w, 140), (0, 0, 0, 0))
    for row, bg in enumerate(((22, 24, 23, 255), (244, 242, 236, 255))):
        band = Image.new("RGBA", (w, 70), bg)
        sheet.paste(band, (0, row * 70))
        x = 20
        for frames in tiles:
            for im in frames:
                sheet.alpha_composite(im, (x, row * 70 + 11))
                x += 52
            x += 16
    sheet.save(path)


if __name__ == "__main__":
    out = build()
    n = sum(1 for p in (out / "cursors").iterdir() if not p.is_symlink())
    print(f"{out.relative_to(ROOT)}: {n} cursors, {len(list((out / 'cursors').iterdir())) - n} names more", file=sys.stderr)
    if len(sys.argv) > 1:
        preview(out, pathlib.Path(sys.argv[1]))
