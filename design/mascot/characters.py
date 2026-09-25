"""Jackson mascot concepts for SOS: «Чёрт» (a friendly imp) and «Кот» (a 2000s cat).

Each character = palette + base (head, body, accessories) + a face/prop layer per state.
States: idle, blink, listening, thinking, talk1, talk2, happy, error.
Coordinates: 32×32, pixel (x, y) from the top-left; the face is centred between x=15 and x=16.
"""
from __future__ import annotations

from pixel import N, Sprite

STATES = ["idle", "blink", "listening", "thinking", "talk1", "talk2", "happy", "error"]


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


def pts(s: Sprite, key: str, *xy: tuple[int, int]) -> None:
    for x, y in xy:
        s.set(x, y, key)


def think(s: Sprite) -> None:
    """Thought bubbles rising to the top-right corner: · o O (amber, lit from the top-left)."""
    s.set(26, 7, "a")
    pts(s, "a", (27, 4), (28, 4), (27, 5), (28, 5))
    s.set(27, 4, "y")
    pts(s, "a", (29, 1), (30, 1), (29, 2), (30, 2), (28, 2), (31, 2), (29, 3), (30, 3))
    s.set(29, 1, "y")


# ─────────────────────────────── «Чёрт» ───────────────────────────────
IMP = {
    "o": "#24160f",  # outline, warm near-black
    "r": "#d9553b",  # skin
    "R": "#a8402f",  # skin shade
    "q": "#f07d58",  # skin light
    "a": "#ffb547",  # amber — horns, LEDs, drawstrings (the Graphite signal)
    "A": "#cf7f18",  # amber shade
    "y": "#ffe3a8",  # amber highlight
    "h": "#3b404a",  # hoodie
    "H": "#292d34",  # hoodie shade
    "j": "#59606d",  # hoodie light / rim
    "d": "#1a1d22",  # headphone band
    "c": "#4b515d",  # cup
    "w": "#fff6e6",  # eye glint / fang
    "m": "#5e1711",  # mouth inside
    "t": "#ff8f73",  # tongue
    "k": "#f59a7e",  # blush
    "v": "#8fd0ea",  # sweat drop
}


def imp_base() -> Sprite:
    s = Sprite(IMP)
    # hoodie body + hood up
    s.poly([(1.5, 32), (3, 25), (7, 22.5), (25, 22.5), (29, 25), (30.5, 32)], "h")
    s.ellipse(16, 14.6, 11.2, 10.6, "h")                  # hood
    shade(s, "h", "H", "j", 16, 15, 7.5, -10.5, sx=0.6, lx=0.9)
    s.rect(15, 26, 16, 31, "H")                            # zip line
    # face opening
    s.ellipse(16, 15.4, 7.7, 7.3, "r")
    shade(s, "r", "R", "q", 16, 15.4, 5.6, -7.2)
    # horns through the hood
    horn = ["a....",
            "ay...",
            ".aa..",
            ".aaA.",
            "..aaA",
            "..aaA"]
    s.stamp(7, 1, horn)
    s.stamp(7, 1, horn, mirror=True)
    # headphones worn over the hood: thin band + cups with an amber LED
    for x in range(11, 21):
        s.set(x, 4 if 13 <= x <= 18 else 5, "d")
    pts(s, "d", (10, 6), (21, 6), (9, 7), (22, 7))
    cup = [".dd.",
           "dccd",
           "dcad",
           "dccd",
           ".dd."]
    s.stamp(3, 12, cup)
    s.stamp(3, 12, cup, mirror=True)
    pts(s, "d", (5, 9), (5, 10), (5, 11), (26, 9), (26, 10), (26, 11), (6, 8), (25, 8), (7, 7), (24, 7), (8, 7), (23, 7))
    # drawstrings with aglets
    s.stamp(12, 23, ["a", "a", "a", "A", "y"])
    s.stamp(12, 23, ["a", "a", "a", "A", "y"], mirror=True)
    s.outline("o")
    return s


def imp_face(base: Sprite, state: str) -> Sprite:
    s = base.copy()
    # ── eyes: big, dark and shiny (kind); brows do the "sly" part ──
    if state == "blink":
        pts(s, "o", (11, 15), (12, 15), (13, 15), (18, 15), (19, 15), (20, 15))
        pts(s, "R", (11, 14), (13, 14), (18, 14), (20, 14))
    elif state == "happy":
        pts(s, "o", (11, 15), (12, 14), (13, 15), (18, 15), (19, 14), (20, 15))
    elif state == "error":
        for ex in (11, 18):
            pts(s, "o", (ex, 13), (ex + 2, 13), (ex + 1, 14), (ex, 15), (ex + 2, 15))
    else:
        dx = 1 if state == "thinking" else 0
        dy = -1 if state == "thinking" else 0
        for ex in (11, 18):
            pts(s, "o", (ex + dx, 13 + dy), (ex + 1 + dx, 13 + dy), (ex + dx, 14 + dy), (ex + 1 + dx, 14 + dy), (ex + dx, 15 + dy), (ex + 1 + dx, 15 + dy))
            s.set(ex + dx, 13 + dy, "w")
        if state == "listening":  # wider, attentive
            for ex in (11, 18):
                pts(s, "o", (ex + 2, 13), (ex + 2, 14), (ex + 2, 15))
    # brows
    if state in ("idle", "blink", "talk1", "talk2"):
        pts(s, "o", (10, 11), (11, 11), (12, 11), (18, 11), (19, 10), (20, 10), (21, 11))   # right one raised: sly
    elif state == "listening":
        pts(s, "o", (10, 10), (11, 10), (12, 10), (19, 10), (20, 10), (21, 10))
    elif state == "thinking":
        pts(s, "o", (11, 10), (12, 10), (13, 11), (18, 11), (19, 11), (20, 10), (21, 10))
    elif state == "error":
        pts(s, "o", (10, 12), (11, 11), (12, 11), (19, 11), (20, 11), (21, 12))
    # ── mouth ──
    if state in ("idle", "blink"):
        pts(s, "o", (12, 18), (13, 19), (14, 19), (15, 19), (16, 19), (17, 19), (18, 18), (19, 17))
        s.set(17, 18, "w")                                   # the fang
    elif state == "listening":
        pts(s, "o", (13, 19), (14, 19), (15, 19), (16, 19), (17, 19), (18, 18))
    elif state == "thinking":
        pts(s, "o", (14, 19), (15, 19), (16, 19), (17, 18))
    elif state == "talk1":
        pts(s, "o", (12, 18), (13, 19), (17, 19), (18, 18), (14, 20), (15, 20), (16, 20))
        pts(s, "m", (14, 19), (15, 19), (16, 19))
        s.set(17, 18, "w")
    elif state == "talk2":
        pts(s, "o", (13, 18), (14, 18), (15, 18), (16, 18), (17, 18), (12, 19), (18, 19), (12, 20), (18, 20), (13, 21), (14, 21), (15, 21), (16, 21), (17, 21))
        pts(s, "m", (13, 19), (14, 19), (15, 19), (16, 19), (17, 19), (13, 20), (14, 20), (17, 20))
        pts(s, "t", (15, 20), (16, 20))
        s.set(16, 19, "w")
    elif state == "happy":
        pts(s, "o", (11, 17), (12, 18), (13, 19), (14, 20), (15, 20), (16, 20), (17, 20), (18, 19), (19, 18), (20, 17))
        pts(s, "m", (12, 17), (13, 18), (14, 19), (15, 19), (16, 19), (17, 19), (18, 18), (19, 17), (13, 17), (14, 18), (15, 18), (16, 18), (17, 18), (18, 17), (14, 17), (15, 17), (16, 17), (17, 17))
        pts(s, "t", (15, 19), (16, 19))
        pts(s, "w", (13, 17), (18, 17))
        pts(s, "k", (9, 16), (10, 16), (21, 16), (22, 16))
    elif state == "error":
        pts(s, "o", (12, 19), (13, 18), (14, 19), (15, 18), (16, 19), (17, 18), (18, 19), (19, 18))
    # ── props ──
    if state == "listening":   # cups light up, sound comes in
        for x in (5, 26):
            pts(s, "a", (x, 13), (x, 14), (x, 15))
            pts(s, "y", (x, 14))
        pts(s, "a", (1, 12), (0, 13), (0, 14), (0, 15), (1, 16), (30, 12), (31, 13), (31, 14), (31, 15), (30, 16))
    if state == "thinking":    # thought bubbles rising from the head: · o O
        think(s)
    if state == "happy":       # a small amber sparkle
        pts(s, "a", (28, 2), (28, 3), (28, 5), (28, 6), (26, 4), (27, 4), (29, 4), (30, 4))
        pts(s, "y", (28, 4))
    if state == "error":       # sweat drop + dimmed LEDs
        pts(s, "v", (24, 10), (23, 11), (24, 11), (23, 12), (24, 12))
        for x in (5, 26):
            s.set(x, 14, "c")
    return s


# ─────────────────────────────── «Кот» ───────────────────────────────
CAT = {
    "o": "#1b1d24",  # outline
    "f": "#8f9bb1",  # fur (russian blue)
    "F": "#6b768b",  # fur shade
    "u": "#b7c1d3",  # fur light
    "n": "#e8ebf1",  # muzzle / chest
    "p": "#e79c9c",  # nose / inner ear
    "s": "#14161b",  # shades
    "e": "#5d6b86",  # eyes seen through the tinted lenses
    "S": "#7ad3e6",  # shades glint (cloud)
    "Z": "#ffffff",  # hard glint
    "d": "#20232a",  # headphones band
    "c": "#4b515d",  # cup
    "a": "#ffb547",  # amber LED
    "y": "#ffe3a8",  # amber highlight
    "b": "#3140e0",  # jacket (the Paper signal, a touch deeper)
    "B": "#212a9e",  # jacket shade
    "l": "#5f6bf5",  # jacket light
    "m": "#4a1d24",  # mouth
    "t": "#f08c8c",  # tongue
    "k": "#f3a9a9",  # blush
    "v": "#8fd0ea",  # sweat drop
}


def cat_base() -> Sprite:
    s = Sprite(CAT)
    # track jacket with an open collar
    s.poly([(1.5, 32), (3.4, 25.6), (8, 23), (24, 23), (28.6, 25.6), (30.5, 32)], "b")
    shade(s, "b", "B", "l", 16, 27, 5.2, -9.5, sx=0.9, lx=0.9)
    s.poly([(12.5, 22.6), (16, 27.5), (19.5, 22.6)], "n")
    s.rect(15, 28, 16, 31, "B")
    # ears
    s.poly([(6.8, 13), (8.2, 3.2), (14.6, 9)], "f")
    s.poly([(25.2, 13), (23.8, 3.2), (17.4, 9)], "f")
    s.poly([(8.6, 10.6), (9.2, 5.6), (12.8, 9)], "p")
    s.poly([(23.4, 10.6), (22.8, 5.6), (19.2, 9)], "p")
    # head with fluffy cheeks
    s.ellipse(16, 15.6, 9.6, 7.4, "f")
    s.stamp(5, 17, ["ff", ".f"]); s.stamp(5, 17, ["ff", ".f"], mirror=True)
    shade(s, "f", "F", "u", 16, 15.6, 5.2, -7.3, sx=0.5, lx=0.6)
    pts(s, "F", (15, 9), (16, 9), (15, 10), (13, 10), (18, 10))          # tabby hint
    s.ellipse(16, 19.6, 3.3, 1.9, "n")                                   # muzzle
    # DJ headphones resting around the neck: band behind the neck, cups on the collarbones
    pts(s, "d", (10, 22), (11, 22), (20, 22), (21, 22))
    cup = [".ddd.",
           "dcccd",
           "dcacd",
           "dcccd",
           ".ddd."]
    s.stamp(5, 21, cup)
    s.stamp(5, 21, cup, mirror=True)
    s.outline("o")
    return s


def cat_face(base: Sprite, state: str) -> Sprite:
    s = base.copy()
    # ── tinted shades: his eyes show faintly through the lenses ──
    lens = ["ssssss",
            "ssssss",
            "ssssss",
            ".ssss."]
    s.stamp(9, 13, lens)
    s.stamp(9, 13, lens, mirror=True)
    pts(s, "s", (15, 13), (16, 13))                 # bridge
    tilt = state == "error"
    if tilt:                                         # knocked askew: right lens slides down a pixel
        s.stamp(17, 13, ["......"])
        for x in range(17, 23):
            s.set(x, 13, s.get(x, 12) if x > 21 else "f")
        s.stamp(17, 14, ["ssssss", "ssssss", "ssssss", ".ssss."])
        pts(s, "f", (15, 13), (16, 13)); pts(s, "s", (15, 14), (16, 14))
    L, R = 10, 19
    dy = 1 if tilt else 0
    for ex in (L, R):
        oy = dy if ex == R else 0
        if state == "blink":
            pts(s, "e", (ex, 15), (ex + 1, 15), (ex + 2, 15))
        elif state == "happy":
            pts(s, "e", (ex, 15), (ex + 1, 14), (ex + 2, 15))
        elif state == "error":
            pts(s, "e", (ex, 14 + oy), (ex + 2, 14 + oy), (ex + 1, 15 + oy), (ex, 16 + oy), (ex + 2, 16 + oy))
        elif state == "thinking":
            pts(s, "e", (ex + 1, 14), (ex + 2, 14), (ex + 1, 15), (ex + 2, 15))
        elif state == "listening":
            pts(s, "e", (ex, 14), (ex + 1, 14), (ex + 2, 14), (ex, 15), (ex + 1, 15), (ex + 2, 15))
            s.set(ex + 1, 15, "s")
        else:                                        # relaxed, half-closed
            pts(s, "e", (ex, 15), (ex + 1, 15), (ex + 2, 15), (ex + 1, 14))
    # glints on the lenses (top-left of each)
    pts(s, "Z", (10, 13), (19, 13 + dy))
    s.set(11, 13, "S"); s.set(20, 13 + dy, "S")
    # ── nose + mouth ──
    pts(s, "p", (15, 18), (16, 18))
    if state in ("idle", "blink", "listening"):     # little "ω" with a smirk on the right
        pts(s, "o", (15, 19), (16, 19), (14, 20), (17, 20), (18, 20), (19, 19))
    elif state == "thinking":
        pts(s, "o", (15, 19), (16, 19), (14, 20), (15, 20), (16, 20), (17, 20))
    elif state == "talk1":
        pts(s, "o", (15, 19), (16, 19), (14, 20), (17, 20), (15, 21), (16, 21))
        pts(s, "m", (15, 20), (16, 20))
    elif state == "talk2":
        pts(s, "o", (15, 19), (16, 19), (13, 20), (18, 20), (13, 21), (18, 21), (14, 22), (15, 22), (16, 22), (17, 22))
        pts(s, "m", (14, 20), (15, 20), (16, 20), (17, 20), (14, 21), (17, 21))
        pts(s, "t", (15, 21), (16, 21))
    elif state == "happy":
        pts(s, "o", (15, 19), (16, 19), (12, 19), (19, 19), (12, 20), (19, 20), (13, 21), (18, 21), (14, 22), (15, 22), (16, 22), (17, 22))
        pts(s, "m", (13, 20), (14, 20), (17, 20), (18, 20), (14, 21), (17, 21))
        pts(s, "t", (15, 20), (16, 20), (15, 21), (16, 21))
        pts(s, "k", (8, 18), (9, 18), (22, 18), (23, 18))
    elif state == "error":
        pts(s, "o", (13, 21), (14, 20), (15, 21), (16, 20), (17, 21), (18, 20))
    # whiskers
    pts(s, "u", (10, 19), (11, 19), (10, 21), (11, 20), (21, 19), (20, 19), (21, 21), (20, 20))
    # ── props ──
    if state == "listening":                         # cups light up, sound comes in
        for x in (7, 24):
            pts(s, "a", (x - 1, 23), (x, 22), (x, 23), (x, 24), (x + 1, 23))
            s.set(x, 23, "y")
        pts(s, "a", (1, 12), (0, 13), (0, 14), (0, 15), (1, 16), (30, 12), (31, 13), (31, 14), (31, 15), (30, 16))
    if state == "thinking":
        think(s)
    if state == "happy":
        pts(s, "a", (28, 2), (28, 3), (28, 5), (28, 6), (26, 4), (27, 4), (29, 4), (30, 4))
        s.set(28, 4, "y")
    if state == "error":
        pts(s, "v", (25, 10), (24, 11), (25, 11), (24, 12), (25, 12))
        for x in (7, 24):
            s.set(x, 23, "c")
    return s


def frames(kind: str) -> dict[str, Sprite]:
    base, face = (imp_base(), imp_face) if kind == "imp" else (cat_base(), cat_face)
    return {st: face(base, st) for st in STATES}
