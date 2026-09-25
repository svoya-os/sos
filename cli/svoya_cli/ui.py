"""Calm mono output: ``›`` bullets, dim labels, one accent color.

* Truecolor ANSI when the terminal says so (``COLORTERM=truecolor|24bit``), 256 colors otherwise.
* Colors come from the applied theme (``~/.local/state/svoya/theme.json``), Graphite by default.
* ``NO_COLOR`` (any value), a non-tty stream or ``TERM=dumb`` → plain text. ``--json`` never styles.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Mapping, TextIO

from . import i18n

BULLET = "›"
DOT = "·"

# Graphite defaults (themes/graphite.toml, accent «signal») — used when no theme.json is present.
# Semantic colors never reuse the accent (DESIGN §10): warn is yellow, not amber.
_DEFAULTS = {
    "accent": "#ffb547",
    "text": "#ebe8e1",
    "textDim": "#9d9a92",
    "textFaint": "#67655f",
    "ok": "#8fd48a",
    "warn": "#f5cf52",
    "bad": "#ff6b6b",
    "cloud": "#7ad3e6",
}


def _rgb(hexstr: str) -> tuple[int, int, int]:
    h = hexstr.lstrip("#")
    if len(h) == 8:  # #AARRGGBB (theme.json / QML)
        h = h[2:]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _to256(r: int, g: int, b: int) -> int:
    if abs(r - g) < 10 and abs(g - b) < 10:
        if r < 8:
            return 16
        if r > 248:
            return 231
        return 232 + round((r - 8) / 247 * 24)
    q = lambda v: round(v / 255 * 5)  # noqa: E731
    return 16 + 36 * q(r) + 6 * q(g) + q(b)


class Style:
    def __init__(self, stream: TextIO | None = None, env: Mapping[str, str] | None = None,
                 theme_json: str | os.PathLike | None = None, enabled: bool | None = None):
        self.stream = stream or sys.stdout
        env = os.environ if env is None else env
        if enabled is None:
            if "NO_COLOR" in env:
                enabled = False
            elif env.get("FORCE_COLOR") or env.get("CLICOLOR_FORCE"):
                enabled = True
            else:
                enabled = bool(getattr(self.stream, "isatty", lambda: False)()) and env.get("TERM") != "dumb"
        self.enabled = enabled
        self.truecolor = env.get("COLORTERM", "").lower() in ("truecolor", "24bit") or \
            env.get("TERM", "") in ("xterm-kitty", "foot", "foot-extra", "xterm-direct")
        self.palette = dict(_DEFAULTS)
        if theme_json and self.enabled:
            try:
                data = json.loads(open(theme_json, encoding="utf-8").read())
                for k in self.palette:
                    v = data.get(k)
                    if isinstance(v, str) and v.startswith("#"):
                        self.palette[k] = v
            except (OSError, ValueError):
                pass

    def _fg(self, token: str) -> str:
        r, g, b = _rgb(self.palette[token])
        if self.truecolor:
            return f"\x1b[38;2;{r};{g};{b}m"
        return f"\x1b[38;5;{_to256(r, g, b)}m"

    def paint(self, token: str, s: str) -> str:
        if not self.enabled or not s:
            return s
        return f"{self._fg(token)}{s}\x1b[0m"

    def accent(self, s: str) -> str:
        return self.paint("accent", s)

    def dim(self, s: str) -> str:
        return self.paint("textDim", s)

    def faint(self, s: str) -> str:
        return self.paint("textFaint", s)

    def ok(self, s: str) -> str:
        return self.paint("ok", s)

    def warn(self, s: str) -> str:
        return self.paint("warn", s)

    def bad(self, s: str) -> str:
        return self.paint("bad", s)

    def cloud(self, s: str) -> str:
        return self.paint("cloud", s)

    def bold(self, s: str) -> str:
        return f"\x1b[1m{s}\x1b[22m" if self.enabled and s else s

    def swatch(self, hexstr: str | None, width: int = 2) -> str:
        """A small block painted in an arbitrary color (accent previews); empty without color."""
        if not self.enabled or not hexstr:
            return ""
        r, g, b = _rgb(hexstr)
        code = f"\x1b[38;2;{r};{g};{b}m" if self.truecolor else f"\x1b[38;5;{_to256(r, g, b)}m"
        return f"{code}{'█' * width}\x1b[0m"


_style: Style | None = None


def style() -> Style:
    global _style
    if _style is None:
        from .paths import Paths
        _style = Style(theme_json=Paths().theme_json)
    return _style


def set_style(s: Style | None) -> None:
    global _style
    _style = s


def out(line: str = "") -> None:
    st = style()
    print(line, file=st.stream)


def err(line: str) -> None:
    print(line, file=sys.stderr)


def head(text: str) -> None:
    """``› svoya run train.py`` — a heading line with the accent bullet."""
    st = style()
    out(f"{st.accent(BULLET)} {text}")


def kv(label: str, value: str, width: int = 9, indent: int = 2) -> None:
    """``  среда    torch 2.13 · CUDA 13.0`` — dim label, plain value."""
    st = style()
    pad = " " * max(1, width - len(label))
    out(f"{' ' * indent}{st.dim(label)}{pad}{value}")


def columns() -> int:
    """The terminal's width, or 0 when output is not a terminal (then nothing is wrapped)."""
    stream = style().stream
    if not getattr(stream, "isatty", lambda: False)():
        return 0
    import shutil
    return shutil.get_terminal_size((100, 24)).columns


def note(text: str, indent: int = 2) -> None:
    """A faint line; in a narrow terminal it wraps under its own indent instead of at column 0."""
    width = columns()
    lines = [text]
    if width and "\x1b" not in text and indent + len(text) > width:
        import textwrap
        lines = textwrap.wrap(text, width=max(24, width - indent), break_on_hyphens=False) or [text]
    for line in lines:
        out(" " * indent + style().faint(line))


MARKS = {"ok": "✓", "warn": "!", "fail": "×", "skip": "·", "info": "·"}


def mark(status: str) -> str:
    st = style()
    m = MARKS.get(status, "·")
    return {"ok": st.ok, "warn": st.warn, "fail": st.bad}.get(status, st.faint)(m)


def bar(fraction: float, width: int = 25) -> str:
    st = style()
    fraction = min(1.0, max(0.0, fraction))
    full = int(round(fraction * width))
    return st.accent("█" * full) + st.faint("░" * (width - full))


def confirm(question: str, default: bool = False, assume: bool | None = None) -> bool:
    """Ask y/n on a tty; non-interactive runs return ``assume`` (or the default)."""
    if assume is not None:
        return assume
    if not sys.stdin.isatty():
        return default
    hint = i18n.tr("[y/N]", "[д/Н]") if not default else i18n.tr("[Y/n]", "[Д/н]")
    try:
        ans = input(f"{style().accent(BULLET)} {question} {style().faint(hint)} ").strip().lower()
    except EOFError:
        return default
    if not ans:
        return default
    return ans[0] in ("y", "д", "l")  # "l" = "д" typed on a US layout


def print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False))
