#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate the small raster textures used by the Svoya Shell wallpaper.

Python stdlib only (zlib + struct), deterministic (fixed seeds), so the PNGs in
shell/assets/textures/ can be regenerated and reviewed byte-for-byte.

    python3 shell/tools/gen_textures.py

Why rasters: Qt Quick has no CSS blend modes and custom shaders would need the
`qsb` compiler at build time. Tiled PNGs drawn with a low Image.opacity give the
same look as design/mockups/desktop.css:

* grain-dark.png   dark themes. The mockup uses a 50% grey noise with
                   `mix-blend-mode: overlay`, which is visually a no-op on dark
                   walls; we keep a very faint symmetric light/dark speckle that
                   mostly acts as dithering against banding in the large glows.
* grain-light.png  light themes: `multiply` of 50% grey noise == black specks
                   with alpha 0.5 * noise (drawn at Theme.grain opacity).
* dots.png/@2x     Paper dot grid: radial-gradient(circle, rgba(21,21,21,.13)
                   0.9px, transparent 1.25px) / 22px 22px.
* scanlines.png/@2x Phosphor: repeating-linear-gradient(transparent 0 2px,
                   rgba(0,0,0,.22) 2px 3px), multiply == black at alpha .22.
"""
import math
import pathlib
import random
import struct
import zlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "assets" / "textures"


def write_png(path: pathlib.Path, width: int, height: int, rgba: bytearray) -> None:
    """Write an 8-bit RGBA PNG (no filtering, max compression)."""
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw.extend(rgba[y * stride:(y + 1) * stride])

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def tileable_value_noise(size: int, cell: float, rng: random.Random) -> list[list[float]]:
    """Seamless value noise in [0, 1] on a torus (bicubic-smoothed lattice)."""
    n = max(2, round(size / cell))
    lattice = [[rng.random() for _ in range(n)] for _ in range(n)]
    out = [[0.0] * size for _ in range(size)]
    for y in range(size):
        fy = y / size * n
        y0 = int(fy) % n
        y1 = (y0 + 1) % n
        ty = fy - int(fy)
        ty = ty * ty * (3 - 2 * ty)
        for x in range(size):
            fx = x / size * n
            x0 = int(fx) % n
            x1 = (x0 + 1) % n
            tx = fx - int(fx)
            tx = tx * tx * (3 - 2 * tx)
            a = lattice[y0][x0] + (lattice[y0][x1] - lattice[y0][x0]) * tx
            b = lattice[y1][x0] + (lattice[y1][x1] - lattice[y1][x0]) * tx
            out[y][x] = a + (b - a) * ty
    return out


def fractal(size: int, seed: int) -> list[list[float]]:
    """Three octaves, roughly feTurbulence(baseFrequency=.85, numOctaves=3)."""
    rng = random.Random(seed)
    octaves = [(1.2, 0.55), (2.4, 0.3), (4.8, 0.15)]
    acc = [[0.0] * size for _ in range(size)]
    for cell, weight in octaves:
        layer = tileable_value_noise(size, cell, rng)
        for y in range(size):
            row, src = acc[y], layer[y]
            for x in range(size):
                row[x] += src[x] * weight
    return acc


def grain(size: int = 256) -> None:
    field = fractal(size, seed=0x5C05)
    dark = bytearray(size * size * 4)
    light = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            v = field[y][x]                      # ~[0, 1], mean ~0.5
            i = (y * size + x) * 4
            # dark: symmetric speckle, +-0.18 alpha around neutral
            d = max(-1.0, min(1.0, (v - 0.5) * 2.4))
            c = 255 if d > 0 else 0
            dark[i:i + 4] = bytes((c, c, c, int(abs(d) * 0.18 * 255)))
            # light: multiply of 50% grey with alpha (1.4a - 0.2) == black at 0.5*alpha
            a = max(0.0, min(1.0, 1.4 * v - 0.2))
            light[i:i + 4] = bytes((0, 0, 0, int(a * 0.5 * 255)))
    write_png(OUT / "grain-dark.png", size, size, dark)
    write_png(OUT / "grain-light.png", size, size, light)


def dots(scale: int) -> None:
    size = 22 * scale
    cx = cy = 11 * scale - 0.5
    inner, outer = 0.9 * scale, 1.25 * scale
    buf = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            # 4x4 supersampling for a clean antialiased dot
            cov = 0.0
            for sy in range(4):
                for sx in range(4):
                    dx = x + (sx + 0.5) / 4 - 0.5 - cx
                    dy = y + (sy + 0.5) / 4 - 0.5 - cy
                    r = math.hypot(dx, dy)
                    if r <= inner:
                        cov += 1
                    elif r < outer:
                        cov += (outer - r) / (outer - inner)
            cov /= 16
            i = (y * size + x) * 4
            buf[i:i + 4] = bytes((21, 21, 21, int(round(cov * 0.13 * 255))))
    name = "dots.png" if scale == 1 else f"dots@{scale}x.png"
    write_png(OUT / name, size, size, buf)


def scanlines(scale: int) -> None:
    w, h = 4 * scale, 3 * scale
    buf = bytearray(w * h * 4)
    for y in range(h):
        on = y >= 2 * scale
        for x in range(w):
            i = (y * w + x) * 4
            buf[i:i + 4] = bytes((0, 0, 0, int(0.22 * 255) if on else 0))
    name = "scanlines.png" if scale == 1 else f"scanlines@{scale}x.png"
    write_png(OUT / name, w, h, buf)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    grain()
    for s in (1, 2):
        dots(s)
        scanlines(s)
    for p in sorted(OUT.glob("*.png")):
        print(p.relative_to(OUT.parent.parent), p.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
