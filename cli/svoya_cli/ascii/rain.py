"""``sos art rain``: rain at night over still water. Far drops are grey ticks, near ones phosphor
streaks slanted by the wind; where a near drop hits the water it bounces and a ring opens and
fades. Every eighteen seconds the rain writes the signal into the water, ··· ——— ···, one symbol
at a time in Morse rhythm, and lets it go. No lightning: never a flash."""
from __future__ import annotations

import math

from .engine import FG, NOISE, Canvas, Effect, rnd

PERIOD = 18.0                 # the signal comes back
SIGNAL_AT = 4.0               # ...this many seconds into each period
SIGNAL = "··· ——— ···"
UNIT = 0.16                   # one Morse unit, seconds
SLANT = -0.5                  # cells sideways per row: the wind
RING = 0.7                    # how long a ring lasts, seconds


def signal_times() -> list[float]:
    """When each symbol of the signal appears (Morse: a dot is one unit, a dash three, one unit
    between symbols, three between letters)."""
    times, pos = [], 0
    for c in SIGNAL:
        times.append(pos * UNIT)
        pos += 2 if c == "·" else 4 if c == "—" else 2
    return times


class Rain(Effect):
    still_at = 9.0                 # the signal written in full

    def __init__(self, hud: bool = True, seed: int = 5):
        self.hud = hud
        self.seed = seed
        self.w = self.h = 0
        self.times = signal_times()

    def resize(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.tiny = w < 24 or h < 9
        self.narrow = w < 80
        self.top = 1 if self.hud and not self.tiny else 0
        self.bottom = h - 1 - self.top              # the last row inside the frame
        self.ground = self.bottom - 2               # the water's edge; two rows of water below it
        s = self.seed
        n = max(8, (w * h) // (40 if self.narrow else 26))
        self.drops = []
        for k in range(n):
            near = rnd(k, s, 1) < 0.38
            speed = 34.0 + 16.0 * rnd(k, s, 2) if near else 14.0 + 10.0 * rnd(k, s, 2)    # rows a second
            length = (3 if rnd(k, s, 3) > 0.5 else 2) if near else 1
            fall = (self.ground - (self.top - 1)) / speed
            cycle = fall + 0.2 + 1.1 * rnd(k, s, 4)
            rings = near and rnd(k, s, 8) < 0.55
            self.drops.append((k, near, rings, speed, length, fall, cycle, rnd(k, s, 5) * cycle))
        self.edge = ["─" if rnd(i, s, 9) < 0.82 else " " for i in range(w)]

    def column(self, k: int, c: int, y: float) -> int:
        """Where drop k of fall c is at row y: a new place every fall, the wind pushing it aside."""
        span = self.w + (self.ground - self.top + 1) * -SLANT
        return math.floor(rnd(k, c, 7) * span + SLANT * (y - (self.top - 1)))

    def draw(self, cv: Canvas, t: float) -> None:
        if (cv.w, cv.h) != (self.w, self.h):
            self.resize(cv.w, cv.h)
        cv.fill()
        w, h = cv.w, cv.h
        if self.tiny:
            cv.text(max(0, w // 2 - 3), h // 2, "' / '", FG)
            return
        top, ground, bottom = self.top, self.ground, self.bottom
        # the water: the edge, then a slow shimmer
        for i in range(w):
            if self.edge[i] != " ":
                cv.put(i, ground, self.edge[i], NOISE)
        p = t - SIGNAL_AT - math.floor((t - SIGNAL_AT) / PERIOD) * PERIOD
        writing = p < 7.0
        x0 = (w - len(SIGNAL)) // 2
        for j in range(ground + 1, bottom + 1):
            for i in range(w):
                if writing and j == bottom and x0 - 2 <= i < x0 + len(SIGNAL) + 2:
                    continue                                 # still water where the signal is written
                v = math.sin(i * 0.7 + t * 1.3 + j * 2.1) * math.sin(i * 0.23 - t * 0.6) + 0.4 * (rnd(i, j, 11) - 0.5)
                if v > 0.8:
                    cv.put(i, j, "~", NOISE)
        # the drops
        for k, near, rings, speed, length, fall, cycle, phase in self.drops:
            u = t + phase
            c = math.floor(u / cycle)
            local = u - c * cycle
            if local < fall:
                head = (top - 1) + local * speed
                for m in range(length):
                    y = head - m
                    j = math.floor(y)
                    if j < top or j >= ground:
                        continue
                    if near:
                        cv.put(self.column(k, c, y), j, "/" if m < 2 else "'", FG if m < 2 else NOISE)
                    else:
                        cv.put(self.column(k, c, y), j, "'", NOISE)
            elif rings and local - fall < RING:
                self.ring(cv, self.column(k, c, float(ground)), local - fall)
        # the signal, written into the water
        if writing:
            for n, ch in enumerate(SIGNAL):
                if ch == " " or p < self.times[n]:
                    continue
                cv.put(x0 + n, bottom, ch, FG if p < 6.0 else NOISE)
        if self.hud:
            cv.text(0, 0, "┌─" + "─" * (w - 4) + "─┐", NOISE)
            cv.text(2, 0, " SOS::ART::RAIN " if not self.narrow else " RAIN ", FG)
            label = "SIGNAL" if writing else "RAIN"
            cv.text(w - len(label) - 4, 0, f" {label} ", FG)
            cv.text(0, h - 1, "└─" + "─" * (w - 4) + "─┘", NOISE)
            cv.text(2, h - 1, " Q QUIT ", NOISE)
            stamp = f"T+{t % 100:05.1f}"
            cv.text(w - len(stamp) - 4, h - 1, f" {stamp} ", NOISE)

    def ring(self, cv: Canvas, x: int, age: float) -> None:
        """A drop meets the water: it bounces, a ring opens on the water and fades."""
        g = self.ground
        if age < 0.1:
            cv.put(x - 1, g - 1, ".", FG)
            cv.put(x + 1, g - 1, ".", FG)
            cv.put(x, g + 1, "o", FG)
        elif age < 0.25:
            cv.put(x - 1, g + 1, "(", FG)
            cv.put(x + 1, g + 1, ")", FG)
        elif age < 0.45:
            cv.put(x - 2, g + 1, "(", NOISE)
            cv.put(x + 2, g + 1, ")", NOISE)
        else:
            cv.put(x - 3, g + 1, ".", NOISE)
            cv.put(x + 3, g + 1, ".", NOISE)
