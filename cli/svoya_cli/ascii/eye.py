"""``sos eye``: Jackson's eye across the whole terminal.

Lids drawn with half blocks, an iris of fibers, a black pupil with a pink rim (the alive part),
a highlight. It blinks every 4–7 seconds, follows the mouse when the terminal reports it and looks
around by itself otherwise, and the pupil opens wider at night (Tallinn time by default).

Jackson's states: thinking (the iris turns, glyphs run along its edge), listening (the pupil pulses
like a voice), done (a pink flash in the pupil and a blink), error (a glitch: the eye falls apart into
symbols and comes back). ``--story`` is the 14-second film: the camera flies into the pupil, stars
and a small cat-Jackson waving inside, then back out, a blink, the end.
"""
from __future__ import annotations

import bisect
import datetime as dt
import math
import random

from .engine import (ACCENT, ASPECT, BLOCKS, FG, GLYPHS, NOISE, RAMP, Canvas, Effect, clamp, ease, ease_in,
                     ease_out, rnd)

STATES = ("idle", "thinking", "listening", "done", "error")
STORY_LEN = 14.0
STORY_LINE = "> LOOK CLOSER"
FLASH_GAP = 0.5            # two flashes at least this far apart: never more than 3 a second
ZOOM_MAX = 22.0

# cat-Jackson for the story; "o" are his (pink) eyes, the second frame waves
CAT = (
    ["  ▄▀▄     ▄▀▄    ",
     "  █ ▀▀▀▀▀▀▀ █    ",
     "  █  o   o  █    ",
     "  █    ▾    █    ",
     "   ▀▄▄▄▄▄▄▄▀     ",
     "    ▐▌   ▐▌      "],
    ["  ▄▀▄     ▄▀▄  ▄▄",
     "  █ ▀▀▀▀▀▀▀ █ ▐█▌",
     "  █  o   o  █▄▀  ",
     "  █    ▾    █    ",
     "   ▀▄▄▄▄▄▄▄▀     ",
     "    ▐▌   ▐▌      "],
)


BIG = {"█": ("██", "██"), "▀": ("██", "  "), "▄": ("  ", "██"), "▌": ("█ ", "█ "), "▐": (" █", " █"),
       "o": ("oo", "oo"), "▾": ("▀▀", "  ")}


def scale2(art: list[str]) -> list[str]:
    """The cat twice as big for a big terminal: every cell becomes 2×2, blocks stay blocks."""
    out = []
    for line in art:
        top, bot = "", ""
        for c in line:
            a, b = BIG.get(c, (c + c if c != " " else "  ", "  "))
            top, bot = top + a, bot + b
        out += [top, bot]
    return out


def is_night(tz: str = "Europe/Tallinn", now: dt.datetime | None = None) -> bool:
    try:
        from zoneinfo import ZoneInfo
        local = (now or dt.datetime.now(dt.timezone.utc)).astimezone(ZoneInfo(tz))
    except Exception:                       # no tz data: the computer's own clock
        local = (now or dt.datetime.now()).astimezone()
    return local.hour >= 22 or local.hour < 6


class Eye(Effect):
    wants_mouse = True

    def __init__(self, state: str = "idle", hud: bool = True, seed: int = 7, night: bool | None = None,
                 tz: str = "Europe/Tallinn", story: bool = False, clock=None):
        self.mode = state if state in ("idle", "thinking", "listening") else "idle"
        self.recurring = state if state in ("done", "error") else None
        self.hud = hud and not story
        self.story = story
        self.duration = STORY_LEN if story else None
        self.still_at = 2.2 if not story else 2.4
        self.tz = tz
        self.night = is_night(tz) if night is None else night
        self.night_fixed = night is not None
        self.clock = clock
        self.events: list[tuple[str, float]] = []        # ("done"|"error"|"blink", t)
        self.mouse: tuple[float, float, float] | None = None
        self.g_cur = (0.0, 0.0)
        self.last_t = None
        rng = random.Random(seed)
        self.blinks, t = [], 1.5
        while t < 3600:
            self.blinks.append(t)
            t += rng.uniform(4.0, 7.0)
        self.saccades, t, prev = [(0.0, (0.0, 0.0))], 0.8, (0.0, 0.0)
        while t < 3600:
            if rng.random() < 0.35:
                tgt = (rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15))
            else:
                ang = rng.uniform(0, 2 * math.pi)
                rad = rng.uniform(0.45, 1.0)
                tgt = (math.cos(ang) * rad, math.sin(ang) * rad * 0.8)
            self.saccades.append((t, tgt))
            prev = tgt
            t += rng.uniform(0.9, 3.2)
        self.saccade_t = [s[0] for s in self.saccades]
        self.w = self.h = 0

    # ---- geometry --------------------------------------------------------------------------------
    def resize(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.tiny = w < 24 or h < 9
        self.narrow = w < 80
        self.top = 1 if self.hud and not self.tiny else 0
        rows = h - 2 * self.top
        self.cx = w / 2.0
        self.cy = (self.top + rows / 2.0) * ASPECT          # in column units
        self.b = min(rows * ASPECT * 0.40, w * 0.45 * 0.46)
        self.a = self.b / 0.46
        self.R = self.b * 0.86
        self.r0 = self.R * 0.36
        self.gmax = (max(0.0, self.a - self.R * 1.15), self.b * 0.32)
        n = w * h
        self.bg_ch, self.bg_co = [" "] * n, [0] * n
        if not self.narrow and not self.story:
            for i in range(n):
                v = rnd(i, 3, 1)
                if v < 0.02:
                    self.bg_ch[i], self.bg_co[i] = ("·" if v < 0.013 else "."), NOISE
        # the sclera's grain is fixed to the cells: the lids only decide where it shows
        self.grain = [(":" if v < 0.025 else ".") if v < 0.09 else None for v in (rnd(k, 7, 2) for k in range(n))]
        self.scratch = Canvas(w, h)

    # ---- time ------------------------------------------------------------------------------------
    def key(self, k: str, t: float) -> bool:
        if k in ("1", "2", "3"):
            self.mode = ("idle", "thinking", "listening")[int(k) - 1]
        elif k in ("4", "5", "enter"):
            self.trigger("done" if k in ("4", "enter") else "error", t)
        elif k in ("b", "B", "и", "И", "space"):
            self.events.append(("blink", t))
        else:
            return super().key(k, t)
        return True

    def trigger(self, kind: str, t: float) -> bool:
        """done/error: refused while the last flash is younger than FLASH_GAP (photosensitivity)."""
        if any(k in ("done", "error") and 0 <= t - te < FLASH_GAP for k, te in self.events):
            return False
        self.events.append((kind, t))
        return True

    def pointer(self, x: int, y: int, t: float) -> None:
        self.mouse = (x + 0.5, (y + 0.5) * ASPECT, t)

    def last_event(self, kind: str, t: float) -> float | None:
        """Time since the latest ``kind`` event (recurring ones from --state done|error too)."""
        best = None
        for k, te in self.events:
            if k == kind and te <= t and (best is None or te > best):
                best = te
        if self.recurring == kind and t >= 1.0:
            te = 1.0 + 4.0 * math.floor((t - 1.0) / 4.0)
            best = te if best is None else max(best, te)
        return None if best is None else t - best

    def openness(self, t: float) -> float:
        times = []
        k = bisect.bisect_right(self.blinks, t)
        if k:
            times.append(self.blinks[k - 1])
        times += [te for kind, te in self.events if kind == "blink"]
        d = self.last_event("done", t)
        if d is not None:
            times.append(t - d + 0.42)
        o = 1.0
        for tb in times:
            p = t - tb
            if 0 <= p < 0.30:
                o = min(o, 1 - ease_in(p / 0.11) if p < 0.11 else 0.0 if p < 0.15 else ease_out((p - 0.15) / 0.15))
        return o

    def gaze(self, t: float) -> tuple[float, float]:
        gx, gy = self.gmax
        if self.mouse and 0 <= t - self.mouse[2] < 4.0:
            nx = clamp((self.mouse[0] - self.cx) / max(1.0, self.a * 0.8), -1.0, 1.0)
            ny = clamp((self.mouse[1] - self.cy) / max(1.0, self.b * 1.2), -1.0, 1.0)
            tgt = (nx * gx, ny * gy)
            step = 1.0 if self.last_t is None else clamp((t - self.last_t) * 14.0)
            self.g_cur = (self.g_cur[0] + (tgt[0] - self.g_cur[0]) * step,
                          self.g_cur[1] + (tgt[1] - self.g_cur[1]) * step)
            return self.g_cur
        k = bisect.bisect_right(self.saccade_t, t) - 1
        t0, p1 = self.saccades[k]
        p0 = self.saccades[k - 1][1] if k else p1
        e = ease((t - t0) / 0.16)
        jx = 0.25 * math.sin(t * 7.1) * math.sin(t * 2.3)
        x, y = p0[0] + (p1[0] - p0[0]) * e, p0[1] + (p1[1] - p0[1]) * e
        self.g_cur = (x * gx + jx, y * gy)
        return self.g_cur

    # ---- the film ----------------------------------------------------------------------------------
    def story_at(self, t: float) -> dict:
        s = {"open": 1.0, "g": (0.0, 0.0), "z": 1.0, "inside": 0.0, "cat": 0.0, "paw": 0, "text": 0}
        gx, gy = self.gmax
        s["open"] = ease((t - 0.3) / 1.0)
        for tb in (3.1, 12.5):
            p = t - tb
            if 0 <= p < 0.30:
                s["open"] = min(s["open"], 1 - ease_in(p / 0.11) if p < 0.11 else 0.0 if p < 0.15
                                else ease_out((p - 0.15) / 0.15))
        if t >= 13.25:
            s["open"] = 1 - ease((t - 13.25) / 0.45)
        look = [(0.0, (0.35, -0.1)), (1.0, (0.0, 0.0)), (2.0, (-0.5, 0.25)), (2.6, (0.0, 0.0))]
        k = max(i for i, (tt, _) in enumerate(look) if tt <= max(t, 0.0))
        p0 = look[k - 1][1] if k else look[0][1]
        e = ease((t - look[k][0]) / 0.16)
        s["g"] = ((p0[0] + (look[k][1][0] - p0[0]) * e) * gx, (p0[1] + (look[k][1][1] - p0[1]) * e) * gy)
        if 3.7 <= t < 6.0:
            s["z"] = math.exp(math.log(ZOOM_MAX) * ease_in((t - 3.7) / 2.3))
        elif 6.0 <= t < 10.0:
            s["z"] = ZOOM_MAX
            s["inside"] = min(ease((t - 6.0) / 0.4), 1 - ease((t - 9.6) / 0.4))
            s["cat"] = min(ease((t - 6.4) / 0.6), 1 - ease((t - 9.3) / 0.5))
            s["paw"] = 1 if 7.1 <= t < 8.9 and int((t - 7.1) / 0.3) % 2 == 0 else 0
        elif 10.0 <= t < 12.0:
            s["z"] = math.exp(math.log(ZOOM_MAX) * (1 - ease_out((t - 10.0) / 2.0)))
        if t < 1.6:
            n = len(STORY_LINE)
            s["text"] = min(n, int(max(0.0, t - 0.05) / 0.055) + 1) if t > 0.05 else 0
            s["text_fade"] = ease((t - 1.25) / 0.35)
        return s

    # ---- drawing ---------------------------------------------------------------------------------
    def draw(self, cv: Canvas, t: float) -> None:
        if (cv.w, cv.h) != (self.w, self.h):
            self.resize(cv.w, cv.h)
        if not self.night_fixed and int(t) % 60 == 0 and self.last_t is not None and int(self.last_t) % 60 != 0:
            self.night = is_night(self.tz)
        cv.fill(self.bg_ch, self.bg_co)
        if self.tiny:
            self.draw_tiny(cv, t)
            self.last_t = t
            return
        frame = int(t * 30)
        if self.story:
            s = self.story_at(t)
            if s["inside"] > 0 or 6.0 <= t < 10.0:
                self.draw_inside(cv, t, s)
            else:
                self.draw_eye(cv, t, frame, s["open"], s["g"], self.pupil(t), s["z"], thinking=False)
            if s["text"]:
                self.draw_line(cv, s)
            self.last_t = t
            return
        op = self.openness(t)
        g = self.gaze(t)
        rp = self.pupil(t)
        err = self.last_event("error", t)
        if err is not None and err < 1.25:
            self.draw_error(cv, t, frame, err, op, g, rp)
        else:
            self.draw_eye(cv, t, frame, op, g, rp, 1.0, thinking=self.mode == "thinking")
            done = self.last_event("done", t)
            if done is not None and done < 0.35:
                self.flash(cv, g, rp, 1 - ease(done / 0.35))
        if self.hud:
            self.draw_hud(cv, t)
        self.last_t = t

    def pupil(self, t: float) -> float:
        r = self.r0 * (1.22 if self.night else 1.0)
        if self.mode == "listening" and not self.story:
            env = clamp(0.5 + 0.5 * math.sin(t * 7.3) * math.sin(t * 2.1 + 1.0) + 0.2 * math.sin(t * 13.7))
            r *= 1.0 + 0.16 * env
        d = self.last_event("done", t)
        if d is not None and d < 1.6:
            r *= 1.0 - 0.28 * (ease(d / 0.15) if d < 0.15 else 1 - ease((d - 0.15) / 1.45))
        return r

    def draw_eye(self, cv: Canvas, t: float, frame: int, op: float, g: tuple[float, float], rp: float,
                 z: float, thinking: bool) -> None:
        w, h = cv.w, cv.h
        ch, co = cv.ch, cv.co
        sin, sqrt, atan2 = math.sin, math.sqrt, math.atan2
        cx, cy = self.cx, self.cy
        a, b, R = self.a * z, self.b * z, self.R * z
        rp *= z
        icx, icy = cx + g[0] * z, cy + g[1] * z
        breath = 1.0 + 0.07 * sin(t * 2 * math.pi / 6.4)
        narrow = self.narrow
        # lids: per column the upper and lower edge (in column units, y down)
        up, lo = {}, {}
        i0, i1 = max(0, int(cx - a)), min(w, int(cx + a) + 1)
        for i in range(i0, i1):
            u = (i + 0.5 - cx) / a
            if u * u >= 1:
                continue
            sh = (1 - u * u) ** 0.8
            yc = cy + b * 0.30 * sh
            up[i] = yc + (cy - b * sh - yc) * op
            lo[i] = yc + (cy + b * 0.88 * sh - yc) * op
        # sclera: sparse grey grain inside the lids
        grain = self.grain
        for i, yu in up.items():
            yl = lo[i]
            for j in range(max(0, int(yu / ASPECT)), min(h - 1, int(yl / ASPECT)) + 1):
                k = j * w + i
                gr = grain[k]
                if gr and yu < (j + 0.5) * ASPECT < yl:
                    ch[k], co[k] = gr, NOISE
        # iris, pupil, highlight
        rot = t * 0.9 if thinking else 0.0
        fa, fb = (17, 5) if narrow else (29, 7)
        rc = rp / R + 0.13 if R else 0.5
        ring = 1.7 * max(1.0, z ** 0.5)
        hx, hy, hr = icx - 0.30 * R, icy - 0.34 * R, max(1.1, 0.13 * R)
        ia, ib = max(0, int(icx - R)), min(w, int(icx + R) + 2)
        ja, jb = max(0, int((icy - R) / ASPECT)), min(h, int((icy + R) / ASPECT) + 2)
        R2 = R * R
        for j in range(ja, jb):
            y = (j + 0.5) * ASPECT
            dy = y - icy
            dy2 = dy * dy
            base = j * w
            for i in range(ia, ib):
                yu = up.get(i)
                if yu is None or not (yu < y < lo[i]):
                    continue
                dx = i + 0.5 - icx
                d2 = dx * dx + dy2
                if d2 > R2:
                    continue
                k = base + i
                d = sqrt(d2)
                hd = sqrt((i + 0.5 - hx) ** 2 + (y - hy) ** 2)
                if hd < hr:
                    ch[k], co[k] = "█", FG
                    continue
                if hd < hr * 1.6:
                    ch[k], co[k] = "▓", FG
                    continue
                if d < rp:
                    ch[k], co[k] = " ", 0
                    continue
                if d < rp + ring:
                    ch[k], co[k] = BLOCKS[3 - int(2.999 * (d - rp) / ring)], ACCENT
                    continue
                rho = d / R
                if rho > 0.94:
                    ch[k], co[k] = (":" if rnd(i, j, frame // 4) < 0.8 else "."), FG
                    continue
                th = atan2(dy, dx)
                f1 = 0.5 + 0.5 * sin(th * fa + 1.4 * sin(th * fb + rho * 4.0) + rot)
                f2 = 0.5 + 0.5 * sin(th * 47 - rho * 7.0 - rot * 0.5) if not narrow else 0.5
                inten = (0.22 + 0.72 * (0.8 * f1 + 0.2 * f2)) * (1.0 - 0.6 * clamp((rho - 0.70) / 0.25))
                inten += 0.22 * math.exp(-((rho - rc) / 0.07) ** 2)
                ch[k], co[k] = RAMP[int(clamp(inten * breath) * 9.999)], FG
        if thinking:
            self.thinking_ring(cv, t, icx, icy, R, up, lo)
        # lids on top: the upper lid is a thick half-block line with lashes, the lower one thin
        lash = not narrow and z < 1.5
        th_up = 1.8 * z ** 0.5
        for i, yu in up.items():
            u = (i + 0.5 - cx) / a
            taper = 0.45 + 0.55 * (1 - u * u)
            self.halfline(cv, i, yu - th_up * taper, yu, FG)
            self.halfline(cv, i, lo[i], lo[i] + 1.0, FG)
            if lash and i % 3 == 0 and 0.18 < abs(u) < 0.9:
                top = int((yu - th_up * taper) / ASPECT)
                c = "\\" if u < -0.3 else "/" if u > 0.3 else "|"
                step = -1 if c == "\\" else 1 if c == "/" else 0
                for n in range(1, 3 if abs(u) < 0.45 else 2):
                    cv.put(i + step * (n - 1), top - n, c, FG)
            # the edges shiver a little
            if rnd(i, frame, 5) < 0.18:
                jj = int((yu - th_up * taper) / ASPECT) - 1 - int(rnd(i, frame, 6) * 2)
                if 0 <= jj < h and ch[jj * w + i] == " ":
                    ch[jj * w + i], co[jj * w + i] = ".", NOISE

    @staticmethod
    def halfline(cv: Canvas, i: int, y0: float, y1: float, slot: int) -> None:
        """Fills column i from y0 to y1 (column units) at half-row resolution: ▀ ▄ █."""
        h0, h1 = int(y0 / ASPECT * 2), int(y1 / ASPECT * 2)
        if h1 < h0:
            h0, h1 = h1, h0
        cells: dict[int, int] = {}
        for hh in range(h0, h1 + 1):
            cells[hh // 2] = cells.get(hh // 2, 0) | (1 if hh % 2 == 0 else 2)
        for j, m in cells.items():
            cv.put(i, j, "▀" if m == 1 else "▄" if m == 2 else "█", slot)

    def thinking_ring(self, cv: Canvas, t: float, icx: float, icy: float, R: float, up: dict, lo: dict) -> None:
        r = R + 2.0
        n = max(12, int(2 * math.pi * r / 2.4))
        head = (t * 2.4) % (2 * math.pi)
        for k in range(n):
            ang = 2 * math.pi * k / n
            dlt = (head - ang) % (2 * math.pi)
            if dlt > 2.8:
                continue
            i = int(icx + math.cos(ang) * r)
            y = icy + math.sin(ang) * r
            yu = up.get(i)
            if yu is None or not (yu < y < lo[i]):
                continue
            v = 1 - dlt / 2.8
            c = GLYPHS[(k + int(t * 12)) % len(GLYPHS)] if v > 0.55 else RAMP[3 + int(v * 6)]
            cv.put(i, int(y / ASPECT), c, FG)

    def flash(self, cv: Canvas, g: tuple[float, float], rp: float, amount: float) -> None:
        """«Done»: the pupil fills with pink and fades (one flash, rate-limited by trigger())."""
        icx, icy = self.cx + g[0], self.cy + g[1]
        c = BLOCKS[int(clamp(amount) * 4.999)]
        for j in range(max(0, int((icy - rp) / ASPECT)), min(cv.h, int((icy + rp) / ASPECT) + 2)):
            for i in range(max(0, int(icx - rp)), min(cv.w, int(icx + rp) + 2)):
                if (i + 0.5 - icx) ** 2 + ((j + 0.5) * ASPECT - icy) ** 2 < rp * rp and c != " ":
                    cv.put(i, j, c, ACCENT)

    def draw_error(self, cv: Canvas, t: float, frame: int, dt_: float, op: float, g: tuple[float, float],
                   rp: float) -> None:
        """Two frames of a broken grid, then the eye falls apart into symbols and comes back."""
        sc = self.scratch
        sc.fill()
        self.draw_eye(sc, t, frame, op, g, rp, 1.0, thinking=False)
        w, h = cv.w, cv.h
        if dt_ < 0.067:
            for j in range(h):
                if rnd(j, frame, 11) < 0.45:
                    off = int((rnd(j, frame, 12) - 0.5) * 16)
                    row = sc.ch[j * w:(j + 1) * w]
                    cols = sc.co[j * w:(j + 1) * w]
                    sc.ch[j * w:(j + 1) * w] = row[-off:] + row[:-off] if off else row
                    sc.co[j * w:(j + 1) * w] = cols[-off:] + cols[:-off] if off else cols
            for k in range(w * h):
                if sc.ch[k] != " ":
                    if rnd(k, frame, 13) < 0.08:
                        sc.ch[k], sc.co[k] = GLYPHS[int(rnd(k, frame, 14) * len(GLYPHS))], ACCENT
                    cv.ch[k], cv.co[k] = sc.ch[k], sc.co[k]
            return
        p = (dt_ - 0.067) / 1.18
        amp = math.sin(math.pi * clamp(p)) ** 1.4
        for k in range(w * h):
            c = sc.ch[k]
            if c == " ":
                continue
            i, j = k % w, k // w
            dx, dy = i + 0.5 - self.cx, (j + 0.5) * ASPECT - self.cy
            dist = math.hypot(dx, dy) or 1.0
            push = amp * (5.0 + 16.0 * rnd(i, j, 5))
            jx = (rnd(i, j, 8) - 0.5) * 0.9
            nx = int(i + 0.5 + (dx / dist + jx) * push)
            ny = int(((j + 0.5) * ASPECT + (dy / dist + jx) * push) / ASPECT)
            slot = sc.co[k]
            if amp > 0.25 and rnd(i, j, frame // 3) < amp * 0.45:
                c = GLYPHS[int(rnd(i, j, frame // 2) * len(GLYPHS))]
                slot = ACCENT if rnd(i, j, 21) < 0.12 else FG
            cv.put(nx, ny, c, slot)

    def draw_inside(self, cv: Canvas, t: float, s: dict) -> None:
        """Inside the pupil: stars flying past and cat-Jackson waving."""
        w, h = cv.w, cv.h
        f = 0.32 * min(w, h * ASPECT)
        cx, cy = w / 2.0, h * ASPECT / 2.0
        n = max(40, w * h // 16)
        for k in range(n):
            if rnd(k, 1, 4) > s["inside"]:
                continue
            sx, sy = rnd(k, 2, 4) * 2 - 1, rnd(k, 3, 4) * 2 - 1
            z = ((rnd(k, 4, 4) - 0.22 * (t - 6.0)) % 1.0) + 0.03
            i = int(cx + sx * f / z * 1.6)
            j = int((cy + sy * f / z) / ASPECT)
            if 0 <= i < w and 0 <= j < h:
                c = "*" if z < 0.25 else "+" if z < 0.5 else "·" if z < 0.8 else "."
                cv.put(i, j, c, FG if z < 0.35 else NOISE)
        if s["cat"] > 0:
            art = CAT[s["paw"]] if w < 110 or h < 30 else scale2(CAT[s["paw"]])
            x0 = int(cx - len(art[0]) / 2)
            y0 = int(cy / ASPECT - len(art) / 2)
            for dy, line in enumerate(art):
                for dx, c in enumerate(line):
                    if c != " " and rnd(x0 + dx, y0 + dy, 9) < s["cat"]:
                        cv.put(x0 + dx, y0 + dy, "●" if c == "o" else c, ACCENT if c == "o" else FG)

    def draw_line(self, cv: Canvas, s: dict) -> None:
        text = STORY_LINE[:s["text"]]
        x0, y = (cv.w - len(STORY_LINE)) // 2, max(1, cv.h // 8)
        fade = s.get("text_fade", 0.0)
        for k, c in enumerate(text):
            if c != " " and rnd(k, 1, 17) >= fade:
                cv.put(x0 + k, y, c, FG)
        if s["text"] < len(STORY_LINE) or fade == 0.0:
            cv.put(x0 + len(text), y, "█", FG)

    def draw_hud(self, cv: Canvas, t: float) -> None:
        w, h = cv.w, cv.h
        state = self.mode
        for kind in ("error", "done"):
            d = self.last_event(kind, t)
            if d is not None and d < 1.2:
                state = kind
                break
        label = state.upper()
        left = " JACKSON::EYE " if not self.narrow else " EYE "
        cv.text(0, 0, "┌─" + "─" * (w - 4) + "─┐", NOISE)
        cv.text(2, 0, left, FG)
        cv.text(w - len(label) - 4, 0, f" {label} ", ACCENT if state == "error" else FG)
        cv.text(0, h - 1, "└─" + "─" * (w - 4) + "─┘", NOISE)
        hint = " 1-5 STATE · B BLINK · Q QUIT " if not self.narrow else " Q QUIT "
        cv.text(2, h - 1, hint, NOISE)
        if self.clock and not self.narrow:
            hhmm = self.clock()
            cv.text(w - len(hhmm) - 9, h - 1, f" {hhmm} TLN ", FG)

    def draw_tiny(self, cv: Canvas, t: float) -> None:
        shut = self.openness(t) < 0.5
        s = "<(---)>" if shut else "<( @ )>"
        x, y = max(0, (cv.w - len(s)) // 2), cv.h // 2
        cv.text(x, y, s, FG)
        if not shut:
            cv.put(x + 3, y, "@", ACCENT)
