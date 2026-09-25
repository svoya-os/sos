"""The accent system (design/DESIGN.md §10–§11): the accent is independent from the base theme.

Canonical data: ``themes/accents.toml`` (installed as ``/usr/share/svoya/themes/accents.toml``).
Every accent has a variant for dark bases and one for light bases. The user's choice lives in
``~/.config/svoya/svoya.toml``::

    [theme]
    accent = "lilac"        # an id from accents.toml, or "#rrggbb"; default: the base theme's accentDefault

Resolution for a base theme gives the four accent tokens every template uses:

* ``accent``       the variant for the base mode (``signal`` = amber on dark, ink blue on light). A custom hex
                   keeps its OKLCH hue and chroma; only lightness moves until contrast vs ``surface`` ≥ 4.5:1.
* ``accentSoft``   the accent at 14 % (dark) / 9 % (light) alpha — tints, selection backgrounds
* ``accentStrong`` hover/pressed: OKLCH lightness +6 % on dark bases, −6 % on light ones
* ``accentInk``    text on an accent fill: ``#141518`` or ``#ffffff``, whichever contrasts more

Semantic colors (ok, warn, bad, cloud) never come from here, and the accent never replaces them.
"""
from __future__ import annotations

import re
import tomllib
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from ..paths import Paths
from .colors import Color

MIN_CONTRAST = 4.5
SOFT_ALPHA = {"dark": 0.14, "light": 0.09}
STRONG_STEP = 0.06
DEFAULT_ID = "signal"
SEMANTIC = ("ok", "warn", "bad", "cloud")
CLASH_DISTANCE = 0.05      # OKLab ΔE under which a custom accent reads as a semantic color

# gsettings org.gnome.desktop.interface accent-color (GNOME ≥ 47): libadwaita's reference colors
GNOME_ACCENTS = {"blue": "#3584e4", "teal": "#2190a4", "green": "#3a944a", "yellow": "#c88800",
                 "orange": "#ed5b00", "red": "#e62d42", "pink": "#d56199", "purple": "#9141ac"}
GNOME_NEUTRAL = "slate"
GNOME_NEUTRAL_CHROMA = 0.05

CUSTOM_NAME = {"en": "Custom", "ru": "Свой"}


class AccentError(ValueError):
    """A choice that is not an accent. ``hint`` holds an alternative worth suggesting."""

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.hint = hint


@dataclass(frozen=True)
class Accent:
    id: str
    name: dict
    dark: Color
    light: Color
    note: dict = field(default_factory=dict)
    ink: dict = field(default_factory=dict)       # optional fixed ink per mode; empty = auto

    def variant(self, mode: str) -> Color:
        return self.light if mode == "light" else self.dark


@dataclass
class Catalog:
    default: str
    accents: dict[str, Accent]
    path: Path | None = None

    def get(self, accent_id: str) -> Accent | None:
        return self.accents.get(accent_id)


def accents_path(paths: Paths) -> Path:
    return paths.themes_dir / "accents.toml"


def load_catalog(paths: Paths) -> Catalog:
    """accents.toml → Catalog. A missing or broken file gives an empty catalog (custom hex still works)."""
    path = accents_path(paths)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return Catalog(default=DEFAULT_ID, accents={}, path=None)
    accents: dict[str, Accent] = {}
    for aid, v in data.items():
        if not isinstance(v, dict) or "dark" not in v or "light" not in v:
            continue
        try:
            dark, light = Color.parse(str(v["dark"])).with_alpha(1.0), Color.parse(str(v["light"])).with_alpha(1.0)
        except ValueError:
            continue
        ink: dict = {}
        raw_ink = v.get("ink", "auto")
        try:
            if isinstance(raw_ink, str) and raw_ink != "auto":
                ink = {"dark": Color.parse(raw_ink), "light": Color.parse(raw_ink)}
            elif isinstance(raw_ink, dict):
                ink = {k: Color.parse(str(c)) for k, c in raw_ink.items() if k in ("dark", "light") and c != "auto"}
        except ValueError:
            ink = {}
        name = v.get("name") if isinstance(v.get("name"), dict) else {"en": aid.capitalize()}
        accents[aid] = Accent(id=aid, name=name, dark=dark, light=light,
                              note=v.get("note") if isinstance(v.get("note"), dict) else {}, ink=ink)
    default = data.get("default") if data.get("default") in accents else (DEFAULT_ID if DEFAULT_ID in accents else
                                                                         next(iter(accents), DEFAULT_ID))
    return Catalog(default=default, accents=accents, path=path)


# ---------------------------------------------------------------- names people type

_WORDS = {
    # Russian names of the accents (DESIGN §10)
    "сигнал": "signal", "янтарь": "amber", "чернила": "ink", "фосфор": "phosphor", "лед": "ice",
    "сирень": "lilac", "роза": "rose", "моно": "mono",
    # color words
    "фиолетовый": "lilac", "синий": "ink", "зеленый": "phosphor", "голубой": "ice", "розовый": "rose",
    "оранжевый": "amber", "желтый": "amber", "белый": "mono", "черный": "mono", "серый": "mono",
    "violet": "lilac", "purple": "lilac", "blue": "ink", "green": "phosphor", "cyan": "ice", "teal": "ice",
    "pink": "rose", "orange": "amber", "yellow": "amber", "white": "mono", "black": "mono", "gray": "mono",
    "grey": "mono",
}
# Russian inflections («сделай акцент фиолетовым», «сиреневый», «ледяной»): stem → id, most specific first
_STEMS = (("чернил", "ink"), ("янтар", "amber"), ("сигнал", "signal"), ("фосфор", "phosphor"),
          ("сирен", "lilac"), ("фиолет", "lilac"), ("лилов", "lilac"), ("пурпур", "lilac"),
          ("голуб", "ice"), ("бирюз", "ice"), ("ледян", "ice"), ("льд", "ice"), ("лед", "ice"),
          ("синь", "ink"), ("син", "ink"), ("зелен", "phosphor"), ("салатов", "phosphor"),
          ("розов", "rose"), ("роз", "rose"), ("оранж", "amber"), ("желт", "amber"), ("золот", "amber"),
          ("бел", "mono"), ("черн", "mono"), ("сер", "mono"), ("моно", "mono"))
_RESET = {"default", "reset", "auto", "по-умолчанию", "поумолчанию", "умолчание", "сброс", "сбросить",
          "стандарт", "стандартный", "обычный", "авто"}
_RESERVED = {"red": "bad", "красный": "bad", "красн": "bad", "алый": "bad"}
_HEX = re.compile(r"^#?([0-9a-f]{6}|[0-9a-f]{3})$")


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFC", text).strip().lower().replace("ё", "е")
    return t.strip(" \t\"'«».,!?")


def parse_choice(text: str, catalog: Catalog | None = None) -> str | None:
    """What the user typed → an accent id, ``#rrggbb``, or ``None`` (= back to the theme's default).

    Accepts ids and English names (``lilac``), Russian names (``сирень``, ``лёд``/``лед``), color
    words in either language with Russian inflections (``фиолетовым`` → lilac), and hex with or
    without ``#``. Raises ``AccentError`` otherwise (red is reserved for errors).
    """
    t = _norm(text)
    if not t:
        raise AccentError("empty accent")
    known = catalog.accents if catalog and catalog.accents else None
    if t in _RESET:
        return None
    m = _HEX.match(t)
    if m and (t.startswith("#") or len(m.group(1)) == 6):
        h = m.group(1)
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return "#" + h
    if t.startswith("#") or re.fullmatch(r"#?[0-9a-f]{8}", t):
        raise AccentError(f"not an opaque #rrggbb color: {text}")
    ids = set(known) if known else {"signal", "amber", "ink", "phosphor", "ice", "lilac", "rose", "mono"}
    if t in ids:
        return t
    if known:
        for a in known.values():
            if t in {_norm(str(n)) for n in a.name.values()}:
                return a.id
    words = t.replace("-", " ").split()
    for w in words:
        if w in _RESERVED or any(w.startswith(s) for s in _RESERVED):
            raise AccentError("red is reserved for errors", hint="rose")
    for w in words:
        if w in _WORDS and _WORDS[w] in ids:
            return _WORDS[w]
    for w in words:
        for stem, aid in _STEMS:
            if w.startswith(stem) and aid in ids:
                return aid
    raise AccentError(f"unknown accent: {text}")


# ---------------------------------------------------------------- resolution

@dataclass
class Resolved:
    id: str                       # accent id, "custom", or "theme" (no accents.toml: the base theme's own)
    name: dict
    mode: str
    color: Color                  # accent
    soft: Color                   # accentSoft
    strong: Color                 # accentStrong
    ink: Color                    # accentInk
    requested: Color              # before any contrast adjustment
    contrast: float               # accent vs surface
    ink_contrast: float
    adjusted: bool = False
    custom: str | None = None     # the user's own "#rrggbb"
    note: dict = field(default_factory=dict)
    clash: str | None = None      # semantic token the accent looks like (custom colors only)
    fallback: str | None = None   # why the configured choice was not used

    @property
    def gnome(self) -> str:
        return gnome_accent(self.color)

    def as_json(self) -> dict:
        return {"id": self.id, "name": dict(self.name), "mode": self.mode, "color": self.color.hex,
                "soft": self.soft.hexa, "strong": self.strong.hex, "ink": self.ink.hex,
                "requested": self.requested.hex, "adjusted": self.adjusted, "custom": self.custom,
                "contrast": round(self.contrast, 2), "inkContrast": round(self.ink_contrast, 2),
                "gnome": self.gnome, "clash": self.clash, "fallback": self.fallback,
                "note": dict(self.note) if self.note else None}


def fit_contrast(color: Color, surface: Color, minimum: float = MIN_CONTRAST) -> tuple[Color, bool]:
    """Keep OKLCH hue and chroma; move lightness (up on dark surfaces, down on light ones) just far
    enough for ``minimum`` contrast. Returns ``(color, adjusted)``. Chroma shrinks only where the
    color would leave the sRGB gamut."""
    color = color.with_alpha(1.0)
    if color.contrast(surface) >= minimum:
        return color, False
    L0, C, h = color.oklch()  # noqa: N806
    lighter_first = surface.contrast(Color(255, 255, 255)) >= surface.contrast(Color(0, 0, 0))
    best = color
    for up in (lighter_first, not lighter_first):
        end = 1.0 if up else 0.0
        if Color.from_oklch(end, C, h).contrast(surface) < minimum:
            cand = Color.from_oklch(end, C, h)
            if cand.contrast(surface) > best.contrast(surface):
                best = cand
            continue
        lo, hi = L0, end                       # lo fails, hi passes
        for _ in range(40):
            mid = (lo + hi) / 2
            if Color.from_oklch(mid, C, h).contrast(surface) >= minimum:
                hi = mid
            else:
                lo = mid
        return Color.from_oklch(hi, C, h), True
    return best, True                          # unreachable surfaces (mid gray): the best we can do


def strong_variant(color: Color, mode: str) -> Color:
    """Hover/pressed: OKLCH lightness +6 % on dark bases, −6 % on light ones (flipped at the ends)."""
    L, C, h = color.oklch()  # noqa: N806
    step = STRONG_STEP if mode != "light" else -STRONG_STEP
    if not 0.0 <= L + step <= 1.0:
        step = -step
    return Color.from_oklch(L + step, C, h)


def gnome_accent(color: Color) -> str:
    """Closest GNOME accent-color name (blue, teal, green, yellow, orange, red, pink, purple, slate)."""
    _, C, h = color.oklch()
    if C < GNOME_NEUTRAL_CHROMA:
        return GNOME_NEUTRAL

    def dist(name: str) -> float:
        d = abs(Color.parse(GNOME_ACCENTS[name]).oklch()[2] - h) % 360
        return min(d, 360 - d)
    return min(GNOME_ACCENTS, key=dist)


def _clash(color: Color, colors: dict[str, Color]) -> str | None:
    for tok in SEMANTIC:
        c = colors.get(tok)
        if c is not None and color.distance(c.with_alpha(1.0)) < CLASH_DISTANCE:
            return tok
    return None


def resolve(choice: str | None, *, mode: str, colors: dict[str, Color], catalog: Catalog,
            theme_default: str | None = None) -> Resolved:
    """The user's choice (id | #hex | None) for a base theme (``mode`` + its colors) → Resolved."""
    surface = colors["surface"].with_alpha(1.0)
    fallback = None
    custom = None
    accent: Accent | None = None
    if choice:
        try:
            parsed = parse_choice(choice, catalog)
        except AccentError as e:
            parsed, fallback = None, str(e)
        if parsed and parsed.startswith("#"):
            custom = parsed
        elif parsed:
            accent = catalog.get(parsed)
            if accent is None:
                fallback = f"unknown accent: {choice}"
    if accent is None and custom is None:
        for cand in (theme_default, catalog.default):
            if cand and catalog.get(cand):
                accent = catalog.get(cand)
                break
    if custom is not None:
        requested = Color.parse(custom)
        name, aid, note = dict(CUSTOM_NAME), "custom", {}
    elif accent is not None:
        requested = accent.variant(mode)
        name, aid, note = dict(accent.name), accent.id, dict(accent.note)
    else:                                   # no accents.toml at all: the base theme's own tokens
        requested = colors["accent"].with_alpha(1.0)
        name, aid, note = {"en": "Theme", "ru": "Тема"}, "theme", {}
    color, adjusted = fit_contrast(requested, surface)
    ink = accent.ink.get(mode) if accent is not None and accent.ink.get(mode) else color.ink()
    return Resolved(id=aid, name=name, mode=mode, color=color,
                    soft=color.with_alpha(SOFT_ALPHA["light" if mode == "light" else "dark"]),
                    strong=strong_variant(color, mode), ink=ink, requested=requested,
                    contrast=color.contrast(surface), ink_contrast=color.contrast(ink), adjusted=adjusted,
                    custom=custom, note=note, clash=_clash(color, colors) if custom else None, fallback=fallback)


def listing(catalog: Catalog, current_id: str | None, current_custom: str | None = None,
            surfaces: dict[str, Color] | None = None) -> list[dict]:
    """``sos theme accents --json``: every accent with both variants and their inks, plus «custom»."""
    out = []
    for a in catalog.accents.values():
        out.append({"id": a.id, "name": dict(a.name), "note": dict(a.note) if a.note else None,
                    "dark": a.dark.hex, "light": a.light.hex,
                    "ink": {"dark": (a.ink.get("dark") or a.dark.ink()).hex, "light": (a.ink.get("light") or a.light.ink()).hex},
                    "gnome": {"dark": gnome_accent(a.dark), "light": gnome_accent(a.light)},
                    "default": a.id == catalog.default, "current": a.id == current_id})
    entry: dict = {"id": "custom", "name": dict(CUSTOM_NAME), "note": None, "dark": None, "light": None,
                   "ink": None, "gnome": None, "default": False, "current": current_id == "custom",
                   "custom": current_custom}
    if current_custom and surfaces:
        dark, _ = fit_contrast(Color.parse(current_custom), surfaces["dark"])
        light, _ = fit_contrast(Color.parse(current_custom), surfaces["light"])
        entry.update({"dark": dark.hex, "light": light.hex, "ink": {"dark": dark.ink().hex, "light": light.ink().hex},
                      "gnome": {"dark": gnome_accent(dark), "light": gnome_accent(light)}})
    out.append(entry)
    return out
