"""Reference runtime for the Jackson sprite format (FORMAT.md), in Python.

Renders any character × options × state × theme mode × accent straight from the exported JSON data — the
same algorithm the shell implements in QML (see jackson.js for the JavaScript twin).
"""
from __future__ import annotations

from PIL import Image

from color import detail as detail_of, outfit as outfit_of


def derive(data: dict, opts: dict) -> dict:
    o = dict(opts)
    for key, rules in data.get("derive", {}).items():
        for rule in rules:
            if all(o.get(k) == v for k, v in rule.get("when", {}).items()):
                o[key] = rule["value"]
                break
    return o


def _match(when: dict, o: dict) -> bool:
    for k, v in when.items():
        if isinstance(v, list):
            if o.get(k) not in v:
                return False
        elif o.get(k) != v:
            return False
    return True


def compose(data: dict, opts: dict, state: str) -> list[list[str | None]]:
    n = data["size"]
    o = derive(data, {**data["defaults"], **opts, "state": state})
    skin = data["skins"][o["skin"]]
    grid: list[list[str | None]] = [[None] * n for _ in range(n)]

    def draw(rows: list[str]) -> None:
        for y, row in enumerate(rows):
            for x, c in enumerate(row):
                if c != ".":
                    grid[y][x] = c

    for step in data["compose"]:
        if "when" in step and not _match(step["when"], o):
            continue
        if "skinFlag" in step and step["skinFlag"] not in skin.get("flags", []):
            continue
        if "outline" in step:
            k = step["outline"]
            add = [(x, y) for y in range(n) for x in range(n) if grid[y][x] is None and any(
                0 <= x + dx < n and 0 <= y + dy < n and grid[y + dy][x + dx] is not None
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
            for x, y in add:
                grid[y][x] = k
        elif "state" in step:
            draw(data["states"][state])
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


def colors(data: dict, opts: dict, state: str, mode: str, accent: str, outfit_color: str | None = None) -> dict[str, str]:
    """Slot → hex. `accent` is the system accent hex for this mode; outfit_color pins another outfit colour."""
    o = {**data["defaults"], **opts}
    c = dict(data["fixed"])
    c.update(data["skins"][o["skin"]]["colors"])
    c.update(detail_of(accent))
    c.update(outfit_of(outfit_color or accent, mode))
    for slot, alias in data.get("aliases", {}).items():
        c.setdefault(slot, c[alias])
    for slot, alias in data.get("stateSlots", {}).get(state, {}).items():
        c[slot] = c[alias]
    return c


def image(data: dict, opts: dict, state: str, mode: str, accent: str, scale: int = 1, bg: str | None = None,
          outfit_color: str | None = None) -> Image.Image:
    g = compose(data, opts, state)
    pal = colors(data, opts, state, mode, accent, outfit_color)
    n = data["size"]
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0) if not bg else tuple(int(bg[i:i + 2], 16) for i in (1, 3, 5)) + (255,))
    px = im.load()
    for y in range(n):
        for x in range(n):
            k = g[y][x]
            if k is not None:
                h = pal[data["slots"][k]]
                px[x, y] = tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
    return im.resize((n * scale, n * scale), Image.NEAREST) if scale != 1 else im
