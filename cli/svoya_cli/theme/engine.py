"""A tiny, safe template engine: substitution and filters only — no code, no loops, no includes.

Syntax::

    {{ color.accent }}                    → #ffb547   (opaque colors print as #rrggbb, others #aarrggbb)
    {{ color.accent | hex }}              → #ffb547
    {{ color.accentSoft | hexa }}         → #24ffb547 (ARGB, Qt/QML)
    {{ color.accent | rgb }}              → 255,181,71
    {{ color.accent | rgba(0.5) }}        → rgba(255,181,71,0.5)
    {{ color.accent | strip }}            → ffb547
    {{ color.accentSoft | stripa }}       → ffb54724  (alpha last: fuzzel, Hyprland rgba())
    {{ color.accent | ansi }}             → 38;2;255;181;71
    {{ color.accent | mix(color.surface, 0.7) | hex }}   blend toward another color
    {{ color.text | lighten(0.1) }}  {{ color.text | darken(0.1) }}  {{ color.accent | opacity(0.3) | hexa }}
    {{ color.accentSoft | over(color.surface) | hex }}   flatten a translucent color
    {{ font.mono | json }}   {{ name.ru | upper }}   {{ effects.grain | round(2) }}

Unknown variables and filters are errors (with template name and line), never silent blanks.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

from .colors import Color

_TAG = re.compile(r"\{\{(.*?)\}\}", re.S)
_TOK = re.compile(r"""
    \s*(?:
      (?P<num>-?\d+(?:\.\d+)?)
    | (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
    | (?P<path>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)
    | (?P<sym>[|(),])
    )""", re.X)


class TemplateError(Exception):
    pass


def _color(v: Any, fname: str) -> Color:
    if isinstance(v, Color):
        return v
    if isinstance(v, str):
        return Color.parse(v)
    raise TemplateError(f"filter '{fname}' needs a color, got {type(v).__name__}")


FILTERS: dict[str, Callable[..., Any]] = {
    "hex": lambda v: _color(v, "hex").hex,
    "hexa": lambda v: _color(v, "hexa").hexa,
    "rgb": lambda v: _color(v, "rgb").rgb,
    "rgba": lambda v, a=None: _color(v, "rgba").rgba(a),
    "strip": lambda v: _color(v, "strip").strip,
    "stripa": lambda v: _color(v, "stripa").stripa,
    "ansi": lambda v: _color(v, "ansi").ansi,
    "alpha": lambda v: round(_color(v, "alpha").a, 3),
    "mix": lambda v, other, t: _color(v, "mix").mix(_color(other, "mix"), float(t)),
    "over": lambda v, bg: _color(v, "over").over(_color(bg, "over")),
    "lighten": lambda v, x: _color(v, "lighten").lighten(float(x)),
    "darken": lambda v, x: _color(v, "darken").darken(float(x)),
    "opacity": lambda v, a: _color(v, "opacity").with_alpha(float(a)),
    "json": lambda v: json.dumps(v, ensure_ascii=False),
    "upper": lambda v: str(v).upper(),
    "lower": lambda v: str(v).lower(),
    "round": lambda v, n=0: round(float(v), int(n)) if int(n) else int(round(float(v))),
}


def _to_str(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        s = repr(v)
        return s[:-2] if s.endswith(".0") else s
    if isinstance(v, Color):
        return str(v)
    if v is None:
        raise TemplateError("value is null")
    return str(v)


def _lookup(path: str, ctx: dict) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(path)
    return cur


class _Parser:
    def __init__(self, expr: str, ctx: dict, where: str):
        self.toks: list[tuple[str, str]] = []
        pos = 0
        expr = expr.strip()
        while pos < len(expr):
            m = _TOK.match(expr, pos)
            if not m or m.end() == pos:
                raise TemplateError(f"{where}: cannot parse {expr!r}")
            kind = m.lastgroup or ""
            self.toks.append((kind, m.group(kind)))
            pos = m.end()
            while pos < len(expr) and expr[pos].isspace():
                pos += 1
        self.i = 0
        self.ctx = ctx
        self.where = where

    def peek(self) -> tuple[str, str] | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self) -> tuple[str, str]:
        t = self.peek()
        if t is None:
            raise TemplateError(f"{self.where}: unexpected end of expression")
        self.i += 1
        return t

    def value(self) -> Any:
        kind, text = self.take()
        if kind == "num":
            return float(text) if "." in text else int(text)
        if kind == "str":
            return json.loads(text) if text[0] == '"' else text[1:-1]
        if kind == "path":
            try:
                return _lookup(text, self.ctx)
            except KeyError:
                raise TemplateError(f"{self.where}: unknown variable '{text}'") from None
        raise TemplateError(f"{self.where}: unexpected '{text}'")

    def parse(self) -> Any:
        v = self.value()
        while self.peek() is not None:
            kind, text = self.take()
            if (kind, text) != ("sym", "|"):
                raise TemplateError(f"{self.where}: expected '|', got '{text}'")
            fkind, fname = self.take()
            if fkind != "path" or fname not in FILTERS:
                raise TemplateError(f"{self.where}: unknown filter '{fname}'")
            args: list[Any] = []
            if self.peek() == ("sym", "("):
                self.take()
                if self.peek() != ("sym", ")"):
                    while True:
                        args.append(self.value())
                        t = self.take()
                        if t == ("sym", ")"):
                            break
                        if t != ("sym", ","):
                            raise TemplateError(f"{self.where}: expected ',' or ')'")
                else:
                    self.take()
            try:
                v = FILTERS[fname](v, *args)
            except TemplateError:
                raise
            except (TypeError, ValueError) as e:
                raise TemplateError(f"{self.where}: filter '{fname}': {e}") from None
        return v


def render(text: str, ctx: dict, name: str = "<template>") -> str:
    def repl(m: re.Match) -> str:
        line = text.count("\n", 0, m.start()) + 1
        return _to_str(_Parser(m.group(1), ctx, f"{name}:{line}").parse())
    return _TAG.sub(repl, text)


def variables(text: str) -> list[str]:
    """Variable paths referenced by a template (for docs/tests)."""
    out = []
    for m in _TAG.finditer(text):
        for tm in _TOK.finditer(m.group(1)):
            if tm.lastgroup == "path" and tm.group("path") not in FILTERS:
                out.append(tm.group("path"))
    return out
