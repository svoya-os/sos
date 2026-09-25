"""OKLCH helpers for the mascot palettes (DESIGN.md §10, §13).

Outfit shades are derived from any color by setting OKLCH lightness (hue and chroma kept, chroma reduced
only as far as needed to stay inside sRGB). The same maths is mirrored in design/mascot/jackson.js.
"""
from __future__ import annotations

import math
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# §13: outfit = (base, shade, light) lightness for dark and light themes
OUTFIT_L = {"dark": (0.32, 0.25, 0.40), "light": (0.45, 0.36, 0.56)}
OUTFIT_CMAX = {"dark": 0.075, "light": 0.11}   # dyed, not neon: garments stay calm next to the UI
# Dark oranges and yellows turn to mud-brown, so they get less chroma: a smooth dip centred on hue 75°
# (0 below 35° and above 115°), up to 40% less. Amber/Signal → warm coffee instead of mustard.
BROWN_HUE, BROWN_WIDTH, BROWN_DIP = 75.0, 40.0, 0.4


def outfit_cmax(hue: float, mode: str) -> float:
    d = (hue - BROWN_HUE + 180) % 360 - 180
    band = math.cos(d / BROWN_WIDTH * math.pi / 2) if abs(d) < BROWN_WIDTH else 0.0
    return OUTFIT_CMAX[mode] * (1 - BROWN_DIP * band)


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hex_to_oklch(h: str) -> tuple[float, float, float]:
    r, g, b = (_lin(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    bb = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def _oklch_to_linear(L: float, C: float, H: float) -> tuple[float, float, float]:
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def oklch_to_hex(L: float, C: float, H: float) -> str:
    """Convert, reducing chroma (bisection) until the color fits in sRGB."""
    lo, hi = 0.0, C
    rgb = _oklch_to_linear(L, C, H)
    if not all(-1e-4 <= v <= 1 + 1e-4 for v in rgb):
        for _ in range(24):
            mid = (lo + hi) / 2
            if all(-1e-4 <= v <= 1 + 1e-4 for v in _oklch_to_linear(L, mid, H)):
                lo = mid
            else:
                hi = mid
        rgb = _oklch_to_linear(L, lo, H)
    return "#" + "".join(f"{round(min(1, max(0, _gam(min(1, max(0, v))))) * 255):02x}" for v in rgb)


def with_lightness(h: str, L: float, cmax: float | None = None) -> str:
    _, C, H = hex_to_oklch(h)
    return oklch_to_hex(L, min(C, cmax) if cmax else C, H)


def shift(h: str, dL: float) -> str:
    L, C, H = hex_to_oklch(h)
    return oklch_to_hex(max(0, min(1, L + dL)), C, H)


def outfit(color: str, mode: str) -> dict[str, str]:
    b, s, l = OUTFIT_L[mode]
    cm = outfit_cmax(hex_to_oklch(color)[2], mode)
    return {"outfit": with_lightness(color, b, cm), "outfitShade": with_lightness(color, s, cm),
            "outfitLight": with_lightness(color, l, cm)}


def detail(accent: str) -> dict[str, str]:
    """`detail` = the accent itself (horns, LEDs, drawstrings) + a shade and a highlight."""
    L, _, _ = hex_to_oklch(accent)
    return {"detail": accent, "detailShade": shift(accent, -0.13 if L > 0.45 else -0.08),
            "detailLight": shift(accent, min(0.12, 0.97 - L))}


def accents() -> dict[str, dict]:
    data = tomllib.loads((ROOT / "themes" / "accents.toml").read_text())
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def luminance(h: str) -> float:
    r, g, b = (_lin(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)
