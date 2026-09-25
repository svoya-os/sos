"""Colors. Theme tokens use ``#rrggbb`` or ``#aarrggbb`` — **alpha first** (ARGB, like Qt/QML):
``accentSoft = "#24ffb547"`` is amber at 0x24/255 ≈ 14 % opacity.

Perceptual math uses OKLab/OKLCH (Björn Ottosson, 2020); contrast is WCAG 2.x.
"""
from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass


def _fmt_alpha(a: float) -> str:
    s = f"{a:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"


# ---------------------------------------------------------------- OKLab / OKLCH

def _to_linear(v: float) -> float:
    """sRGB transfer function, inverse (0..1 → linear light)."""
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _from_linear(x: float) -> float:
    """sRGB transfer function (linear light → 0..1); defined for out-of-gamut values too."""
    if abs(x) <= 0.0031308:
        return 12.92 * x
    return math.copysign(1.055 * abs(x) ** (1 / 2.4) - 0.055, x)


def _cbrt(v: float) -> float:
    return math.copysign(abs(v) ** (1 / 3), v)


def _linear_to_oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    l_ = _cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m_ = _cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s_ = _cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def _oklab_to_linear(L: float, a: float, b: float) -> tuple[float, float, float]:  # noqa: N803
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3  # noqa: E741
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def _lch_to_linear(L: float, C: float, h: float) -> tuple[float, float, float]:  # noqa: N803
    rad = math.radians(h)
    return _oklab_to_linear(L, C * math.cos(rad), C * math.sin(rad))


def _in_gamut(rgb: tuple[float, float, float], eps: float = 1e-7) -> bool:
    return all(-eps <= c <= 1 + eps for c in rgb)


INK_DARK_HEX = "#141518"    # DESIGN §10: text on an accent fill is near-black …
INK_LIGHT_HEX = "#ffffff"   # … or white, whichever contrasts more


@dataclass(frozen=True)
class Color:
    r: int
    g: int
    b: int
    a: float = 1.0

    @classmethod
    def parse(cls, s: str) -> "Color":
        h = s.strip()
        if not h.startswith("#"):
            raise ValueError(f"not a color: {s!r}")
        h = h[1:]
        try:
            if len(h) == 3:
                return cls(int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16))
            if len(h) == 6:
                return cls(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
            if len(h) == 8:  # ARGB
                return cls(int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16), int(h[0:2], 16) / 255)
        except ValueError:
            pass
        raise ValueError(f"not a color: {s!r}")

    # ---- formats ----
    @property
    def a8(self) -> int:
        return max(0, min(255, int(self.a * 255 + 0.5)))

    @property
    def hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    @property
    def hexa(self) -> str:
        """``#aarrggbb`` (Qt/QML, theme.json)."""
        return f"#{self.a8:02x}{self.r:02x}{self.g:02x}{self.b:02x}"

    @property
    def strip(self) -> str:
        return f"{self.r:02x}{self.g:02x}{self.b:02x}"

    @property
    def stripa(self) -> str:
        """``rrggbbaa`` — alpha **last** (fuzzel, Hyprland ``rgba(...)``)."""
        return f"{self.r:02x}{self.g:02x}{self.b:02x}{self.a8:02x}"

    @property
    def rgb(self) -> str:
        return f"{self.r},{self.g},{self.b}"

    def rgba(self, alpha: float | None = None) -> str:
        a = self.a if alpha is None else float(alpha)
        return f"rgba({self.r},{self.g},{self.b},{_fmt_alpha(a)})"

    @property
    def ansi(self) -> str:
        """SGR parameters for a truecolor foreground: ``38;2;r;g;b``."""
        return f"38;2;{self.r};{self.g};{self.b}"

    # ---- math ----
    def with_alpha(self, a: float) -> "Color":
        return Color(self.r, self.g, self.b, max(0.0, min(1.0, float(a))))

    def mix(self, other: "Color", t: float) -> "Color":
        """Linear blend: ``t=0`` → self, ``t=1`` → other."""
        t = max(0.0, min(1.0, float(t)))
        f = lambda x, y: int(x + (y - x) * t + 0.5)  # half up (round() is banker's)  # noqa: E731
        return Color(f(self.r, other.r), f(self.g, other.g), f(self.b, other.b), self.a + (other.a - self.a) * t)

    def over(self, bg: "Color") -> "Color":
        """Composite a translucent color over an opaque background → opaque color."""
        return bg.mix(self.with_alpha(1.0), self.a).with_alpha(1.0)

    def hls(self) -> tuple[float, float, float]:
        return colorsys.rgb_to_hls(self.r / 255, self.g / 255, self.b / 255)

    @classmethod
    def from_hls(cls, h: float, l: float, s: float, a: float = 1.0) -> "Color":  # noqa: E741
        r, g, b = colorsys.hls_to_rgb(h % 1.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
        return cls(int(r * 255 + 0.5), int(g * 255 + 0.5), int(b * 255 + 0.5), a)

    def lighten(self, amount: float) -> "Color":
        h, l, s = self.hls()  # noqa: E741
        return Color.from_hls(h, l + float(amount), s, self.a)

    def darken(self, amount: float) -> "Color":
        return self.lighten(-float(amount))

    def with_hue(self, degrees: float) -> "Color":
        _, l, s = self.hls()  # noqa: E741
        return Color.from_hls(degrees / 360.0, l, s, self.a)

    @property
    def hue(self) -> float:
        return self.hls()[0] * 360.0

    def luminance(self) -> float:
        def ch(c: int) -> float:
            v = c / 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * ch(self.r) + 0.7152 * ch(self.g) + 0.0722 * ch(self.b)

    def contrast(self, other: "Color") -> float:
        a, b = self.luminance(), other.luminance()
        hi, lo = max(a, b), min(a, b)
        return (hi + 0.05) / (lo + 0.05)

    # ---- perceptual (OKLab / OKLCH) ----
    def oklab(self) -> tuple[float, float, float]:
        return _linear_to_oklab(_to_linear(self.r / 255), _to_linear(self.g / 255), _to_linear(self.b / 255))

    def oklch(self) -> tuple[float, float, float]:
        """``(L 0..1, C ≥ 0, h degrees 0..360)``; hue is 0 for grays."""
        L, a, b = self.oklab()  # noqa: N806
        C = math.hypot(a, b)  # noqa: N806
        h = math.degrees(math.atan2(b, a)) % 360.0 if C > 1e-9 else 0.0
        return L, C, h

    @classmethod
    def from_oklch(cls, L: float, C: float, h: float, a: float = 1.0) -> "Color":  # noqa: N803
        """OKLCH → sRGB. Out-of-gamut colors keep lightness and hue; chroma is reduced until they fit."""
        L = max(0.0, min(1.0, float(L)))  # noqa: N806
        C = max(0.0, float(C))  # noqa: N806
        rgb = _lch_to_linear(L, C, h)
        if not _in_gamut(rgb):
            lo, hi = 0.0, C
            for _ in range(32):
                mid = (lo + hi) / 2
                if _in_gamut(_lch_to_linear(L, mid, h)):
                    lo = mid
                else:
                    hi = mid
            rgb = _lch_to_linear(L, lo, h)
        to8 = lambda x: max(0, min(255, int(_from_linear(max(0.0, min(1.0, x))) * 255 + 0.5)))  # noqa: E731
        return cls(to8(rgb[0]), to8(rgb[1]), to8(rgb[2]), a)

    def distance(self, other: "Color") -> float:
        """Perceptual distance (Euclidean ΔE in OKLab; ≈0.02 is a just-noticeable difference)."""
        return math.dist(self.oklab(), other.oklab())

    def ink(self) -> "Color":
        """Text color for this fill: near-black or white, whichever contrasts more (ties → dark)."""
        dark, light = Color.parse(INK_DARK_HEX), Color.parse(INK_LIGHT_HEX)
        return dark if self.contrast(dark) >= self.contrast(light) else light

    def __str__(self) -> str:
        return self.hex if self.a >= 1.0 else self.hexa


def terminal_palette(c: dict[str, Color], mode: str) -> dict[str, Color]:
    """16 ANSI colors derived from the semantic tokens of the base theme. Themes define no
    blue/magenta, so they are the ``cloud`` color rotated to 220°/300°. The accent never enters
    the palette: programs' colors stay put when the user changes the accent (DESIGN §10)."""
    dark = mode != "light"
    red, green, yellow, cyan = c["bad"], c["ok"], c["warn"], c["cloud"]
    blue = cyan.with_hue(220)
    magenta = cyan.with_hue(300)
    shift = (lambda x: x.lighten(0.08)) if dark else (lambda x: x.darken(0.08))
    if dark:
        black, white, bblack, bwhite = c["surface3"], c["textDim"], c["textFaint"], c["text"]
    else:
        black, white, bblack, bwhite = c["text"], c["textDim"], c["textFaint"], c["textFaint"].mix(c["lineStrong"], 0.5)
    base = {"black": black, "red": red, "green": green, "yellow": yellow, "blue": blue,
            "magenta": magenta, "cyan": cyan, "white": white}
    pal = dict(base)
    for k, v in base.items():
        bright = {"black": bblack, "white": bwhite}.get(k) or shift(v)
        pal["bright" + k.capitalize()] = bright
    order = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
    for i, k in enumerate(order):
        pal[f"c{i}"] = pal[k]
        pal[f"c{i + 8}"] = pal["bright" + k.capitalize()]
    return pal
