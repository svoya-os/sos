"""Jackson mascot system for SOS: «Чёрт» (imp) and «Кот» (cat) — DESIGN.md §13.

Every colour is a palette SLOT, every option is a LAYER. A frame is composed at runtime as:

    derive options → draw the "silhouette" layers in order → 1px outline pass → draw the state layer
    (face + props) and the overlays (glasses, tinted eyes, lit headphones) → map keys to colours.

This module draws the layers (32×32 grids of single-character keys) and describes the recipe; build.py
exports it to shell/assets/jackson/<character>.json (format: FORMAT.md) and renders previews by running the
same recipe from the exported data (render.py), so the JSON is what we test.
"""
from __future__ import annotations

from pixel import N, Sprite

STATES = ["idle", "blink", "listening", "thinking", "talk1", "talk2", "happy", "error"]
ANIMATIONS = {                       # shell mood → frames (ms): idle blinks, talking alternates
    "idle": {"frames": ["idle", "blink"], "ms": [3600, 120], "jitter": [2400, 0]},
    "listening": {"frames": ["listening"], "ms": [0]},
    "thinking": {"frames": ["thinking"], "ms": [0]},
    "talking": {"frames": ["talk1", "talk2"], "ms": [140, 140]},
    "happy": {"frames": ["happy"], "ms": [0]},
    "error": {"frames": ["error"], "ms": [0]},
}

# key → slot name (shared by both characters; a character uses a subset)
SLOTS = {
    "o": "outline", "r": "skin", "R": "skinShade", "q": "skinLight",
    "h": "outfit", "H": "outfitShade", "j": "outfitLight", "N": "undershirt",
    "a": "detail", "A": "detailShade", "y": "detailLight", "L": "led",
    "d": "headphones", "c": "headphonesLight",
    "w": "white", "Y": "iris", "e": "eyesTinted", "m": "mouth", "t": "tongue", "k": "blush", "v": "sweat",
    "s": "lens", "S": "lensGlint", "Z": "lensHighlight", "g": "frame",
    "n": "muzzle", "p": "nose", "X": "stripe", "P": "points", "Q": "pointsLight", "u": "whisker",
}
TINT = {"keys": "owY", "to": "e"}    # under tinted lenses: eye pixels show as `e`, the rest as the lens


def blank() -> Sprite:
    return Sprite({})


def pts(s: Sprite, key: str, *xy: tuple[int, int]) -> None:
    for x, y in xy:
        s.set(x, y, key)


def shade(s: Sprite, key: str, dark: str, light: str, cx: float, cy: float, kd: float, kl: float,
          sx: float = 0.55, lx: float = 0.8) -> None:
    """Light from the top-left: darken the lower-right, lighten the upper-left of a region."""
    for y in range(N):
        for x in range(N):
            if s.get(x, y) == key:
                if (x - cx) * sx + (y - cy) > kd:
                    s.set(x, y, dark)
                elif (x - cx) * lx + (y - cy) < kl:
                    s.set(x, y, light)


def mirror_pts(s: Sprite, key: str, *xy: tuple[int, int]) -> None:
    for x, y in xy:
        s.set(x, y, key)
        s.set(N - 1 - x, y, key)


# ═════════════════════════════════════ «Чёрт» ═════════════════════════════════════
IMP_FIXED = {
    "outline": "#24160f", "white": "#fff6e6", "mouth": "#5e1711", "tongue": "#ff8f73", "blush": "#f59a7e",
    "sweat": "#8fd0ea", "headphones": "#1a1d22", "headphonesLight": "#4b515d", "undershirt": "#e9e5dc",
    "lens": "#16171b", "lensGlint": "#7ad3e6", "lensHighlight": "#ffffff", "frame": "#2b2e36",
    "eyesTinted": "#7b6a64",
}
IMP_SKINS = {   # id: (ru, slots)
    "ember": ("Огонь", {"skin": "#d9553b", "skinShade": "#a8402f", "skinLight": "#f07d58"}),
    "wine": ("Бордо", {"skin": "#a8384d", "skinShade": "#7e2538", "skinLight": "#c9556f"}),
    "plum": ("Слива", {"skin": "#8c55a3", "skinShade": "#693e7c", "skinLight": "#ab74c2"}),
    "graphite": ("Графит", {"skin": "#747b89", "skinShade": "#565c69", "skinLight": "#959dab"}),
    "mint": ("Мята", {"skin": "#5cbf98", "skinShade": "#3f9677", "skinLight": "#86d9b7"}),
}


def imp_layers() -> dict[str, Sprite]:
    L: dict[str, Sprite] = {}
    torso = [(1.5, 32), (3, 25), (7, 22.5), (25, 22.5), (29, 25), (30.5, 32)]

    # ── bodies ──
    s = blank()                                            # hoodie (pullover, drawstrings = detail)
    s.poly(torso, "h")
    shade(s, "h", "H", "j", 16, 15, 7.5, -10.5, sx=0.6, lx=0.9)
    pts(s, "H", *[(x, 28) for x in range(11, 21)])         # kangaroo pocket seam
    pts(s, "H", (10, 29), (21, 29))
    s.stamp(12, 23, ["a", "a", "a", "A", "y"]); s.stamp(12, 23, ["a", "a", "a", "A", "y"], mirror=True)
    L["body.hoodie"] = s

    s = blank()                                            # jacket: open zip, tee underneath
    s.poly(torso, "h")
    shade(s, "h", "H", "j", 16, 15, 7.5, -10.5, sx=0.6, lx=0.9)
    s.poly([(12, 22.4), (16, 29), (20, 22.4)], "N")
    s.poly([(10, 22.6), (12.8, 22.4), (15.4, 28.6), (13.4, 28.8)], "j")
    s.poly([(22, 22.6), (19.2, 22.4), (16.6, 28.6), (18.6, 28.8)], "j")
    pts(s, "H", (15, 29), (16, 29), (15, 30), (16, 30), (15, 31), (16, 31))
    pts(s, "a", (13, 27), (13, 28))                        # zip pull
    L["body.jacket"] = s

    s = blank()                                            # tee: round neck, detail-coloured collar trim
    s.poly([(2, 32), (3.4, 25.5), (8, 23), (24, 23), (28.6, 25.5), (30, 32)], "h")
    shade(s, "h", "H", "j", 16, 15, 7.5, -10.5, sx=0.6, lx=0.9)
    s.ellipse(16, 22.2, 4.6, 2.6, "r")
    pts(s, "a", (11, 23), (12, 24), (13, 25), (14, 25), (15, 25), (16, 25), (17, 25), (18, 25), (19, 24), (20, 23))
    pts(s, "H", (6, 29), (7, 30), (25, 29), (24, 30))      # sleeve seams
    L["body.tee"] = s

    # ── hood ──
    s = blank()
    s.ellipse(16, 14.6, 11.2, 10.6, "h")
    s.poly([(4.8, 23), (27.2, 23), (26, 26), (6, 26)], "h")
    shade(s, "h", "H", "j", 16, 15, 7.5, -10.5, sx=0.6, lx=0.9)
    L["hood.up"] = s

    s = blank()                                            # hood down: a soft roll behind the neck
    s.ellipse(16, 22.6, 10.2, 3.4, "H")
    pts(s, "j", *[(x, 20) for x in range(12, 20)])
    pts(s, "j", (9, 21), (10, 21), (11, 21), (20, 21), (21, 21), (22, 21))
    L["hood.down"] = s

    # ── heads ──
    s = blank()                                            # face in the hood opening
    s.ellipse(16, 15.4, 7.7, 7.3, "r")
    shade(s, "r", "R", "q", 16, 15.4, 5.6, -7.2)
    L["head.hooded"] = s

    s = blank()                                            # bare head with pointy ears
    s.ellipse(16, 14.6, 8.3, 7.6, "r")
    s.stamp(5, 12, ["r...", ".rr.", ".rrr", "..rr"]); s.stamp(5, 12, ["r...", ".rr.", ".rrr", "..rr"], mirror=True)
    shade(s, "r", "R", "q", 16, 14.6, 6.2, -8.2)
    s.ellipse(16, 22.2, 3.2, 1.6, "R", only={None})        # neck
    L["head.bare"] = s

    # ── headphones (LEDs are `L` = led slot, which follows the accent) ──
    cup = [".dd.", "dccd", "dLcd", "dccd", ".dd."]
    s = blank()                                            # over the hood
    for x in range(11, 21):
        s.set(x, 4 if 13 <= x <= 18 else 5, "d")
    pts(s, "d", (10, 6), (21, 6), (9, 7), (22, 7), (8, 7), (23, 7), (7, 7), (24, 7), (6, 8), (25, 8))
    pts(s, "d", (5, 9), (5, 10), (5, 11), (26, 9), (26, 10), (26, 11))
    s.stamp(3, 12, cup); s.stamp(3, 12, cup, mirror=True)
    L["headphones.hooded"] = s

    s = blank()                                            # on the bare head, band between the horns
    for x in range(12, 20):
        s.set(x, 5, "d"); s.set(x, 6, "c")
    pts(s, "d", (11, 6), (20, 6), (10, 7), (21, 7), (9, 8), (22, 8), (8, 9), (23, 9), (7, 10), (24, 10))
    pts(s, "c", (11, 7), (20, 7))
    s.stamp(4, 11, cup); s.stamp(4, 11, cup, mirror=True)
    L["headphones.bare"] = s

    # lit cups while listening (overlay, per head shape)
    s = blank()
    for x in (5, 26):
        pts(s, "a", (x, 13), (x, 14), (x, 15)); s.set(x, 14, "y")
    L["lit.hooded"] = s
    s = blank()
    for x in (6, 25):
        pts(s, "a", (x, 12), (x, 13), (x, 14)); s.set(x, 13, "y")
    L["lit.bare"] = s

    # ── horns (detail = accent), drawn over the headphone band ──
    horn_h = ["a....", "ay...", ".aa..", ".aaA.", "..aaA", "..aaA"]
    s = blank(); s.stamp(7, 1, horn_h); s.stamp(7, 1, horn_h, mirror=True)
    L["horns.hooded"] = s
    horn_b = ["a.....", "ay....", ".aA...", ".aaA..", "..aaA.", "..aaAA"]
    s = blank(); s.stamp(8, 2, horn_b); s.stamp(8, 2, horn_b, mirror=True)
    L["horns.bare"] = s

    # ── glasses (eyes: left x 11–12, right x 18–19, rows 13–15) ──
    s = blank()
    s.stamp(10, 13, ["ssss", "ssss", ".ss."]); s.stamp(17, 13, ["ssss", "ssss", ".ss."])
    pts(s, "s", (14, 13), (15, 13), (16, 13))
    L["glasses.shades"] = s
    s = blank(); pts(s, "Z", (10, 13), (17, 13)); pts(s, "S", (11, 13), (18, 13))
    L["glasses.shades.glint"] = s
    s = blank()
    ring = [".gg.", "g..g", "g..g", "g..g", ".gg."]
    s.stamp(10, 12, ring); s.stamp(17, 12, ring)
    pts(s, "g", (14, 13), (15, 13), (16, 13))
    L["glasses.round"] = s
    s = blank(); pts(s, "Z", (13, 13), (20, 13))
    L["glasses.round.glint"] = s
    return L


def imp_state(state: str) -> Sprite:
    s = blank()
    # eyes: big, dark and shiny (kind); brows do the "sly" part
    if state == "blink":
        pts(s, "o", (11, 15), (12, 15), (13, 15), (18, 15), (19, 15), (20, 15))
        pts(s, "R", (11, 14), (13, 14), (18, 14), (20, 14))
    elif state == "happy":
        pts(s, "o", (11, 15), (12, 14), (13, 15), (18, 15), (19, 14), (20, 15))
    elif state == "error":
        for ex in (11, 18):
            pts(s, "o", (ex, 13), (ex + 2, 13), (ex + 1, 14), (ex, 15), (ex + 2, 15))
    else:
        dx, dy = (1, -1) if state == "thinking" else (0, 0)
        for ex in (11, 18):
            for yy in (13, 14, 15):
                pts(s, "o", (ex + dx, yy + dy), (ex + 1 + dx, yy + dy))
            s.set(ex + dx, 13 + dy, "w")
            if state == "listening":
                pts(s, "o", (ex + 2, 13), (ex + 2, 14), (ex + 2, 15))
    # brows
    brows = {
        "idle": [(10, 11), (11, 11), (12, 11), (18, 11), (19, 10), (20, 10), (21, 11)],
        "listening": [(10, 10), (11, 10), (12, 10), (19, 10), (20, 10), (21, 10)],
        "thinking": [(11, 10), (12, 10), (13, 11), (18, 11), (19, 11), (20, 10), (21, 10)],
        "error": [(10, 12), (11, 11), (12, 11), (19, 11), (20, 11), (21, 12)],
    }
    b = brows.get("idle" if state in ("blink", "talk1", "talk2") else state)
    if b:
        pts(s, "o", *b)
    # mouth
    if state in ("idle", "blink"):
        pts(s, "o", (12, 18), (13, 19), (14, 19), (15, 19), (16, 19), (17, 19), (18, 18), (19, 17))
        s.set(17, 18, "w")                                                  # the fang
    elif state == "listening":
        pts(s, "o", (13, 19), (14, 19), (15, 19), (16, 19), (17, 19), (18, 18))
    elif state == "thinking":
        pts(s, "o", (14, 19), (15, 19), (16, 19), (17, 18))
    elif state == "talk1":
        pts(s, "o", (12, 18), (13, 19), (17, 19), (18, 18), (14, 20), (15, 20), (16, 20))
        pts(s, "m", (14, 19), (15, 19), (16, 19)); s.set(17, 18, "w")
    elif state == "talk2":
        pts(s, "o", (13, 18), (14, 18), (15, 18), (16, 18), (17, 18), (12, 19), (18, 19), (12, 20), (18, 20),
            (13, 21), (14, 21), (15, 21), (16, 21), (17, 21))
        pts(s, "m", (13, 19), (14, 19), (15, 19), (17, 19), (13, 20), (14, 20), (17, 20))
        pts(s, "t", (15, 20), (16, 20)); s.set(16, 19, "w")
    elif state == "happy":
        pts(s, "o", (11, 17), (12, 18), (13, 19), (14, 20), (15, 20), (16, 20), (17, 20), (18, 19), (19, 18), (20, 17))
        pts(s, "m", (12, 17), (13, 18), (14, 19), (15, 19), (16, 19), (17, 19), (18, 18), (19, 17), (14, 18), (15, 18),
            (16, 18), (17, 18), (14, 17), (15, 17), (16, 17), (17, 17))
        pts(s, "t", (15, 19), (16, 19)); pts(s, "w", (13, 17), (18, 17))
        pts(s, "k", (9, 16), (10, 16), (21, 16), (22, 16))
    elif state == "error":
        pts(s, "o", (12, 19), (13, 18), (14, 19), (15, 18), (16, 19), (17, 18), (18, 19), (19, 18))
    props(s, state, sweat=(24, 10))
    return s


# ═════════════════════════════════════ «Кот» ═════════════════════════════════════
CAT_FIXED = {
    "outline": "#1b1d24", "white": "#fff8ec", "mouth": "#4a1d24", "tongue": "#f08c8c", "blush": "#f3a9a9",
    "sweat": "#8fd0ea", "headphones": "#20232a", "headphonesLight": "#4b515d", "undershirt": "#e9e5dc",
    "lens": "#14161b", "lensGlint": "#7ad3e6", "lensHighlight": "#ffffff", "frame": "#2b2e36",
    "eyesTinted": "#5d6b86",
}
CAT_SKINS = {
    "blue": ("Русский голубой", {"skin": "#8f9bb1", "skinShade": "#6b768b", "skinLight": "#b7c1d3", "muzzle": "#e8ebf1",
                                 "nose": "#e79c9c", "stripe": "#7a8599", "whisker": "#b7c1d3", "iris": "#9fd25f"}),
    "ginger": ("Рыжий", {"skin": "#e08b3e", "skinShade": "#b8672a", "skinLight": "#f3ad66", "muzzle": "#fbeede",
                         "nose": "#e98a86", "stripe": "#c06a2b", "whisker": "#fbeede", "iris": "#8fcf54"}),
    "black": ("Чёрный", {"skin": "#434753", "skinShade": "#30333c", "skinLight": "#5f6572", "muzzle": "#565b69",
                         "nose": "#8a6168", "stripe": "#434753", "whisker": "#8a91a0", "iris": "#f2c94c"}),
    "snow": ("Снежный", {"skin": "#eef0f5", "skinShade": "#c9ced9", "skinLight": "#ffffff", "muzzle": "#ffffff",
                         "nose": "#f0a0a8", "stripe": "#eef0f5", "whisker": "#c9ced9", "iris": "#6fb6e8"}),
    "siamese": ("Сиамский", {"skin": "#efe3cc", "skinShade": "#d6c29f", "skinLight": "#fbf4e6", "muzzle": "#efe3cc",
                             "nose": "#4a3228", "stripe": "#efe3cc", "whisker": "#fbf4e6", "iris": "#5aa9f0",
                             "points": "#8a6450", "pointsLight": "#bea389"}, ["points"]),
}


def cat_layers() -> dict[str, Sprite]:
    L: dict[str, Sprite] = {}
    torso = [(1.5, 32), (3.4, 25.6), (8, 23), (24, 23), (28.6, 25.6), (30.5, 32)]

    s = blank()                                            # track jacket, open collar
    s.poly(torso, "h")
    shade(s, "h", "H", "j", 16, 27, 5.2, -9.5, sx=0.9, lx=0.9)
    s.poly([(12.5, 22.6), (16, 27.5), (19.5, 22.6)], "n")
    s.poly([(10.4, 22.8), (12.9, 22.6), (15.5, 27.6), (13.5, 27.8)], "j")
    s.poly([(21.6, 22.8), (19.1, 22.6), (16.5, 27.6), (18.5, 27.8)], "j")
    pts(s, "H", (15, 28), (16, 28), (15, 29), (16, 29), (15, 30), (16, 30), (15, 31), (16, 31))
    pts(s, "a", (17, 29), (17, 30))                        # zip pull
    L["body.jacket"] = s

    s = blank()                                            # hoodie, hood down, detail drawstrings
    s.poly(torso, "h")
    shade(s, "h", "H", "j", 16, 27, 5.2, -9.5, sx=0.9, lx=0.9)
    s.ellipse(16, 23.2, 8.6, 2.8, "H")
    pts(s, "j", *[(x, 21) for x in range(12, 20)])
    s.stamp(13, 24, ["a", "a", "A", "y"]); s.stamp(13, 24, ["a", "a", "A", "y"], mirror=True)
    pts(s, "H", *[(x, 29) for x in range(11, 21)])
    L["body.hoodie"] = s

    s = blank()                                            # tee: round neck shows the chest fur
    s.poly([(2, 32), (3.4, 26), (8, 23.4), (24, 23.4), (28.6, 26), (30, 32)], "h")
    shade(s, "h", "H", "j", 16, 27, 5.2, -9.5, sx=0.9, lx=0.9)
    s.ellipse(16, 22.8, 4.4, 2.4, "n")
    pts(s, "a", (11, 23), (12, 24), (13, 25), (14, 25), (15, 25), (16, 25), (17, 25), (18, 25), (19, 24), (20, 23))
    L["body.tee"] = s

    s = blank()                                            # head
    s.poly([(6.8, 13), (8.2, 3.2), (14.6, 9)], "r")
    s.poly([(25.2, 13), (23.8, 3.2), (17.4, 9)], "r")
    s.poly([(8.6, 10.6), (9.2, 5.6), (12.8, 9)], "p")
    s.poly([(23.4, 10.6), (22.8, 5.6), (19.2, 9)], "p")
    s.ellipse(16, 15.6, 9.6, 7.4, "r")
    s.stamp(5, 17, ["rr", ".r"]); s.stamp(5, 17, ["rr", ".r"], mirror=True)
    shade(s, "r", "R", "q", 16, 15.6, 5.2, -7.3, sx=0.5, lx=0.6)
    pts(s, "X", (15, 9), (16, 9), (15, 10), (16, 10), (13, 10), (18, 10), (12, 11), (19, 11))   # tabby marks
    pts(s, "X", (7, 15), (8, 15), (24, 15), (23, 15), (7, 17), (24, 17))
    s.ellipse(16, 19.6, 3.3, 1.9, "n")
    pts(s, "p", (15, 18), (16, 18))
    pts(s, "u", (10, 19), (11, 19), (10, 21), (11, 20), (21, 19), (20, 19), (21, 21), (20, 20))
    L["head"] = s

    s = blank()                                            # siamese points: soft mask + ear tips
    s.ellipse(16, 17.9, 5.4, 3.9, "Q")
    s.ellipse(16, 18.4, 3.9, 2.9, "P")
    pts(s, "P", (8, 4), (9, 5), (8, 5), (8, 6), (9, 6), (23, 4), (22, 5), (23, 5), (23, 6), (22, 6))
    pts(s, "Q", (9, 7), (10, 6), (22, 7), (21, 6))
    pts(s, "p", (15, 18), (16, 18))
    L["points"] = s

    s = blank()                                            # DJ headphones around the neck
    pts(s, "d", (10, 22), (11, 22), (20, 22), (21, 22))
    cup = [".ddd.", "dcccd", "dcLcd", "dcccd", ".ddd."]
    s.stamp(5, 21, cup); s.stamp(5, 21, cup, mirror=True)
    L["headphones.neck"] = s
    s = blank()
    for x in (7, 24):
        pts(s, "a", (x - 1, 23), (x, 22), (x, 23), (x, 24), (x + 1, 23)); s.set(x, 23, "y")
    L["lit.neck"] = s

    # glasses (eyes: left x 10–12, right x 19–21, rows 13–14)
    s = blank()
    lens = ["ssssss", "ssssss", "ssssss", ".ssss."]
    s.stamp(9, 13, lens); s.stamp(9, 13, lens, mirror=True)
    pts(s, "s", (15, 13), (16, 13))
    L["glasses.shades"] = s
    s = blank(); pts(s, "Z", (9, 13), (18, 13)); pts(s, "S", (10, 13), (19, 13))
    L["glasses.shades.glint"] = s
    s = blank()
    ring = [".ggg.", "g...g", "g...g", ".ggg."]
    s.stamp(9, 12, ring); s.stamp(18, 12, ring)
    pts(s, "g", (14, 13), (15, 13), (16, 13), (17, 13))
    L["glasses.round"] = s
    s = blank(); pts(s, "Z", (12, 13), (21, 13))
    L["glasses.round.glint"] = s
    return L


def cat_state(state: str) -> Sprite:
    s = blank()
    for ex in (10, 19):                                    # cat eyes: iris + slit pupil
        if state == "blink":
            pts(s, "o", (ex, 14), (ex + 1, 14), (ex + 2, 14))
        elif state == "happy":
            pts(s, "o", (ex, 14), (ex + 1, 13), (ex + 2, 14))
        elif state == "error":
            pts(s, "o", (ex, 12), (ex + 2, 12), (ex + 1, 13), (ex, 14), (ex + 2, 14))
        elif state == "thinking":                          # looking up and to the right
            pts(s, "o", (ex, 12), (ex + 1, 12), (ex + 2, 12))
            pts(s, "Y", (ex, 13), (ex + 1, 13), (ex, 14), (ex + 1, 14), (ex + 2, 14))
            s.set(ex + 2, 13, "o")
        elif state == "listening":                         # wide awake
            pts(s, "Y", (ex, 13), (ex + 2, 13), (ex, 14), (ex + 2, 14))
            pts(s, "o", (ex + 1, 13), (ex + 1, 14), (ex, 12), (ex + 1, 12), (ex + 2, 12))
            s.set(ex, 13, "w")
        else:                                              # relaxed, half-lidded: cool
            pts(s, "o", (ex, 13), (ex + 1, 13), (ex + 2, 13))
            pts(s, "Y", (ex, 14), (ex + 2, 14)); s.set(ex + 1, 14, "o")
    # nose + mouth
    if state in ("idle", "blink", "listening"):            # little "ω" with a smirk on the right
        pts(s, "o", (15, 19), (16, 19), (14, 20), (17, 20), (18, 20), (19, 19))
    elif state == "thinking":
        pts(s, "o", (15, 19), (16, 19), (14, 20), (15, 20), (16, 20), (17, 20))
    elif state == "talk1":
        pts(s, "o", (15, 19), (16, 19), (14, 20), (17, 20), (15, 21), (16, 21)); pts(s, "m", (15, 20), (16, 20))
    elif state == "talk2":
        pts(s, "o", (15, 19), (16, 19), (13, 20), (18, 20), (13, 21), (18, 21), (14, 22), (15, 22), (16, 22), (17, 22))
        pts(s, "m", (14, 20), (15, 20), (16, 20), (17, 20), (14, 21), (17, 21)); pts(s, "t", (15, 21), (16, 21))
    elif state == "happy":
        pts(s, "o", (15, 19), (16, 19), (12, 19), (19, 19), (12, 20), (19, 20), (13, 21), (18, 21), (14, 22), (15, 22),
            (16, 22), (17, 22))
        pts(s, "m", (13, 20), (14, 20), (17, 20), (18, 20), (14, 21), (17, 21)); pts(s, "t", (15, 20), (16, 20), (15, 21), (16, 21))
        pts(s, "k", (8, 18), (9, 18), (22, 18), (23, 18))
    elif state == "error":
        pts(s, "o", (13, 21), (14, 20), (15, 21), (16, 20), (17, 21), (18, 20))
    props(s, state, sweat=(25, 10))
    return s


def props(s: Sprite, state: str, sweat: tuple[int, int]) -> None:
    """State props outside the face; drawn after the outline pass (no outline)."""
    if state == "listening":                               # sound coming in
        pts(s, "a", (1, 12), (0, 13), (0, 14), (0, 15), (1, 16), (30, 12), (31, 13), (31, 14), (31, 15), (30, 16))
    if state == "thinking":                                # thought bubbles rising · o O
        s.set(26, 7, "a")
        pts(s, "a", (27, 4), (28, 4), (27, 5), (28, 5)); s.set(27, 4, "y")
        pts(s, "a", (29, 1), (30, 1), (28, 2), (29, 2), (30, 2), (31, 2), (29, 3), (30, 3)); s.set(29, 1, "y")
    if state == "happy":                                   # a small sparkle
        pts(s, "a", (28, 2), (28, 3), (28, 5), (28, 6), (26, 4), (27, 4), (29, 4), (30, 4)); s.set(28, 4, "y")
    if state == "error":                                   # a sweat drop
        x, y = sweat
        pts(s, "v", (x, y), (x - 1, y + 1), (x, y + 1), (x - 1, y + 2), (x, y + 2))


# ═════════════════════════════════════ recipes ═════════════════════════════════════
CHARACTERS = {
    "imp": {
        "name": {"ru": "Чёрт", "en": "Imp"},
        "fixed": IMP_FIXED, "skins": IMP_SKINS, "layers": imp_layers, "state": imp_state,
        "options": {"skin": list(IMP_SKINS), "style": ["hoodie", "jacket", "tee"], "hood": [True, False],
                    "headphones": [True, False], "glasses": ["none", "shades", "round"]},
        "defaults": {"skin": "ember", "outfit": "accent", "style": "hoodie", "hood": True, "headphones": True,
                     "glasses": "none"},
        # derived options: first matching rule wins
        "derive": {"head": [{"when": {"style": "hoodie", "hood": True}, "value": "hooded"}, {"value": "bare"}],
                   "hoodLayer": [{"when": {"style": "hoodie", "hood": True}, "value": "up"},
                                 {"when": {"style": "hoodie"}, "value": "down"}, {"value": ""}]},
        "compose": [
            {"layer": "body.{style}"},
            {"layer": "hood.{hoodLayer}"},
            {"layer": "head.{head}"},
            {"layer": "headphones.{head}", "when": {"headphones": True}},
            {"layer": "horns.{head}"},
            {"outline": "o"},
            {"state": True},
            {"layer": "lit.{head}", "when": {"headphones": True, "state": "listening"}},
            {"tint": "glasses.shades", "when": {"glasses": "shades"}},
            {"layer": "glasses.round", "when": {"glasses": "round"}},
            {"layer": "glasses.{glasses}.glint"},
        ],
    },
    "cat": {
        "name": {"ru": "Кот", "en": "Cat"},
        "fixed": CAT_FIXED, "skins": CAT_SKINS, "layers": cat_layers, "state": cat_state,
        "options": {"skin": list(CAT_SKINS), "style": ["jacket", "hoodie", "tee"], "headphones": [True, False],
                    "glasses": ["shades", "none", "round"]},
        "defaults": {"skin": "blue", "outfit": "accent", "style": "jacket", "headphones": True, "glasses": "shades"},
        "derive": {},
        "compose": [
            {"layer": "body.{style}"},
            {"layer": "head"},
            {"layer": "points", "skinFlag": "points"},
            {"layer": "headphones.neck", "when": {"headphones": True}},
            {"outline": "o"},
            {"state": True},
            {"layer": "lit.neck", "when": {"headphones": True, "state": "listening"}},
            {"tint": "glasses.shades", "when": {"glasses": "shades"}},
            {"layer": "glasses.round", "when": {"glasses": "round"}},
            {"layer": "glasses.{glasses}.glint"},
        ],
    },
}
STATE_SLOTS = {"error": {"led": "headphonesLight"}}       # per-state slot aliases (dim LEDs on error)
