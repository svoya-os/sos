"""``sos art heart``: a heart beats seventy-two times a minute, lub-dub, shaded like the planets (a
soft dome lit from the upper left and the front), and a monitor line runs along the bottom with a
spike for every beat. Pink, because it is alive."""
from __future__ import annotations

import math

from .engine import ACCENT, ASPECT, FG, NOISE, RAMP, Canvas, Effect, clamp

BPM = 72
BEAT = 60.0 / BPM
WINDOW = 2.5                      # seconds of the monitor line on screen
LIGHT = (-0.35, 0.35, 0.87)       # x right, y up, z toward you
_LN = math.sqrt(sum(c * c for c in LIGHT))
LX, LY, LZ = (c / _LN for c in LIGHT)


def g(x: float) -> float:
    return math.exp(-x * x)


def phase(t: float) -> float:
    return (t - math.floor(t / BEAT) * BEAT) / BEAT


def pulse(t: float) -> float:
    """How much bigger the heart is: lub, dub, rest."""
    p = phase(t)
    return 0.10 * g((p - 0.06) / 0.05) + 0.06 * g((p - 0.30) / 0.06) + 0.10 * g((p - 1.06) / 0.05)


def ecg(t: float) -> float:
    """The monitor's line in rows above its base: P, the QRS spike with the lub, T."""
    p = phase(t)
    return (-0.4 * g((p - 0.025) / 0.008) + 3.0 * g((p - 0.045) / 0.010) - 0.8 * g((p - 0.065) / 0.010)
            + 0.7 * g((p - 0.30) / 0.05) + 0.4 * g((p - 0.85) / 0.03))


class Heart(Effect):
    still_at = 0.07                # the lub

    def __init__(self, hud: bool = True):
        self.hud = hud
        self.w = self.h = 0

    def resize(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.tiny = w < 24 or h < 9
        self.narrow = w < 80
        self.top = 1 if self.hud and not self.tiny else 0
        rows = h - 2 * self.top
        self.base = h - 1 - self.top - 1          # the monitor line's rest
        self.size = min(0.30 * w, 0.29 * rows * ASPECT) / 1.2
        self.hx = w / 2.0
        self.hy = (self.top + rows * 0.40) * ASPECT

    def draw(self, cv: Canvas, t: float) -> None:
        if (cv.w, cv.h) != (self.w, self.h):
            self.resize(cv.w, cv.h)
        cv.fill()
        w, h = cv.w, cv.h
        if self.tiny:
            cv.text(max(0, w // 2 - 1), h // 2, "<3", ACCENT)
            return
        self.heart(cv, self.size * (1.0 + pulse(t)))
        self.monitor(cv, t)
        if self.hud:
            cv.text(0, 0, "┌─" + "─" * (w - 4) + "─┐", NOISE)
            cv.text(2, 0, " SOS::ART::HEART " if not self.narrow else " HEART ", FG)
            label = f"{BPM} BPM"
            cv.text(w - len(label) - 4, 0, f" {label} ", FG)
            cv.text(0, h - 1, "└─" + "─" * (w - 4) + "─┘", NOISE)
            cv.text(2, h - 1, " Q QUIT ", NOISE)
            stamp = f"T+{t % 100:05.1f}"
            cv.text(w - len(stamp) - 4, h - 1, f" {stamp} ", NOISE)

    def heart(self, cv: Canvas, s: float) -> None:
        """(x² + y² − 1)³ − x²y³ ≤ 0, seen as a soft dome z = ∛−F: its normal decides the light."""
        w, h = cv.w, cv.h
        ch, co = cv.ch, cv.co
        hx, hy = self.hx, self.hy
        for j in range(max(self.top, int((hy - 1.25 * s) / ASPECT)), min(self.base - 1, int((hy + 1.15 * s) / ASPECT) + 2)):
            y = -((j + 0.5) * ASPECT - hy) / s + 0.12
            for i in range(max(0, int(hx - 1.2 * s)), min(w, int(hx + 1.2 * s) + 2)):
                x = (i + 0.5 - hx) / s
                a = x * x + y * y - 1.0
                f = a * a * a - x * x * y * y * y
                if f >= 0.0:
                    continue
                r = 3.0 * (-f) ** (2.0 / 3.0)
                fx = 6.0 * x * a * a - 2.0 * x * y * y * y
                fy = 6.0 * y * a * a - 3.0 * x * x * y * y
                nx, ny = fx / r, fy / r
                n = math.sqrt(nx * nx + ny * ny + 1.0)
                lam = (nx * LX + ny * LY + LZ) / n
                k = j * w + i
                ch[k] = RAMP[int(clamp(0.15 + 0.81 * max(0.0, lam)) * 9.999)]
                co[k] = ACCENT

    def monitor(self, cv: Canvas, t: float) -> None:
        """The last few seconds of the beat as a line: the newest part bright, the older grey."""
        w, base = cv.w, self.base
        step = WINDOW / w
        rows = [base - math.floor(ecg(t - (w - 1 - i) * step) + 0.5) for i in range(w + 1)]
        for i in range(w):
            r, nxt = rows[i], rows[i + 1]
            slot = FG if i >= w - w // 5 else NOISE
            c = "─" if nxt == r else "/" if nxt < r else "\\"
            cv.put(i, r, c, slot)
            for y in range(min(r, nxt) + 1, max(r, nxt)):
                cv.put(i, y, "|", slot)
