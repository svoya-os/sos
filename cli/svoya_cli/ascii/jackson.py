"""Jackson in symbols: his own sprite (``shell/assets/jackson/<character>.json``, the look from
avatar.json: the imp or the cat, hoodie, horns, headphones), composed exactly as the shell does it
(design/mascot/FORMAT.md) and drawn with characters instead of pixels.

Every cell looks at four points of the sprite (smoothed a little, so pixel stairs become slopes):
covered all over, it gets a character as dense as that part is bright; covered in part, a
character along the edge ( _ / \\ | ' , ); the eyes, mouth and LEDs are pink, the alive part.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .engine import ACCENT, FG

FINE = " .,:;-~=+*xoO#%@"

# slot -> (brightness 0..1, color slot); slots that are not listed are mid phosphor
ROLE = {
    "outline": (0.50, FG), "skin": (0.62, FG), "skinLight": (0.78, FG), "skinShade": (0.46, FG),
    "outfit": (0.30, FG), "outfitLight": (0.42, FG), "outfitShade": (0.20, FG), "undershirt": (0.55, FG),
    "detail": (0.86, FG), "detailLight": (0.96, FG), "detailShade": (0.70, FG),
    "headphones": (0.28, FG), "headphonesLight": (0.42, FG), "led": (0.90, ACCENT),
    "white": (0.95, FG), "mouth": (0.55, ACCENT), "tongue": (0.70, ACCENT), "blush": (0.45, ACCENT),
    "eyesTinted": (0.85, ACCENT), "frame": (0.40, FG), "lens": (0.12, FG), "lensGlint": (0.95, FG),
    "lensHighlight": (0.80, FG), "sweat": (0.80, FG),
}
EDGE = {  # quadrants TL TR BL BR -> character along the edge
    (1, 1, 0, 0): '"', (0, 0, 1, 1): "_", (1, 0, 1, 0): "|", (0, 1, 0, 1): "|", (1, 0, 0, 1): "\\",
    (0, 1, 1, 0): "/", (0, 1, 1, 1): "/", (1, 0, 1, 1): "\\", (1, 1, 0, 1): "\\", (1, 1, 1, 0): "/",
    (1, 0, 0, 0): "'", (0, 1, 0, 0): "'", (0, 0, 1, 0): ",", (0, 0, 0, 1): ".",
}


def shell_dir(env: dict | None = None) -> Path:
    env = env if env is not None else os.environ
    for p in (env.get("SVOYA_SHELL_DIR"), "/usr/share/svoya/shell", Path(__file__).resolve().parents[3] / "shell"):
        if p and (Path(p) / "assets" / "jackson").is_dir():
            return Path(p)
    return Path("/usr/share/svoya/shell")


def load(character: str = "imp", env: dict | None = None) -> dict | None:
    try:
        return json.loads((shell_dir(env) / "assets" / "jackson" / f"{character}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def compose(data: dict, opts: dict, state: str) -> list[list[str | None]]:
    """The 32×32 grid of keys for a look and a state: the shell's Sprite.js, design/mascot/render.py."""
    n = data["size"]
    o = {**data["defaults"], **{k: v for k, v in opts.items() if k in data["defaults"]}, "state": state}
    for key, rules in data.get("derive", {}).items():
        for rule in rules:
            if all(o.get(k) == v for k, v in rule.get("when", {}).items()):
                o[key] = rule["value"]
                break
    skin = data["skins"].get(o.get("skin"), next(iter(data["skins"].values())))
    grid: list[list[str | None]] = [[None] * n for _ in range(n)]

    def match(when: dict) -> bool:
        return all((o.get(k) in v) if isinstance(v, list) else o.get(k) == v for k, v in when.items())

    def draw(rows: list[str]) -> None:
        for y, row in enumerate(rows):
            for x, c in enumerate(row):
                if c != ".":
                    grid[y][x] = c

    for step in data["compose"]:
        if "when" in step and not match(step["when"]):
            continue
        if "skinFlag" in step and step["skinFlag"] not in skin.get("flags", []):
            continue
        if "outline" in step:
            add = [(x, y) for y in range(n) for x in range(n) if grid[y][x] is None and any(
                0 <= x + dx < n and 0 <= y + dy < n and grid[y + dy][x + dx] is not None
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
            for x, y in add:
                grid[y][x] = step["outline"]
        elif "state" in step:
            draw(data["states"].get(state) or data["states"]["idle"])
        elif "tint" in step:
            layer = data["layers"].get(step["tint"].format(**o))
            if layer:
                keys, to = data["tint"]["keys"], data["tint"]["to"]
                for y, row in enumerate(layer):
                    for x, c in enumerate(row):
                        if c != ".":
                            grid[y][x] = to if grid[y][x] in keys else c
        else:
            name = step["layer"].format(**o)
            if name in data["layers"]:
                draw(data["layers"][name])
    return grid


def maps(data: dict, grid: list[list[str | None]]) -> tuple[list[list[float]], list[list[float]], list[list[int]]]:
    """Coverage, brightness and color slot per sprite pixel. An outline pixel inside the shape (not
    next to empty space) is a feature (eyes, mouth): pink."""
    n = len(grid)
    cov = [[0.0] * n for _ in range(n)]
    lum = [[0.0] * n for _ in range(n)]
    slot = [[FG] * n for _ in range(n)]
    for y in range(n):
        for x in range(n):
            k = grid[y][x]
            if k is None:
                continue
            name = data["slots"].get(k, "")
            v, s = ROLE.get(name, (0.5, FG))
            if name == "outline" and all(0 <= x + dx < n and 0 <= y + dy < n and grid[y + dy][x + dx] is not None
                                         for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                v, s = 0.85, ACCENT
            cov[y][x], lum[y][x], slot[y][x] = 1.0, v, s
    return cov, lum, slot


def blur(m: list[list[float]]) -> list[list[float]]:
    n = len(m)
    k = (0.25, 0.5, 0.25)

    def at(a, y, x):
        return a[min(n - 1, max(0, y))][min(n - 1, max(0, x))]
    h = [[sum(k[d + 1] * at(m, y, x + d) for d in (-1, 0, 1)) for x in range(n)] for y in range(n)]
    return [[sum(k[d + 1] * at(h, y + d, x) for d in (-1, 0, 1)) for x in range(n)] for y in range(n)]


def cells(data: dict, opts: dict, state: str, cols: int) -> list[tuple[int, int, str, int]]:
    """Jackson ``cols`` characters wide (and cols/2 rows tall): [(x, y, character, slot)]."""
    grid = compose(data, opts, state)
    n = len(grid)
    cov, lum, slot = maps(data, grid)
    smooth = blur(cov) if cols > n * 0.75 else cov
    rows = max(1, cols // 2)
    sx, sy = n / cols, n / rows

    def sample(m, fx, fy):
        x, y = min(n - 1.001, max(0.0, fx - 0.5)), min(n - 1.001, max(0.0, fy - 0.5))
        x0, y0 = int(x), int(y)
        ax, ay = x - x0, y - y0
        return (m[y0][x0] * (1 - ax) * (1 - ay) + m[y0][x0 + 1] * ax * (1 - ay) +
                m[y0 + 1][x0] * (1 - ax) * ay + m[y0 + 1][x0 + 1] * ax * ay)

    out = []
    for r in range(rows):
        for c in range(cols):
            x0, y0 = c * sx, r * sy
            q = tuple(1 if sample(smooth, x0 + fx * sx, y0 + fy * sy) > 0.5 else 0
                      for fx, fy in ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)))
            if not any(q):
                continue
            px, py = min(n - 1, int(x0 + sx / 2)), min(n - 1, int(y0 + sy / 2))
            if all(q):
                v = lum[py][px] if cov[py][px] else 0.5
                ch = FINE[max(1, int(v * 15.999))]
            else:
                ch = EDGE.get(q, ".")
            out.append((c, r, ch, slot[py][px] if cov[py][px] else FG))
    return out
