"""``sos art planets``: a ringed planet and its moon. The moon's orbit is tilted, so every twelve
seconds it crosses in front of the planet (an eclipse, its shadow on the clouds) and then hides
behind it; star dust drifts and twinkles. Light from the upper left, brightness is density."""
from __future__ import annotations

import math

from .engine import ASPECT, FG, NOISE, RAMP, Canvas, Effect, clamp, rnd

PERIOD = 12.0


class Planets(Effect):
    still_at = 5.6

    def __init__(self, hud: bool = True, seed: int = 3):
        self.hud = hud
        self.seed = seed
        self.w = self.h = 0

    def resize(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.tiny = w < 24 or h < 9
        self.narrow = w < 80
        self.top = 1 if self.hud and not self.tiny else 0
        rows = h - 2 * self.top
        hu = rows * ASPECT
        self.rb = min(w * 0.20, hu * 0.30)
        self.px = w / 2.0 + w * 0.06
        self.py = (self.top + rows / 2.0) * ASPECT + hu * 0.04
        self.rm = self.rb * 0.38
        self.d = self.rb * 2.35
        self.tilt = -0.22
        n = max(12, (w * h) // (44 if self.narrow else 30))
        s = self.seed
        self.dust = [(rnd(k, s, 1), rnd(k, s, 2), 0.002 + 0.006 * rnd(k, s, 3), (rnd(k, s, 4) - 0.5) * 0.002,
                      1.0 + 3.0 * rnd(k, s, 5), 6.28 * rnd(k, s, 6), rnd(k, s, 7)) for k in range(n)]

    def moon(self, t: float) -> tuple[float, float, bool]:
        phi = 2 * math.pi * (t - 5.5) / PERIOD + math.pi / 2
        ex, ey = self.d * math.cos(phi), self.d * 0.22 * math.sin(phi)
        ca, sa = math.cos(self.tilt), math.sin(self.tilt)
        return self.px + ex * ca - ey * sa, self.py + ex * sa + ey * ca, math.sin(phi) > 0

    def draw(self, cv: Canvas, t: float) -> None:
        if (cv.w, cv.h) != (self.w, self.h):
            self.resize(cv.w, cv.h)
        cv.fill()
        if self.tiny:
            cv.text(max(0, cv.w // 2 - 4), cv.h // 2, "( O )  o", FG)
            return
        w, h = cv.w, cv.h
        for u, v, vx, vy, fq, ph, kind in self.dust:
            i = int(((u - vx * t) % 1.0) * w)
            j = self.top + int(((v + vy * t) % 1.0) * (h - 2 * self.top))
            b = 0.5 + 0.5 * math.sin(t * fq + ph)
            c = "." if b < 0.35 else "·" if b < 0.7 else "+" if b < 0.93 or kind < 0.8 else "*"
            cv.put(i, j, c, FG if kind > 0.85 else NOISE)
        mx, my, front = self.moon(t)
        if not front:
            self.sphere(cv, mx, my, self.rm, t, moon=True)
        self.ring(cv, back=True)
        self.sphere(cv, self.px, self.py, self.rb, t, shadow=(mx, my) if front else None)
        self.ring(cv, back=False)
        if front:
            self.cutout(cv, mx, my, self.rm + 1.2)
            self.sphere(cv, mx, my, self.rm, t, moon=True)
        if self.hud:
            eclipse = front and abs(mx - self.px) < self.rb + self.rm
            cv.text(0, 0, "┌─" + "─" * (w - 4) + "─┐", NOISE)
            cv.text(2, 0, " SOS::ART::PLANETS " if not self.narrow else " PLANETS ", FG)
            label = "ECLIPSE" if eclipse else "ORBIT"
            cv.text(w - len(label) - 4, 0, f" {label} ", FG)
            cv.text(0, h - 1, "└─" + "─" * (w - 4) + "─┘", NOISE)
            cv.text(2, h - 1, " Q QUIT ", NOISE)
            stamp = f"T+{t % 100:05.1f}"
            cv.text(w - len(stamp) - 4, h - 1, f" {stamp} ", NOISE)

    def sphere(self, cv: Canvas, ox: float, oy: float, r: float, t: float, moon: bool = False,
               shadow: tuple[float, float] | None = None) -> None:
        """A lit ball: Lambert shading from the upper left; the planet has turning cloud bands and a
        moon shadow during an eclipse, the moon has craters. The dark side hides the stars."""
        w, h = cv.w, cv.h
        ch, co = cv.ch, cv.co
        lx, ly, lz = -0.35, -0.30, 0.89
        sq, sin, atan2 = math.sqrt, math.sin, math.atan2
        tb, cb = math.sin(0.35), math.cos(0.35)
        spin = t * 0.35
        sr = self.rm * 1.1
        sx, sy = (shadow[0] + 0.30 * self.rb, shadow[1] + 0.22 * self.rb) if shadow else (0, 0)
        for j in range(max(0, int((oy - r) / ASPECT)), min(h, int((oy + r) / ASPECT) + 2)):
            y = (j + 0.5) * ASPECT
            ny = (y - oy) / r
            base = j * w
            for i in range(max(0, int(ox - r)), min(w, int(ox + r) + 2)):
                nx = (i + 0.5 - ox) / r
                r2 = nx * nx + ny * ny
                if r2 > 1.0:
                    continue
                nz = sq(1.0 - r2)
                lam = nx * lx + ny * ly + nz * lz
                if moon:
                    inten = max(0.0, lam) * (0.72 + 0.28 * sin(nx * 7.0 + 1.3) * sin(ny * 6.0 - 0.7)) + 0.03
                else:
                    lat = -nx * tb + ny * cb
                    lon = atan2(nx * cb + ny * tb, nz) + spin
                    inten = max(0.0, lam) * (0.86 + 0.14 * sin(lat * 9.0 + 1.6 * sin(lon * 2.0 + lat * 4.0)))
                    inten += 0.35 * (1.0 - nz) ** 4 * max(0.0, -nx * 0.6 - ny * 0.4 + 0.2)
                    if shadow and (i + 0.5 - sx) ** 2 + (y - sy) ** 2 < sr * sr:
                        inten *= 0.12
                k = base + i
                if inten < 0.07:
                    ch[k], co[k] = ("." if r2 > 0.86 and not moon else " "), NOISE
                else:
                    ch[k], co[k] = RAMP[int(clamp(inten) * 9.999)], FG

    @staticmethod
    def cutout(cv: Canvas, ox: float, oy: float, r: float) -> None:
        """A black margin around what passes in front: brutal, and it keeps the shapes apart."""
        for j in range(max(0, int((oy - r) / ASPECT)), min(cv.h, int((oy + r) / ASPECT) + 2)):
            for i in range(max(0, int(ox - r)), min(cv.w, int(ox + r) + 2)):
                if (i + 0.5 - ox) ** 2 + ((j + 0.5) * ASPECT - oy) ** 2 < r * r:
                    cv.put(i, j, " ", 0)

    def ring(self, cv: Canvas, back: bool) -> None:
        """The ring is a tilted ellipse of two bands with a gap: its far half is drawn before the
        planet, its near half after, with a black line on both sides where it crosses the planet."""
        w, h = cv.w, cv.h
        rb, ox, oy = self.rb, self.px, self.py
        ca, sa = math.cos(self.tilt), math.sin(self.tilt)
        ro, kq = 1.82 * rb, 0.28
        span = ro * abs(sa) + ro * kq * ca + 1
        cells = {}
        for j in range(max(0, int((oy - span) / ASPECT)), min(h, int((oy + span) / ASPECT) + 2)):
            y = (j + 0.5) * ASPECT - oy
            for i in range(max(0, int(ox - ro - 1)), min(w, int(ox + ro) + 2)):
                x = i + 0.5 - ox
                xr, yr = x * ca + y * sa, -x * sa + y * ca
                if (yr > 0) == back:
                    continue
                rho = math.sqrt(xr * xr + (yr / kq) ** 2) / rb
                if 1.38 <= rho <= 1.53:
                    c, slot = ("=" if xr < 0.3 * rb else "-"), FG
                elif 1.62 <= rho <= 1.82:
                    c, slot = ("-" if xr < 0.3 * rb else "."), (NOISE if self.narrow or xr > 0 else FG)
                else:
                    continue
                cells[(i, j)] = (c, slot)
        if not back:                       # one black row above and below where it crosses the planet
            span_j: dict[int, list[int]] = {}
            for (i, j) in cells:
                lo_hi = span_j.setdefault(i, [j, j])
                lo_hi[0], lo_hi[1] = min(lo_hi[0], j), max(lo_hi[1], j)
            for i, (j0, j1) in span_j.items():
                for jj in (j0 - 1, j1 + 1):
                    if ((i + 0.5 - ox) / rb) ** 2 + (((jj + 0.5) * ASPECT - oy) / rb) ** 2 < 1:
                        cv.put(i, jj, " ", 0)
        for (i, j), (c, slot) in cells.items():
            cv.put(i, j, c, slot)
