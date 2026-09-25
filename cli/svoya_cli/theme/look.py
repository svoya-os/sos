"""The user's look — base theme + accent — as one undoable, persisted choice.

``change()`` renders everything with the new choice, then remembers it in ``~/.config/svoya/svoya.toml``
(``[theme] id`` / ``[theme] accent``) and in the undo journal (``sos undo`` / ``sos theme accent --undo``).
``system_write()`` puts the same look into ``/etc/svoya/theme.json`` for the login screen: as root
directly, otherwise through ``pkexec sos theme system-write --theme <id> --accent <id|#hex|default>
--avatar <key=value;…>`` — only ids, a validated hex and Jackson's validated look cross the privilege
boundary, never file contents (``avatar_export``: the greeter shows the user's Jackson).
"""
from __future__ import annotations

from pathlib import Path

import copy
import re

from .. import config as config_mod
from .. import journal
from ..context import Ctx
from ..runner import svoya_argv
from ..util import atomic_write
from . import accents, avatar_export
from .apply import ThemeError, _theme_from_file, apply_theme, resolve_accent, theme_json

KIND = "look"
DEFAULT_THEME = "auto"
SYSTEM_THEME_JSON = "/etc/svoya/theme.json"
_THEME_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def state(ctx: Ctx) -> dict:
    """What the user has set (their own file only): ``{"theme": id|None, "accent": id|#hex|None}``."""
    return {"theme": config_mod.user_value(ctx.paths, "theme", "id"),
            "accent": config_mod.user_value(ctx.paths, "theme", "accent")}


def persist(ctx: Ctx, st: dict) -> None:
    for key, cfg_key in (("theme", "id"), ("accent", "accent")):
        if st.get(key) is None:
            config_mod.unset_user_value(ctx.paths, "theme", cfg_key)
        else:
            config_mod.set_user_value(ctx.paths, "theme", cfg_key, st[key])


def describe(theme_report: dict | None, acc: dict | None, what: str) -> dict:
    """Journal/toast wording: {"en": "accent Lilac", "ru": "акцент Сирень"}."""
    if what == "accent" and acc:
        if acc.get("custom"):
            return {"en": f"accent {acc['custom']}", "ru": f"акцент {acc['custom']}"}
        n = acc.get("name") or {}
        return {"en": f"accent {n.get('en', acc.get('id'))}", "ru": f"акцент {n.get('ru', n.get('en', acc.get('id')))}"}
    n = (theme_report or {}).get("name") or {}
    tid = (theme_report or {}).get("theme", "")
    if (theme_report or {}).get("choice") == "auto":
        return {"en": "theme Auto", "ru": "тема Авто"}
    return {"en": f"theme {n.get('en', tid)}", "ru": f"тема {n.get('ru', n.get('en', tid))}"}


def change(ctx: Ctx, cfg: dict, *, theme: str | None = None, accent: str | None = None,
           set_accent: bool = False, system: bool = False, record: bool = True) -> dict:
    """Apply a new look and remember it. ``theme`` None = keep; ``set_accent`` with ``accent`` None =
    back to the theme's default accent. Returns ``{"report", "changed", "undo", "previous", "system"}``."""
    before = state(ctx)
    after = dict(before)
    if theme is not None:
        after["theme"] = theme
    if set_accent:
        after["accent"] = accent
    new_cfg = copy.deepcopy(cfg)
    th = new_cfg.setdefault("theme", {})
    if theme is not None:
        th["id"] = theme
    if set_accent:
        if accent is None:
            th.pop("accent", None)
            sys_accent = config_mod.system_value(ctx.paths, "theme", "accent")
            if sys_accent:
                th["accent"] = sys_accent
        else:
            th["accent"] = accent
    choice = str(th.get("id") or DEFAULT_THEME)
    report = apply_theme(ctx, choice, cfg=new_cfg)
    visible = report["themeJsonChanged"] or any(t["changed"] for t in report["targets"]) or report["accentChanged"]
    eff = lambda st: (st.get("theme") or DEFAULT_THEME, st.get("accent"))  # noqa: E731
    changed = eff(before) != eff(after)
    entry = None
    if not ctx.dry_run and changed:
        persist(ctx, after)
        if record and visible:
            what = "accent" if set_accent and theme is None else "theme"
            entry = journal.push(ctx.paths, KIND, before=before, after=after,
                                 description=describe(report, report["accent"], what), now=ctx.now(), system=system)
    sys_res = None
    if system:
        sys_res = system_write(ctx, report["theme"], after.get("accent") if set_accent else th.get("accent"))
    return {"report": report, "changed": changed, "visible": bool(visible), "undo": entry["id"] if entry else None,
            "previous": before, "system": sys_res}


def undo(ctx: Ctx, cfg: dict, entry_id: str | None = None) -> dict | None:
    """Revert one journal entry (default: the newest look change). None when there is nothing to undo."""
    entry = journal.find(ctx.paths, entry_id) if entry_id else next(
        (e for e in reversed(journal.entries(ctx.paths)) if e.get("kind") == KIND), None)
    if entry is None or entry.get("kind") != KIND:
        return None
    before = entry.get("before") or {}
    new_cfg = copy.deepcopy(cfg)
    th = new_cfg.setdefault("theme", {})
    th["id"] = before.get("theme") or config_mod.system_value(ctx.paths, "theme", "id") or DEFAULT_THEME
    th.pop("accent", None)
    restored = before.get("accent") or config_mod.system_value(ctx.paths, "theme", "accent")
    if restored:
        th["accent"] = restored
    report = apply_theme(ctx, str(th["id"]), cfg=new_cfg)
    if not ctx.dry_run:
        persist(ctx, {"theme": before.get("theme"), "accent": before.get("accent")})
        journal.remove(ctx.paths, entry["id"])
    sys_res = system_write(ctx, report["theme"], th.get("accent")) if entry.get("system") else None
    return {"entry": entry, "report": report, "system": sys_res}


# ---------------------------------------------------------------- login screen (/etc/svoya/theme.json)

def system_write(ctx: Ctx, theme_id: str, accent: str | None) -> dict:
    """Write the login screen's theme.json: directly as root, else ``pkexec sos theme system-write``."""
    acc_arg = accent or "default"
    avatar_spec = avatar_export.encode(avatar_export.user_look(ctx))
    if ctx.is_root:
        try:
            path = write_system_theme(ctx, theme_id, acc_arg)
            avatar_export.write_system_avatar(ctx, avatar_spec)
            return {"ok": True, "path": path}
        except (ThemeError, accents.AccentError, ValueError, OSError) as e:
            return {"ok": False, "error": str(e)}
    if not ctx.runner.which("pkexec"):
        return {"ok": False, "error": "pkexec is not installed"}
    helper = "/usr/lib/svoya/theme-system-write"      # polkit action org.svoya.theme.system-write (no password)
    head = [helper] if ctx.runner.which(helper) or Path(helper).exists() else [*svoya_argv(), "theme", "system-write"]
    res = ctx.runner.run(["pkexec", *head, "--theme", theme_id, "--accent", acc_arg, "--avatar", avatar_spec],
                         timeout=300, mutating=True)
    return {"ok": res.ok, "path": SYSTEM_THEME_JSON, **({} if res.ok else {"error": (res.err or res.out).strip()[:300] or f"exit {res.rc}"})}


def write_system_theme(ctx: Ctx, theme_id: str, accent: str) -> str:
    """Root side. Everything is re-derived from system files; the caller only names a theme and an accent."""
    if not _THEME_ID.match(theme_id or ""):
        raise ThemeError(f"bad theme id: {theme_id!r}")
    catalog = accents.load_catalog(ctx.paths)
    choice = None if accent in ("", "default") else accents.parse_choice(accent, catalog)
    if choice and not choice.startswith("#") and catalog.accents and choice not in catalog.accents:
        raise accents.AccentError(f"unknown accent: {accent}")
    sysdir = ctx.paths.themes_dir                       # system themes only: never the user's directory
    f = sysdir / f"{theme_id}.toml"
    theme = _theme_from_file(f) if f.is_file() else _theme_from_file(sysdir / "graphite.toml")
    if theme.mode == "light":                           # the greeter is dark and neutral (DESIGN §12)
        pair = sysdir / f"{theme.pair}.toml" if theme.pair and _THEME_ID.match(theme.pair) else None
        theme = _theme_from_file(pair) if pair and pair.is_file() else _theme_from_file(sysdir / "graphite.toml")
        if theme.mode == "light":
            theme = _theme_from_file(sysdir / "graphite.toml")
    acc = resolve_accent(theme, {}, ctx.paths, choice=choice)
    data = theme_json(theme, "system", ctx.now(), acc)
    path = ctx.sys(SYSTEM_THEME_JSON)
    if not ctx.dry_run:
        import json
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n", mode=0o644)
    return str(path)
