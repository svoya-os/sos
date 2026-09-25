"""Jackson's look on the login screen: ``/etc/svoya/avatar.json`` (design/DESIGN.md §12–§13).

The greeter runs as its own user and cannot read ``~/.config/svoya/avatar.json``. When the user lets
their look go to the login screen («Использовать на экране входа»), ``sos theme … --system`` also
passes Jackson's look across the privilege boundary — as one validated ``key=value;…`` string, never
file contents — and the root side writes a world-readable copy.

The keys and values are those of ``jackson/jackson/avatar.py`` (tests keep the two in sync), plus
``voice``: how Jackson's fixed lines on the login screen sound — ``kent`` (the default persona, «Здоров,
кент!») or ``plain`` (another persona, or humor 0), taken from ``jackson.toml``.
"""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from urllib.parse import quote, unquote

from ..context import Ctx
from ..util import atomic_write

SYSTEM_AVATAR_JSON = "/etc/svoya/avatar.json"

CHARACTERS = ("imp", "cat")
SKINS = {"imp": ("ember", "wine", "plum", "graphite", "mint"),
         "cat": ("blue", "ginger", "black", "snow", "siamese")}
STYLES = ("hoodie", "jacket", "tee")
GLASSES = ("none", "shades", "round")
ACCENT_IDS = ("signal", "amber", "ink", "phosphor", "ice", "lilac", "rose", "mono")
KEYS = ("character", "skin", "outfit", "style", "headphones", "glasses", "hood", "name")
VOICES = ("kent", "plain")
EXPORT_KEYS = KEYS + ("voice",)
JACKSON_TOML = "jackson.toml"
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_MAX_SPEC = 400


def valid_name(name: object) -> bool:
    """The shell's Avatar.validName: 1–24 characters, no control characters or <>, a sensible first one."""
    if not isinstance(name, str):
        return False
    n = name.strip()
    return 0 < len(n) <= 24 and not re.search(r"[\x00-\x1f\x7f<>]", n) and not re.match(r"[\s.'’-]", n)


def clean(data: object) -> dict:
    """Only the known keys with valid values (the rest is dropped, like the shell does)."""
    src = data if isinstance(data, dict) else {}
    out: dict = {}
    character = src.get("character")
    if character in CHARACTERS:
        out["character"] = character
    skin = src.get("skin")
    if isinstance(skin, str) and skin in SKINS[out.get("character", "imp")]:
        out["skin"] = skin
    outfit = src.get("outfit")
    if isinstance(outfit, str) and (outfit == "accent" or outfit in ACCENT_IDS or _HEX.match(outfit)):
        out["outfit"] = outfit.lower()
    if src.get("style") in STYLES:
        out["style"] = src["style"]
    for key in ("headphones", "hood"):
        if isinstance(src.get(key), bool):
            out[key] = src[key]
    if src.get("glasses") in GLASSES:
        out["glasses"] = src["glasses"]
    if valid_name(src.get("name")):
        out["name"] = src["name"].strip()
    return out


def clean_export(data: object) -> dict:
    """The look plus ``voice`` — only ``plain`` is worth saying: the greeter's default is «кент»."""
    out = clean(data)
    if isinstance(data, dict) and data.get("voice") in VOICES and data["voice"] != "kent":
        out["voice"] = data["voice"]
    return out


def encode(data: object) -> str:
    """Look (+ voice) → ``character=cat;skin=snow;…`` (empty when there is nothing to say)."""
    look = clean_export(data)
    parts = []
    for key in EXPORT_KEYS:
        if key not in look:
            continue
        value = look[key]
        if isinstance(value, bool):
            value = "1" if value else "0"
        parts.append(f"{key}={quote(str(value), safe='#')}")
    return ";".join(parts)


def decode(spec: str) -> dict:
    """The root side: strict — anything unexpected is an error, nothing is guessed."""
    if not isinstance(spec, str) or len(spec) > _MAX_SPEC:
        raise ValueError("avatar: too long")
    raw: dict = {}
    for part in filter(None, spec.split(";")):
        key, sep, value = part.partition("=")
        if not sep or key not in EXPORT_KEYS or key in raw:
            raise ValueError(f"avatar: bad entry {part[:40]!r}")
        value = unquote(value)
        if key in ("headphones", "hood"):
            if value not in ("0", "1"):
                raise ValueError(f"avatar: {key} must be 0 or 1")
            raw[key] = value == "1"
        else:
            raw[key] = value
    look = clean(raw)
    if raw.get("voice") in VOICES:
        look["voice"] = raw["voice"]
    if len(look) != len(raw):
        bad = sorted(set(raw) - set(look))
        raise ValueError(f"avatar: invalid value for {', '.join(bad)}")
    return look


def user_look(ctx: Ctx) -> dict:
    """The user's own avatar.json (sparse); {} when missing or unreadable."""
    path: Path = ctx.paths.user_config_dir / "avatar.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return clean(data)


def user_voice(ctx: Ctx) -> str:
    """``kent`` when Jackson talks as «Кентафурик» (persona id ``kent``) with humor on, else ``plain``.

    Read like Jackson reads it: /etc/svoya/jackson.toml, then ~/.config/svoya/jackson.toml on top;
    the defaults (persona kent, humor 1) when neither says.
    """
    data: dict = {}
    for path in (ctx.sys("/etc/svoya/" + JACKSON_TOML), ctx.paths.user_config_dir / JACKSON_TOML):
        try:
            with open(path, "rb") as f:
                data.update(tomllib.load(f))
        except (OSError, tomllib.TOMLDecodeError):
            continue
    persona = data.get("persona", "kent")
    humor = data.get("humor", 1)
    if isinstance(humor, bool) or not isinstance(humor, (int, float)):
        humor = 1
    return "kent" if persona == "kent" and humor > 0 else "plain"


def export_spec(ctx: Ctx) -> str:
    """What ``sos theme … --system`` passes to the root side: the user's look and Jackson's voice."""
    return encode({**user_look(ctx), "voice": user_voice(ctx)})


def write_system_avatar(ctx: Ctx, spec: str) -> str:
    """Root side: ``/etc/svoya/avatar.json`` (0644). An empty spec removes it (the greeter shows the defaults)."""
    look = decode(spec)
    path = ctx.sys(SYSTEM_AVATAR_JSON)
    if ctx.dry_run:
        return str(path)
    if not look:
        path.unlink(missing_ok=True)
        return str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(look, ensure_ascii=False, indent=2) + "\n", mode=0o644)
    return str(path)
