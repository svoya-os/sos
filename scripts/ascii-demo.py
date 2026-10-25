#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Records an SOS ASCII effect (cli/svoya_cli/ascii) to MP4 and GIF, or to a contact sheet of
frames: the demo clips and the previews. Draws the same canvas the terminal shows, cell by cell,
with DejaVu Sans Mono; block and box characters are drawn as rectangles, as terminals do.

  scripts/ascii-demo.py eye-story  out.mp4 [--gif out.gif]       the 14-second film
  scripts/ascii-demo.py eye        out.mp4 --script states        idle, thinking, listening, done, error
  scripts/ascii-demo.py planets    out.mp4 --seconds 15          (also rain, logo, heart)
  scripts/ascii-demo.py eye        --sheet sheet.png --times 1,2.5,4 [--cols 80 --rows 24]

Needs Pillow and ffmpeg (a development machine, not SOS itself).
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from svoya_cli.ascii.engine import PALETTE, Canvas  # noqa: E402

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
SHADE = {"░": 0.25, "▒": 0.5, "▓": 0.75}


def rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


class Raster:
    def __init__(self, cw: int = 10, chh: int = 20, size: int = 16):
        self.cw, self.chh = cw, chh
        self.font = ImageFont.truetype(FONT, size)
        self.bg = rgb(PALETTE["bg"])
        self.slots = {0: rgb(PALETTE["noise"]), 1: rgb(PALETTE["fg"]), 2: rgb(PALETTE["accent"]),
                      3: rgb(PALETTE["noise"])}
        self.cache: dict[tuple[str, int], Image.Image] = {}

    def tile(self, c: str, slot: int) -> Image.Image:
        key = (c, slot)
        if key in self.cache:
            return self.cache[key]
        cw, chh, fg, bg = self.cw, self.chh, self.slots[slot], self.bg
        im = Image.new("RGB", (cw, chh), bg)
        d = ImageDraw.Draw(im)
        mx, my = cw // 2, chh // 2
        if c == "█":
            d.rectangle([0, 0, cw - 1, chh - 1], fill=fg)
        elif c == "▀":
            d.rectangle([0, 0, cw - 1, my - 1], fill=fg)
        elif c == "▄":
            d.rectangle([0, my, cw - 1, chh - 1], fill=fg)
        elif c == "▌":
            d.rectangle([0, 0, mx - 1, chh - 1], fill=fg)
        elif c == "▐":
            d.rectangle([mx, 0, cw - 1, chh - 1], fill=fg)
        elif c in SHADE:
            a = SHADE[c]
            d.rectangle([0, 0, cw - 1, chh - 1], fill=tuple(int(b + (f - b) * a) for f, b in zip(fg, bg)))
        elif c in "─│┌┐└┘":
            if c in "─┌┐└┘":
                x0 = mx if c in "┌└" else 0
                x1 = mx if c in "┐┘" else cw - 1
                d.line([x0, my, x1, my], fill=fg)
            if c in "│┌┐└┘":
                y0 = my if c in "┌┐" else 0
                y1 = my if c in "└┘" else chh - 1
                d.line([mx, y0, mx, y1], fill=fg)
        elif c != " ":
            d.text((mx, my), c, font=self.font, fill=fg, anchor="mm")
        self.cache[key] = im
        return im

    def image(self, cv: Canvas, base: Image.Image | None = None, prev: Canvas | None = None) -> Image.Image:
        im = base or Image.new("RGB", (cv.w * self.cw, cv.h * self.chh), self.bg)
        for k in range(cv.w * cv.h):
            c, s = cv.ch[k], cv.co[k]
            if prev is not None and prev.ch[k] == c and prev.co[k] == s:
                continue
            im.paste(self.tile(c, s), ((k % cv.w) * self.cw, (k // cv.w) * self.chh))
        return im


def make(name: str, state: str):
    from svoya_cli.ascii.eye import Eye
    from svoya_cli.ascii.heart import Heart
    from svoya_cli.ascii.logo import Logo
    from svoya_cli.ascii.planets import Planets
    from svoya_cli.ascii.rain import Rain
    if name == "eye-story":
        return Eye(story=True, night=False, clock=lambda: "21:47")
    if name == "eye":
        return Eye(state=state, night=False, clock=lambda: "21:47")
    if name == "planets":
        return Planets()
    if name in ("rain", "logo", "heart"):
        return {"rain": Rain, "logo": Logo, "heart": Heart}[name]()
    raise SystemExit(f"unknown effect {name}")


def states_script(eye, t: float, fired: set) -> None:
    """--script states: what the demo of Jackson's states does over 15 seconds."""
    plan = [(3.0, "2"), (6.0, "3"), (8.6, "4"), (10.4, "5"), (12.4, "1")]
    for at, k in plan:
        if t >= at and at not in fired:
            fired.add(at)
            eye.key(k, at)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("effect", choices=["eye", "eye-story", "planets", "rain", "logo", "heart"])
    ap.add_argument("out", nargs="?")
    ap.add_argument("--state", default="idle")
    ap.add_argument("--script", choices=["states"])
    ap.add_argument("--cols", type=int, default=128)
    ap.add_argument("--rows", type=int, default=36)
    ap.add_argument("--seconds", type=float)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--gif")
    ap.add_argument("--sheet")
    ap.add_argument("--times", default="1,2,3,4,5,6")
    a = ap.parse_args()
    eff = make(a.effect, a.state)
    eff.resize(a.cols, a.rows)
    ras = Raster()
    if a.sheet:
        times = [float(x) for x in a.times.split(",")]
        shots = []
        fired: set = set()
        for t in times:
            if a.script:
                states_script(eff, t, fired)
            cv = Canvas(a.cols, a.rows)
            eff.draw(cv, t)
            shots.append(ras.image(cv))
        tw, th = shots[0].size
        cols = 2 if len(shots) > 1 else 1
        sheet = Image.new("RGB", (tw * cols + 8 * (cols - 1), th * ((len(shots) + cols - 1) // cols)), (40, 40, 40))
        for n, im in enumerate(shots):
            sheet.paste(im, ((n % cols) * (tw + 8), (n // cols) * th))
        sheet.save(a.sheet)
        return 0
    seconds = a.seconds or eff.duration or 15.0
    w, h = a.cols * ras.cw, a.rows * ras.chh
    ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                           f"{w}x{h}", "-r", str(a.fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                           "-crf", "18", "-preset", "medium", a.out], stdin=subprocess.PIPE)
    img, prev = None, None
    fired = set()
    for n in range(int(seconds * a.fps)):
        t = n / a.fps
        if a.script:
            states_script(eff, t, fired)
        cv = Canvas(a.cols, a.rows)
        eff.draw(cv, t)
        img = ras.image(cv, img, prev)
        prev = cv
        ff.stdin.write(img.tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        return 1
    if a.gif:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", a.out, "-vf",
                        "fps=15,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=24[p];"
                        "[b][p]paletteuse=dither=none", a.gif], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
