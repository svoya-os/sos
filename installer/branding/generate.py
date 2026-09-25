#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Render the installer's branding images (Graphite palette, DESIGN.md) with Pillow.

    python3 installer/branding/generate.py      # writes installer/branding/svoya/*.png

The images are committed; this script documents how they were made. At package build time the
branding team's lockup (branding/out/logo) replaces welcome.png when it exists.
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE / "svoya"
WALL = (12, 13, 15, 255)          # #0c0d0f
TEXT = (235, 232, 225, 255)       # #ebe8e1
DIM = (157, 154, 146, 255)        # #9d9a92
ACCENT = (255, 181, 71, 255)      # #ffb547


def morse(draw: ImageDraw.ImageDraw, x: float, y: float, unit: float) -> float:
    """Draw ··· ——— ··· (СОС / SOS); the dashes carry the accent. Returns the end x."""
    h = unit
    for group, color, width in ((3, TEXT, unit), (3, ACCENT, unit * 3), (3, TEXT, unit)):
        for _ in range(group):
            draw.rounded_rectangle((x, y, x + width, y + h), radius=h / 2, fill=color)
            x += width + unit
        x += unit * 2
    return x - unit * 3


def morse_width(unit: float) -> float:
    return (3 * unit + 3 * unit) + (3 * unit * 3 + 3 * unit) + (3 * unit + 3 * unit) + 2 * 2 * unit - unit


def font(size: int, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    path = ROOT / "design" / "fonts" / f"IBMPlexSans-{weight}.ttf"
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def logo() -> None:
    im = Image.new("RGBA", (320, 80), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    morse(d, 12, 32, 12)
    im.save(OUT / "logo.png", optimize=True)


def icon() -> None:
    src = ROOT / "branding" / "logo" / "icon" / "png" / "svoya-128.png"
    if src.exists():
        Image.open(src).convert("RGBA").save(OUT / "icon.png", optimize=True)
        return
    im = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, 127, 127), radius=28, fill=WALL)
    morse(d, 10, 58, 5)
    im.save(OUT / "icon.png", optimize=True)


def welcome() -> None:
    im = Image.new("RGBA", (800, 360), WALL)
    d = ImageDraw.Draw(im)
    morse(d, 400 - morse_width(14) / 2, 120, 14)
    d.text((400, 205), "SOS  ·  СОС", font=font(44, "Light"), fill=TEXT, anchor="mm")
    d.text((400, 262), "Svoya Operating System · Своя Операционная Система", font=font(18), fill=DIM,
           anchor="mm")
    im.save(OUT / "welcome.png", optimize=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    logo()
    icon()
    welcome()
    for p in sorted(OUT.glob("*.png")):
        print(p.relative_to(ROOT), Image.open(p).size)
