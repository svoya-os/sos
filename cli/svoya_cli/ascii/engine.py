"""The engine: a character canvas, the brightness ramp, a renderer that writes only what changed,
and a loop that runs an effect in the terminal at 30 frames a second.

An effect is a pure function of time (``draw(canvas, t)``): the same ``t`` and seed always give
the same frame, which is what the golden-frame tests and the demo recorder rely on.
"""
from __future__ import annotations

import os
import select
import sys
import time

BG, FG, ACCENT, NOISE = 0, 1, 2, 3          # color slots; BG means "empty cell"
PALETTE = {"bg": "#0a0a0a", "fg": "#3cffd0", "accent": "#ff2e88", "noise": "#5a5a5a"}
RAMP = " .:-=+*#%@"
BLOCKS = " ░▒▓█"
GLYPHS = "01<>/\\{}[]#$%&*+=?~^"            # what a glitch and Jackson's thinking are made of
ASPECT = 2.0                                 # a cell is about twice as tall as wide
SLOT_LETTER = " fan"                         # colors in golden files: f(g) a(ccent) n(oise)


# ---- small math ------------------------------------------------------------------------------------
def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def ease(t: float) -> float:
    """Ease-in-out (smoothstep) on 0..1."""
    t = clamp(t)
    return t * t * (3.0 - 2.0 * t)


def ease_in(t: float) -> float:
    t = clamp(t)
    return t * t * t


def ease_out(t: float) -> float:
    t = 1.0 - clamp(t)
    return 1.0 - t * t * t


def hash3(i: int, j: int, k: int = 0) -> int:
    """A fast deterministic 32-bit hash: the same cell and frame always get the same noise."""
    h = (i * 374761393 + j * 668265263 + k * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return h ^ (h >> 16)


def rnd(i: int, j: int, k: int = 0) -> float:
    return (hash3(i, j, k) & 0xFFFF) / 65536.0


def ramp(v: float) -> str:
    return RAMP[int(clamp(v) * 9.999)]


# ---- canvas ----------------------------------------------------------------------------------------
class Canvas:
    """A w×h grid of characters and color slots, row by row in two flat lists."""

    __slots__ = ("w", "h", "ch", "co")

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.ch = [" "] * (w * h)
        self.co = [BG] * (w * h)

    def fill(self, ch: list[str] | None = None, co: list[int] | None = None) -> None:
        n = self.w * self.h
        self.ch[:] = ch if ch is not None else [" "] * n
        self.co[:] = co if co is not None else [BG] * n

    def put(self, x: int, y: int, c: str, slot: int = FG) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            i = y * self.w + x
            self.ch[i] = c
            self.co[i] = slot if c != " " else BG

    def text(self, x: int, y: int, s: str, slot: int = FG) -> None:
        for k, c in enumerate(s):
            self.put(x + k, y, c, slot)

    def copy(self) -> "Canvas":
        c = Canvas(self.w, self.h)
        c.ch[:] = self.ch
        c.co[:] = self.co
        return c

    def lines(self) -> list[str]:
        w = self.w
        return ["".join(self.ch[r * w:(r + 1) * w]) for r in range(self.h)]

    def color_lines(self) -> list[str]:
        w = self.w
        return ["".join(SLOT_LETTER[c] for c in self.co[r * w:(r + 1) * w]) for r in range(self.h)]


# ---- colors and the renderer -----------------------------------------------------------------------
def _rgb(hexcolor: str) -> tuple[int, int, int]:
    h = hexcolor.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _xterm256(rgb: tuple[int, int, int]) -> int:
    levels = (0, 95, 135, 175, 215, 255)

    def near(v: int) -> int:
        return min(range(6), key=lambda k: abs(levels[k] - v))

    cube = 16 + 36 * near(rgb[0]) + 6 * near(rgb[1]) + near(rgb[2])
    cube_rgb = tuple(levels[near(v)] for v in rgb)
    gray = max(0, min(23, round((sum(rgb) / 3 - 8) / 10)))
    gray_rgb = (8 + 10 * gray,) * 3

    def dist(a: tuple[int, ...]) -> int:
        return sum((x - y) ** 2 for x, y in zip(a, rgb))

    return cube if dist(cube_rgb) <= dist(gray_rgb) else 232 + gray


def color_mode(env: dict | os._Environ) -> str:
    """truecolor, 256, 16 or none (NO_COLOR)."""
    if env.get("NO_COLOR"):
        return "none"
    ct = (env.get("COLORTERM") or "").lower()
    term = (env.get("TERM") or "").lower()
    if ct in ("truecolor", "24bit") or "direct" in term or term.startswith(("xterm-kitty", "alacritty", "foot")):
        return "truecolor"
    if "256" in term:
        return "256"
    return "16"


class Ansi:
    """Turns canvases into escape sequences. After the first frame only changed cells are sent:
    a still eye costs a few bytes a frame, which keeps it smooth over SSH."""

    def __init__(self, palette: dict[str, str] | None = None, mode: str = "truecolor"):
        pal = {**PALETTE, **(palette or {})}
        self.mode = mode
        if mode == "none":
            self.sgr = ["\x1b[0m"] * 4
        elif mode == "16":
            fg = {FG: 96, ACCENT: 95, NOISE: 90, BG: 90}
            self.sgr = [f"\x1b[0;{fg[s]};40m" for s in range(4)]
        else:
            def spec(hexcolor: str, ground: int) -> str:
                rgb = _rgb(hexcolor)
                return f"{ground};2;{rgb[0]};{rgb[1]};{rgb[2]}" if mode == "truecolor" \
                    else f"{ground};5;{_xterm256(rgb)}"
            bg = spec(pal["bg"], 48)
            names = {BG: "noise", FG: "fg", ACCENT: "accent", NOISE: "noise"}
            self.sgr = [f"\x1b[0;{spec(pal[names[s]], 38)};{bg}m" for s in range(4)]

    def clear(self) -> str:
        return self.sgr[BG] + "\x1b[2J"

    def frame(self, cur: Canvas, prev: Canvas | None = None) -> str:
        w, h = cur.w, cur.h
        full = prev is None or prev.w != w or prev.h != h
        out: list[str] = []
        pen = -1
        sgr = self.sgr
        cch, cco = cur.ch, cur.co
        pch, pco = (None, None) if full else (prev.ch, prev.co)
        for r in range(h):
            a, b = r * w, (r + 1) * w
            if not full and cch[a:b] == pch[a:b] and cco[a:b] == pco[a:b]:
                continue
            at = -2                                       # where the cursor is in this row
            for i in range(a, b):
                c, s = cch[i], cco[i]
                if not full and c == pch[i] and s == pco[i]:
                    continue
                x = i - a
                if at != x:
                    out.append(f"\x1b[{r + 1};{x + 1}H")
                if s != pen and (c != " " or pen < 0):
                    out.append(sgr[s])
                    pen = s
                out.append(c)
                at = x + 1
        return "".join(out)


# ---- effects ---------------------------------------------------------------------------------------
class Effect:
    """A thing that draws itself at time t. Subclasses set ``duration`` (seconds, or None for
    endless), ``wants_mouse`` and override ``resize``/``draw``; ``key`` returns False to quit."""

    duration: float | None = None
    wants_mouse = False
    still_at = 2.0                     # the moment a still frame (--quiet, a pipe) shows

    def resize(self, w: int, h: int) -> None:
        self.w, self.h = w, h

    def draw(self, cv: Canvas, t: float) -> None:
        raise NotImplementedError

    def key(self, k: str, t: float) -> bool:
        return k not in ("q", "Q", "esc", "й", "Й")

    def pointer(self, x: int, y: int, t: float) -> None:
        pass


def render(effect: Effect, w: int, h: int, t: float) -> Canvas:
    effect.resize(w, h)
    cv = Canvas(w, h)
    effect.draw(cv, t)
    return cv


def still(effect: Effect, w: int, h: int, color: bool = True, palette: dict | None = None,
          env: dict | None = None) -> str:
    """One frame as text: colored when the output is a color terminal, plain otherwise."""
    cv = render(effect, w, h, effect.still_at)
    mode = color_mode(env if env is not None else os.environ) if color else "none"
    if mode == "none":
        return "\n".join(line.rstrip() for line in cv.lines()) + "\n"
    ansi = Ansi(palette, mode)
    rows = []
    for r in range(h):
        pen, parts = -1, []
        for i in range(r * w, (r + 1) * w):
            if cv.co[i] != pen:
                pen = cv.co[i]
                parts.append(ansi.sgr[pen])
            parts.append(cv.ch[i])
        rows.append("".join(parts) + "\x1b[0m")
    return "\n".join(rows) + "\n"


# ---- input -----------------------------------------------------------------------------------------
_KEYS = {"\x1b[A": "up", "\x1b[B": "down", "\x1b[C": "right", "\x1b[D": "left", "\x1bOA": "up",
         "\x1bOB": "down", "\x1bOC": "right", "\x1bOD": "left", "\r": "enter", "\n": "enter", " ": "space"}


def parse_input(data: str) -> list[tuple]:
    """Keys and SGR mouse reports (ESC [ < b ; x ; y M) → [("key", name) | ("mouse", x, y)],
    x and y counted from 0."""
    events: list[tuple] = []
    i, n = 0, len(data)
    while i < n:
        if data.startswith("\x1b[<", i):
            end = i + 3
            while end < n and data[end] not in "Mm":
                end += 1
            parts = data[i + 3:end].split(";")
            if end < n and len(parts) == 3 and all(p.isdigit() for p in parts):
                b, x, y = (int(p) for p in parts)
                if data[end] == "M" and not b & 64:        # moves and presses, not the wheel
                    events.append(("mouse", x - 1, y - 1))
            i = end + 1
            continue
        for seq, name in _KEYS.items():
            if data.startswith(seq, i):
                events.append(("key", name))
                i += len(seq)
                break
        else:
            if data[i] == "\x1b":
                j = i + 1
                if j < n and data[j] in "[O":               # an unknown sequence: skip it
                    j += 1
                    while j < n and not ("@" <= data[j] <= "~"):
                        j += 1
                    i = j + 1
                    continue
                events.append(("key", "esc"))
            else:
                events.append(("key", data[i]))
            i += 1
    return events


# ---- the loop --------------------------------------------------------------------------------------
def run(effect: Effect, *, fps: int = 30, speed: float = 1.0, seconds: float | None = None,
        any_key_quits: bool = False, palette: dict | None = None, env: dict | None = None,
        out=None, inp=None) -> int:
    """Runs an effect full screen until q/Esc (or any key with ``any_key_quits``), its duration
    or ``seconds`` is over. Restores the terminal whatever happens."""
    import termios
    import tty

    env = env if env is not None else os.environ
    out = out or sys.stdout
    inp = inp or sys.stdin
    ofd, ifd = out.fileno(), inp.fileno()
    ansi = Ansi(palette, color_mode(env))
    saved = termios.tcgetattr(ifd)
    mouse_on = "\x1b[?1003h\x1b[?1006h" if effect.wants_mouse else ""
    mouse_off = "\x1b[?1003l\x1b[?1006l" if effect.wants_mouse else ""
    write = out.buffer.write if hasattr(out, "buffer") else (lambda b: out.write(b.decode()))
    frame_dt = 1.0 / max(1, min(60, fps))
    prev: Canvas | None = None
    cv: Canvas | None = None
    size = (0, 0)
    start = time.monotonic()
    next_at = start
    try:
        tty.setcbreak(ifd)
        write(("\x1b[?1049h\x1b[?25l\x1b[?7l" + mouse_on + ansi.clear()).encode())
        out.flush()
        while True:
            now = time.monotonic()
            real = now - start
            t = real * speed
            if (seconds is not None and real >= seconds) or (effect.duration is not None and t >= effect.duration):
                return 0
            cols, rows = os.get_terminal_size(ofd)
            if (cols, rows) != size:
                size = (cols, rows)
                effect.resize(cols, rows)
                cv, prev = Canvas(cols, rows), None
                write(ansi.clear().encode())
            effect.draw(cv, t)
            write(ansi.frame(cv, prev).encode())
            out.flush()
            if prev is None:
                prev = cv.copy()
            else:
                prev.ch[:] = cv.ch
                prev.co[:] = cv.co
            next_at += frame_dt
            if next_at < time.monotonic() - 3 * frame_dt:     # far behind: do not try to catch up
                next_at = time.monotonic()
            while True:
                wait = max(0.0, next_at - time.monotonic())
                ready, _, _ = select.select([ifd], [], [], wait)
                if not ready:
                    break
                data = os.read(ifd, 4096).decode("utf-8", "replace")
                for ev in parse_input(data):
                    tnow = (time.monotonic() - start) * speed
                    if ev[0] == "mouse":
                        effect.pointer(ev[1], ev[2], tnow)
                    elif any_key_quits or not effect.key(ev[1], tnow):
                        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        write((mouse_off + "\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l").encode())
        out.flush()
        termios.tcsetattr(ifd, termios.TCSADRAIN, saved)
