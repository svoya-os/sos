"""Tiny pixel-art toolkit for the Jackson mascot concepts (SOS).

A sprite is a 32×32 grid of palette keys (None = transparent). Parts are drawn with a few
primitives (ellipse, polygon, rect) plus hand-placed ASCII stamps for faces, then outlined
automatically. Everything is deterministic, so the PNGs and the JSON pixel data are reproducible.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

N = 32


def hex_rgba(h: str) -> tuple[int, int, int, int]:
    h = h.lstrip("#")
    if len(h) == 6:
        h += "ff"
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4, 6))  # type: ignore[return-value]


@dataclass
class Sprite:
    palette: dict[str, str]
    g: list[list[str | None]] = field(default_factory=lambda: [[None] * N for _ in range(N)])

    # ── access ──
    def get(self, x: int, y: int) -> str | None:
        return self.g[y][x] if 0 <= x < N and 0 <= y < N else None

    def set(self, x: int, y: int, k: str | None) -> None:
        if 0 <= x < N and 0 <= y < N:
            self.g[y][x] = k

    def copy(self) -> "Sprite":
        return Sprite(self.palette, [row[:] for row in self.g])

    # ── primitives (pixel centres at x+0.5, y+0.5) ──
    def ellipse(self, cx: float, cy: float, rx: float, ry: float, k: str, only: set[str | None] | None = None) -> None:
        for y in range(N):
            for x in range(N):
                if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1.0:
                    if only is None or self.get(x, y) in only:
                        self.set(x, y, k)

    def rect(self, x0: int, y0: int, x1: int, y1: int, k: str) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.set(x, y, k)

    def poly(self, pts: list[tuple[float, float]], k: str, only: set[str | None] | None = None) -> None:
        for y in range(N):
            for x in range(N):
                if _inside(x + 0.5, y + 0.5, pts) and (only is None or self.get(x, y) in only):
                    self.set(x, y, k)

    def stamp(self, x0: int, y0: int, rows: list[str], mirror: bool = False) -> None:
        """ASCII patch: '.' or ' ' = leave as is, '_' = make transparent, other chars = palette keys."""
        for dy, row in enumerate(rows):
            for dx, c in enumerate(row):
                if c in ". ":
                    continue
                x = (N - 1 - (x0 + dx)) if mirror else x0 + dx
                self.set(x, y0 + dy, None if c == "_" else c)

    def sym(self, x0: int, y0: int, rows: list[str]) -> None:
        """Stamp on the left half and mirror it onto the right half."""
        self.stamp(x0, y0, rows)
        self.stamp(x0, y0, rows, mirror=True)

    def outline(self, k: str = "o", skip: set[str] = frozenset()) -> None:
        """1px outline (4-neighbourhood) around every opaque pixel whose key is not in `skip`."""
        add = []
        for y in range(N):
            for x in range(N):
                if self.g[y][x] is None:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        v = self.get(x + dx, y + dy)
                        if v is not None and v not in skip and v != k:
                            add.append((x, y))
                            break
        for x, y in add:
            self.set(x, y, k)

    def replace(self, a: str, b: str, region: tuple[int, int, int, int] | None = None) -> None:
        x0, y0, x1, y1 = region or (0, 0, N - 1, N - 1)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if self.g[y][x] == a:
                    self.g[y][x] = b

    # ── output ──
    def image(self, scale: int = 1, bg: str | None = None) -> Image.Image:
        im = Image.new("RGBA", (N, N), hex_rgba(bg) if bg else (0, 0, 0, 0))
        px = im.load()
        for y in range(N):
            for x in range(N):
                k = self.g[y][x]
                if k is not None:
                    px[x, y] = hex_rgba(self.palette[k])
        return im.resize((N * scale, N * scale), Image.NEAREST) if scale != 1 else im

    def rows(self) -> list[str]:
        return ["".join(k or "." for k in row) for row in self.g]


def _inside(x: float, y: float, pts: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def save_sheet(frames: dict[str, Sprite], path: Path, scale: int = 1) -> None:
    """Horizontal strip of frames (for final sprite use) + a JSON with the raw pixel rows."""
    names = list(frames)
    im = Image.new("RGBA", (N * scale * len(names), N * scale), (0, 0, 0, 0))
    for i, n in enumerate(names):
        im.paste(frames[n].image(scale), (i * N * scale, 0))
    im.save(path)
    first = frames[names[0]]
    data = {"size": N, "palette": first.palette, "frames": {n: frames[n].rows() for n in names}}
    path.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
