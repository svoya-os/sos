"""Colors. Theme tokens use ``#rrggbb`` or ``#aarrggbb`` — **alpha first** (ARGB, like Qt/QML):
``accentSoft = "#24ffb547"`` is amber at 0x24/255 ≈ 14 % opacity.
"""
from __future__ import annotations

import colorsys
from dataclasses import dataclass


def _fmt_alpha(a: float) -> str:
    s = f"{a:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"


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

    def __str__(self) -> str:
        return self.hex if self.a >= 1.0 else self.hexa


def terminal_palette(c: dict[str, Color], mode: str) -> dict[str, Color]:
    """16 ANSI colors derived from the semantic tokens (themes define no blue/magenta, so they
    are the ``cloud`` color rotated to 220°/300°, or the accent when the accent is blue)."""
    dark = mode != "light"
    red, green, yellow, cyan = c["bad"], c["ok"], c["warn"], c["cloud"]
    blue = c["accent"] if 200 <= c["accent"].hue <= 260 else cyan.with_hue(220)
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
