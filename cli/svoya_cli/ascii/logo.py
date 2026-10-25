"""``sos art logo``: the letters SOS gather out of noise, stand lit from the upper left with a glint
passing over them, the boot line grows under them and the signal types itself in its gap,
··· ——— ···; once a loop the picture glitches for two frames, then everything flies apart and
gathers again. The letters are drawn from their outlines (distance to the stroke), so they are
smooth at any terminal size."""
from __future__ import annotations

import math

from .engine import ASPECT, FG, GLYPHS, NOISE, RAMP, Canvas, Effect, clamp, ease, hash3, rnd

PERIOD = 16.0
SIGNAL = "··· ——— ···"
UNIT = 0.16                       # one Morse unit, seconds
SW = 0.12                         # half the stroke width, in letter units (the letters are 1.30 tall)
GATHER, HOLD, SCATTER = 2.0, 12.0, 13.6


def signal_times() -> list[float]:
    times, pos = [], 0
    for c in SIGNAL:
        times.append(pos * UNIT)
        pos += 2 if c == "·" else 4 if c == "—" else 2
    return times


def ring(x: float, y: float, rx: float, ry: float) -> tuple[float, float]:
    """Distance from (x, y) to an ellipse through its own center line (first order: the level
    set's value over its gradient, which keeps the stroke even), and the point's angle on it."""
    u, v = x / rx, y / ry
    q = math.sqrt(u * u + v * v)
    if q < 1e-6:
        return min(rx, ry), 0.0
    gx, gy = x / (rx * rx), y / (ry * ry)
    grad = math.sqrt(gx * gx + gy * gy) / q
    return abs(q - 1.0) / grad, math.atan2(v, u)


def arc(x: float, y: float, rx: float, ry: float, keep, ends: tuple[float, float]) -> float:
    """Distance to an elliptic arc (the angles `keep` accepts) with round ends."""
    d, th = ring(x, y, rx, ry)
    if keep(th):
        return d
    best = math.inf
    for e in ends:
        dx, dy = x - rx * math.cos(e), y - ry * math.sin(e)
        best = min(best, math.sqrt(dx * dx + dy * dy))
    return best


def letters(x: float, y: float) -> float:
    """Distance to the center line of S O S (x across, y down, the word 3.2 wide and 1.3 tall)."""
    sx, sy = 0.33, 0.265
    best = ring(x, y, 0.40, 0.53)[0]                                    # O
    for cx in (-1.15, 1.15):                                            # S, S
        top = arc(x - cx, y + sy, sx, sy, lambda th: th <= -0.35 or th >= math.pi / 2, (-0.35, math.pi / 2))
        bot = arc(x - cx, y - sy, sx, sy, lambda th: -math.pi / 2 <= th <= math.pi - 0.35, (-math.pi / 2, math.pi - 0.35))
        best = min(best, top, bot)
    return best - SW


class Logo(Effect):
    still_at = 7.5

    def __init__(self, hud: bool = True, seed: int = 11):
        self.hud = hud
        self.seed = seed
        self.w = self.h = 0
        self.times = signal_times()

    def resize(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.tiny = w < 24 or h < 9
        self.narrow = w < 80
        self.top = 1 if self.hud and not self.tiny else 0
        rows = h - 2 * self.top
        self.scale = min(0.80 * w / 3.2, 0.40 * rows * ASPECT / 1.3)
        self.cx = w / 2.0
        self.cy = (self.top + rows * 0.44) * ASPECT
        self.line_y = min(h - 1 - self.top, int((self.cy + 0.65 * self.scale) / ASPECT) + 2)
        s = self.seed
        # every cell of the letters: where it is, how deep in the stroke, where it comes from and goes
        self.cells = []
        sc = self.scale
        for j in range(max(0, int((self.cy - 0.8 * sc) / ASPECT)), min(h, int((self.cy + 0.8 * sc) / ASPECT) + 2)):
            yl = ((j + 0.5) * ASPECT - self.cy) / sc
            for i in range(max(0, int(self.cx - 1.7 * sc)), min(w, int(self.cx + 1.7 * sc) + 2)):
                xl = (i + 0.5 - self.cx) / sc
                d = letters(xl, yl)
                if d >= 0:
                    continue
                k = len(self.cells)
                self.cells.append((i, j, xl, yl, clamp(-d / SW),
                                   rnd(k, s, 21) * w, self.top + rnd(k, s, 22) * rows,
                                   rnd(k, s, 24) * w, self.top + rnd(k, s, 25) * rows, 0.9 * rnd(k, s, 23)))
        # star dust, kept off the word and the line
        n = max(6, (w * h) // 70)
        y0, y1 = int((self.cy - 0.75 * sc) / ASPECT), self.line_y
        x0, x1 = int(self.cx - 1.7 * sc), int(self.cx + 1.7 * sc) + 1
        self.dust = []
        for k in range(n):
            x, y = int(rnd(k, s, 31) * w), self.top + int(rnd(k, s, 32) * rows)
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                self.dust.append((x, y, 0.6 + 1.6 * rnd(k, s, 33), 6.28 * rnd(k, s, 34)))

    def shade(self, xl: float, yl: float, depth: float, tl: float) -> str:
        b = (0.30 + 0.62 * depth ** 0.6) * (1.0 + 0.04 * math.sin(tl * 2 * math.pi / 5.0))
        for start in (3.0, 8.0):                                       # a glint crosses the word twice
            if start <= tl < start + 2.0:
                band = -2.2 + 4.4 * ease((tl - start) / 2.0)
                v = ((xl + 0.35 * yl) - band) / 0.18
                b += 0.55 * math.exp(-v * v)
        return RAMP[int(clamp(b) * 9.999)]

    def draw(self, cv: Canvas, t: float) -> None:
        if (cv.w, cv.h) != (self.w, self.h):
            self.resize(cv.w, cv.h)
        cv.fill()
        w, h = cv.w, cv.h
        if self.tiny:
            cv.text(max(0, w // 2 - 1), h // 2, "SOS", FG)
            return
        loop = math.floor(t / PERIOD)
        tl = t - loop * PERIOD
        for x, y, fq, ph in self.dust:
            if math.sin(t * fq + ph) > 0.55:
                cv.put(x, y, ".", NOISE)
        for k, (i, j, xl, yl, depth, sx, sy, ax, ay, delay) in enumerate(self.cells):
            if tl < HOLD:
                p = ease((tl - delay) / 1.1)
                if p >= 1.0:
                    cv.put(i, j, self.shade(xl, yl, depth, tl), FG)
                    continue
                x, y = sx + (i - sx) * p, sy + (j - sy) * p
            elif tl < SCATTER:
                p = ease((tl - HOLD - 0.6 * delay) / 1.0)
                if p <= 0.0:
                    cv.put(i, j, self.shade(xl, yl, depth, tl), FG)
                    continue
                if p >= 1.0:
                    continue
                x, y = i + (ax - i) * p, j + (ay - j) * p
            else:
                continue
            g = GLYPHS[hash3(k, int(t * 12), loop) % len(GLYPHS)]
            cv.put(math.floor(x), math.floor(y), g, NOISE)
        self.boot_line(cv, tl)
        if 10.6 <= tl < 10.67:
            self.glitch(cv, loop)
        if self.hud:
            cv.text(0, 0, "┌─" + "─" * (w - 4) + "─┐", NOISE)
            cv.text(2, 0, " SOS::ART::LOGO " if not self.narrow else " LOGO ", FG)
            cv.text(w - 9, 0, " 26.10 ", FG)
            cv.text(0, h - 1, "└─" + "─" * (w - 4) + "─┘", NOISE)
            cv.text(2, h - 1, " Q QUIT ", NOISE)
            stamp = f"T+{t % 100:05.1f}"
            cv.text(w - len(stamp) - 4, h - 1, f" {stamp} ", NOISE)

    def boot_line(self, cv: Canvas, tl: float) -> None:
        """The boot line grows from the middle, the signal types itself into its gap."""
        if tl < 2.2 or tl >= 12.8:
            return
        grow = ease((tl - 2.2) / 0.8) if tl < 12.0 else 1.0 - ease((tl - 12.0) / 0.8)
        half = int(grow * self.scale * 1.6)
        gap = len(SIGNAL) // 2 + 2
        cx, y = int(self.cx), self.line_y
        for dx in range(gap, half):
            cv.put(cx - dx - 1, y, "─", NOISE)
            cv.put(cx + dx, y, "─", NOISE)
        if tl < 12.0:
            x0 = cx - len(SIGNAL) // 2
            for n, ch in enumerate(SIGNAL):
                if ch != " " and tl - 3.0 >= self.times[n]:
                    cv.put(x0 + n, y, ch, FG)

    def glitch(self, cv: Canvas, loop: int) -> None:
        """Two frames out of line: some rows slide sideways, then everything is back in place."""
        w = cv.w
        for j in range(cv.h):
            if rnd(j, loop, 41) >= 0.3:
                continue
            shift = (1 + int(rnd(j, loop, 42) * 4)) * (1 if rnd(j, loop, 43) < 0.5 else -1)
            row_ch, row_co = cv.ch[j * w:(j + 1) * w], cv.co[j * w:(j + 1) * w]
            for i in range(w):
                src = i - shift
                ok = 0 <= src < w
                cv.ch[j * w + i] = row_ch[src] if ok else " "
                cv.co[j * w + i] = row_co[src] if ok else 0
