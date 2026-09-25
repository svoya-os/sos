"""Load themes, resolve ``auto``, render every template, write ``theme.json``, reload what is running.

Idempotent and cheap: rendering is pure; files are only rewritten when their content changes,
and live-reload hooks (hyprctl, kitty, gsettings) only run for targets that actually changed.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .. import config as config_mod
from ..context import Ctx
from ..paths import Paths
from ..util import atomic_write, iso, read_json, read_text, write_json
from . import accents, engine, solar
from .colors import Color, terminal_palette

MARKER = "svoya:generated"
BACKUP_SUFFIX = ".pre-svoya"
REQUIRED_COLORS = ("wall", "bar", "surface", "surface2", "surface3", "line", "lineStrong", "text",
                   "textDim", "textFaint", "accent", "accentSoft", "accentInk", "ok", "warn", "bad", "cloud")
SECTIONS = ("color", "font", "shape", "motion", "effects")


class ThemeError(Exception):
    pass


@dataclass
class Theme:
    id: str
    mode: str
    pair: str | None
    name: dict
    data: dict
    path: Path
    colors: dict[str, Color] = field(default_factory=dict)

    def label(self, lang: str) -> str:
        return self.name.get(lang) or self.name.get("en") or self.id


def _theme_from_file(path: Path) -> Theme:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ThemeError(f"{path}: {e}") from None
    colors: dict[str, Color] = {}
    for k, v in (data.get("color") or {}).items():
        try:
            colors[k] = Color.parse(str(v))
        except ValueError as e:
            raise ThemeError(f"{path}: color.{k}: {e}") from None
    missing = [k for k in REQUIRED_COLORS if k not in colors]
    if missing:
        raise ThemeError(f"{path}: missing colors: {', '.join(missing)}")
    colors.setdefault("shadow", Color(0, 0, 0, 0.7))
    tid = data.get("id") or path.stem
    mode = data.get("mode", "dark")
    if mode not in ("dark", "light"):
        raise ThemeError(f"{path}: mode must be dark or light")
    return Theme(id=tid, mode=mode, pair=data.get("pair"), name=data.get("name") or {"en": tid},
                 data=data, path=path, colors=colors)


def theme_dirs(paths: Paths) -> list[Path]:
    return [paths.user_themes_dir, paths.themes_dir]


def list_themes(paths: Paths) -> list[Theme]:
    seen: dict[str, Theme] = {}
    for d in theme_dirs(paths):
        for f in sorted(d.glob("*.toml")) if d.is_dir() else []:
            try:
                t = _theme_from_file(f)
            except ThemeError:
                continue
            seen.setdefault(t.id, t)
    return list(seen.values())


def load_theme(paths: Paths, theme_id: str) -> Theme:
    for d in theme_dirs(paths):
        f = d / f"{theme_id}.toml"
        if f.is_file():
            return _theme_from_file(f)
    for t in list_themes(paths):
        if t.id == theme_id:
            return t
    raise ThemeError(f"unknown theme: {theme_id}")


# ---------------------------------------------------------------- auto

def resolve(choice: str, cfg: dict, now: dt.datetime, paths: Paths) -> tuple[str, str]:
    """``auto`` → night theme (graphite) or its day pair (paper) by local sunrise/sunset."""
    if choice != "auto":
        return choice, "explicit"
    tcfg = cfg.get("theme", {})
    night = tcfg.get("night", "graphite")
    day = tcfg.get("day")
    if not day:
        try:
            day = load_theme(paths, night).pair or "paper"
        except ThemeError:
            day = "paper"
    loc = cfg.get("location", {})
    is_day, reason = solar.is_daytime(now, loc.get("latitude"), loc.get("longitude"))
    return (day if is_day else night), reason


def next_switch(now: dt.datetime, cfg: dict) -> dt.datetime | None:
    """Next sunrise/sunset after ``now`` (for timers and the control center)."""
    loc = cfg.get("location", {})
    try:
        lat, lon = float(loc.get("latitude")), float(loc.get("longitude"))
    except (TypeError, ValueError):
        return None
    local = now.astimezone()
    for days in range(0, 3):
        st = solar.sun_times(local.date() + dt.timedelta(days=days), lat, lon)
        for t in (st.sunrise, st.sunset):
            if t and t > now:
                return t
    return None


# ---------------------------------------------------------------- accent

_FROM_CONFIG = object()


def resolve_accent(theme: Theme, cfg: dict, paths: Paths, choice=_FROM_CONFIG) -> accents.Resolved:
    """The accent for this base theme: ``[theme] accent`` (or ``choice``), else the theme's ``accentDefault``."""
    if choice is _FROM_CONFIG:
        choice = (cfg.get("theme") or {}).get("accent")
    return accents.resolve(str(choice) if choice else None, mode=theme.mode, colors=theme.colors,
                           catalog=accents.load_catalog(paths), theme_default=theme.data.get("accentDefault"))


def with_accent(theme: Theme, acc: accents.Resolved) -> Theme:
    """The theme with its four accent tokens replaced by the accent system's."""
    colors = dict(theme.colors)
    colors.update(accent=acc.color, accentSoft=acc.soft, accentStrong=acc.strong, accentInk=acc.ink)
    return dataclasses.replace(theme, colors=colors)


# ---------------------------------------------------------------- rendering

def template_context(theme: Theme, paths: Paths, accent: accents.Resolved | None = None) -> dict:
    d = theme.data
    colors = with_accent(theme, accent).colors if accent is not None else dict(theme.colors)
    colors.setdefault("accentStrong", accents.strong_variant(colors["accent"].with_alpha(1.0), theme.mode))
    acc = accent
    acc_vars = {"id": acc.id, "name": dict(acc.name), "custom": acc.custom or "", "adjusted": acc.adjusted,
                "gnome": acc.gnome} if acc else {"id": "theme", "name": {"en": "Theme", "ru": "Тема"}, "custom": "",
                                                 "adjusted": False, "gnome": accents.gnome_accent(colors["accent"])}
    return {
        "id": theme.id,
        "mode": theme.mode,
        "pair": theme.pair or "",
        "dark": theme.mode == "dark",
        "name": {"en": theme.name.get("en", theme.id), "ru": theme.name.get("ru", theme.name.get("en", theme.id))},
        "color": colors,
        "accent": acc_vars,
        "font": dict(d.get("font") or {"sans": "IBM Plex Sans", "mono": "IBM Plex Mono", "pixel": "Departure Mono"}),
        "shape": dict(d.get("shape") or {}),
        "motion": dict(d.get("motion") or {}),
        "effects": dict(d.get("effects") or {}),
        "term": terminal_palette(colors, theme.mode),
        "icons": "Papirus-Dark" if theme.mode == "dark" else "Papirus-Light",
        "colorScheme": "prefer-dark" if theme.mode == "dark" else "prefer-light",
        "path": {"home": str(paths.home), "config": str(paths.config_home), "state": str(paths.state_home)},
    }


def theme_json(theme: Theme, choice: str, now: dt.datetime, accent: accents.Resolved | None = None) -> dict:
    """Flat JSON of the token keys (ARCHITECTURE §4.1, §8); colors as #AARRGGBB for QML.

    With the accent system: ``accent accentSoft accentStrong accentInk`` come from the resolved accent and
    ``accentId accentNameEn accentNameRu accentCustom accentAdjusted accentContrast`` describe it."""
    if accent is not None:
        theme = with_accent(theme, accent)
    out: dict = {"id": theme.id, "mode": theme.mode, "pair": theme.pair,
                 "nameEn": theme.name.get("en", theme.id), "nameRu": theme.name.get("ru", theme.name.get("en", theme.id)),
                 "choice": choice}
    for k, c in theme.colors.items():
        out[k] = c.hexa
    if "accentStrong" not in out:
        out["accentStrong"] = accents.strong_variant(theme.colors["accent"].with_alpha(1.0), theme.mode).hexa
    if accent is not None:
        out.update({"accentId": accent.id, "accentNameEn": accent.name.get("en", accent.id),
                    "accentNameRu": accent.name.get("ru", accent.name.get("en", accent.id)),
                    "accentCustom": accent.custom, "accentAdjusted": accent.adjusted,
                    "accentContrast": round(accent.contrast, 2)})
    for section in ("font", "shape", "motion", "effects"):
        for k, v in (theme.data.get(section) or {}).items():
            out.setdefault(k, v)
    out["appliedAt"] = iso(now)
    return out


@dataclass
class Target:
    id: str
    template: str
    path: Path
    keep_original: str | None = None
    merge: str | None = None
    reload: str | None = None


def load_manifest(paths: Paths) -> list[Target]:
    tdir = paths.templates_dir
    try:
        data = tomllib.loads((tdir / "manifest.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ThemeError(f"{tdir}/manifest.toml: {e}") from None
    out = []
    for t in data.get("target", []):
        p = t["path"].format(config=paths.config_home, state=paths.state_home, home=paths.home)
        out.append(Target(id=t["id"], template=t["template"], path=Path(p),
                          keep_original=t.get("keep_original"), merge=t.get("merge"), reload=t.get("reload")))
    return out


def _header_end(lines: list[str]) -> int:
    """Index just after the leading comment header of a rendered template."""
    if lines and lines[0].lstrip().startswith("/*"):
        for i, ln in enumerate(lines):
            if "*/" in ln:
                return i + 1
        return 1
    i = 0
    while i < len(lines) and lines[i].lstrip().startswith(("#", "//")):
        i += 1
    return i


def _parse_ini(text: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    sec = ""
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith(("#", ";")):
            continue
        if s.startswith("[") and s.endswith("]"):
            sec = s[1:-1]
            out.setdefault(sec, {})
        elif "=" in s:
            k, v = s.split("=", 1)
            out.setdefault(sec, {})[k.strip()] = v.strip()
    return out


def merge_ini(existing: str, updates: dict[str, dict[str, str]]) -> str:
    """Set ``updates`` inside an INI file, keeping every other line (comments, order, keys)."""
    lines = existing.splitlines()
    out: list[str] = []
    pending = {s: dict(kv) for s, kv in updates.items()}
    sec = ""

    def flush(section: str) -> None:
        for k, v in pending.pop(section, {}).items():
            out.append(f"{k}={v}")

    for ln in lines:
        s = ln.strip()
        if s.startswith("[") and s.endswith("]"):
            while out and not out[-1].strip() and sec in pending:
                out.pop()
            flush(sec)
            if out and out[-1].strip():
                out.append("")
            sec = s[1:-1]
            out.append(ln)
            continue
        if "=" in s and not s.startswith(("#", ";")):
            k = s.split("=", 1)[0].strip()
            if k in pending.get(sec, {}):
                out.append(f"{k}={pending[sec].pop(k)}")
                continue
        out.append(ln)
    flush(sec)
    for section, kv in list(pending.items()):
        if not kv:
            continue
        if out and out[-1].strip():
            out.append("")
        if section:
            out.append(f"[{section}]")
        out.extend(f"{k}={v}" for k, v in kv.items())
    return "\n".join(out).strip("\n") + "\n"


def merge_keyvalue(existing: str, updates: dict[str, str]) -> str:
    """``key = value`` files (btop.conf): replace our keys in place, append missing ones."""
    out: list[str] = []
    pending = dict(updates)
    for ln in existing.splitlines():
        s = ln.strip()
        if "=" in s and not s.startswith("#"):
            k = s.split("=", 1)[0].strip()
            if k in pending:
                out.append(f"{k} = {pending.pop(k)}")
                continue
        out.append(ln)
    out.extend(f"{k} = {v}" for k, v in pending.items())
    return "\n".join(out).strip("\n") + "\n"


def _parse_keyvalue(text: str) -> dict[str, str]:
    out = {}
    for ln in text.splitlines():
        s = ln.strip()
        if "=" in s and not s.startswith("#"):
            k, v = s.split("=", 1)
            out[k.strip()] = v.strip()
    return out


@dataclass
class Result:
    target: Target
    changed: bool
    backup: Path | None = None
    skipped: str | None = None


def render_target(target: Target, ctx_vars: dict, paths: Paths) -> str:
    src = paths.templates_dir / target.template
    try:
        text = src.read_text(encoding="utf-8")
    except OSError as e:
        raise ThemeError(f"template {src}: {e}") from None
    return engine.render(text, ctx_vars, target.template)


def plan_target(target: Target, rendered: str, now: dt.datetime,
                created_by_us: bool = False) -> tuple[str, Path | None, Path | None]:
    """Decide what to write: ``(content, backup_in_use, backup_to_create_now)``.

    * A file without our marker is the user's: it is copied to ``<file>.pre-svoya`` once. If that
      backup already exists and the user wrote yet another file of their own, it is kept too, with a
      timestamp — svoya never destroys a file it did not write.
    * ``keep_original`` targets include the backup so the user's settings survive (ours win).
    * ``merge`` targets are edited in place (only our keys); a merge file svoya created itself
      (``created_by_us``) is never backed up.
    """
    path = target.path
    backup = path.with_name(path.name + BACKUP_SUFFIX)
    existing = read_text(path)
    foreign = existing is not None and bool(existing.strip()) and MARKER not in existing and not created_by_us
    backup_now: Path | None = None
    if foreign:
        if not backup.exists():
            backup_now = backup
        elif target.merge is None and existing != read_text(backup):
            backup_now = path.with_name(f"{path.name}{BACKUP_SUFFIX}-{now.astimezone():%Y%m%d%H%M%S}")
    has_backup = backup.exists() or backup_now == backup
    if target.merge == "ini":
        return merge_ini(existing or "", _parse_ini(rendered)), (backup if has_backup else None), backup_now
    if target.merge == "keyvalue":
        return merge_keyvalue(existing or "", _parse_keyvalue(rendered)), (backup if has_backup else None), backup_now
    if target.keep_original and has_backup:
        lines = rendered.splitlines()
        i = _header_end(lines)
        lines[i:i] = [target.keep_original.format(backup=str(backup))]
        rendered = "\n".join(lines) + "\n"
    return rendered, (backup if has_backup else None), backup_now


def apply_theme(ctx: Ctx, choice: str, *, force: bool = False, only: list[str] | None = None,
                cfg: dict | None = None) -> dict:
    """Render and write everything. Returns a report dict (also used for ``--json``)."""
    cfg = cfg if cfg is not None else config_mod.load(ctx.paths)
    now = ctx.now()
    theme_id, reason = resolve(choice, cfg, now, ctx.paths)
    theme = load_theme(ctx.paths, theme_id)
    acc = resolve_accent(theme, cfg, ctx.paths)
    ctx_vars = template_context(theme, ctx.paths, acc)
    skip = set(cfg.get("theme", {}).get("skip", []) or [])
    created_path = ctx.paths.state_dir / "theme-files.json"
    created = set((read_json(created_path) or {}).get("created", []))
    created_before = set(created)
    results: list[Result] = []
    for target in load_manifest(ctx.paths):
        if only and target.id not in only:
            continue
        if target.id in skip:
            results.append(Result(target, False, skipped="config"))
            continue
        rendered = render_target(target, ctx_vars, ctx.paths)
        content, backup, backup_now = plan_target(target, rendered, now, str(target.path) in created)
        existing = read_text(target.path)
        changed = force or existing != content
        if changed and not ctx.dry_run:
            if backup_now is not None:
                shutil.copy2(target.path, backup_now)
            if existing is None:
                created.add(str(target.path))
            atomic_write(target.path, content)
        results.append(Result(target, changed, backup))
    if created != created_before and not ctx.dry_run:
        write_json(created_path, {"created": sorted(created)})

    tj_path = ctx.paths.theme_json
    old = read_json(tj_path) or {}
    new = theme_json(theme, choice, now, acc)
    mode_changed = old.get("mode") != theme.mode
    accent_changed = (old.get("accent"), old.get("accentId")) != (new["accent"], new["accentId"])
    tj_changed = {k: v for k, v in old.items() if k != "appliedAt"} != {k: v for k, v in new.items() if k != "appliedAt"}
    if (tj_changed or force) and not ctx.dry_run:
        write_json(tj_path, new)

    hooks = run_hooks(ctx, theme, results, mode_changed or force, acc if (accent_changed or force) else None)
    return {"theme": theme.id, "name": dict(theme.name), "choice": choice, "reason": reason, "mode": theme.mode,
            "accent": acc.as_json(), "accentChanged": accent_changed,
            "themeJson": str(tj_path), "themeJsonChanged": tj_changed,
            "targets": [{"id": r.target.id, "path": str(r.target.path), "changed": r.changed,
                         "backup": str(r.backup) if r.backup else None, "skipped": r.skipped} for r in results],
            "hooks": hooks, "dryRun": ctx.dry_run}


def run_hooks(ctx: Ctx, theme: Theme, results: list[Result], mode_changed: bool,
              accent: accents.Resolved | None = None) -> list[str]:
    """Live reloads for what changed. ``accent`` is given when the accent changed (→ GNOME accent-color)."""
    ran: list[str] = []
    changed = {r.target.reload for r in results if r.changed and r.target.reload}
    r = ctx.runner
    if "hyprland" in changed and ctx.env.get("HYPRLAND_INSTANCE_SIGNATURE") and r.which("hyprctl"):
        r.run(["hyprctl", "reload"], timeout=5, mutating=True)
        ran.append("hyprctl reload")
    if "kitty" in changed and r.which("pkill"):
        user = ctx.env.get("USER")
        argv = ["pkill", "-USR1", "-x", "kitty"] + (["-u", user] if user else [])
        r.run(argv, timeout=5, mutating=True)
        ran.append("kitty reload")
    if mode_changed and r.which("gsettings") and (ctx.env.get("DBUS_SESSION_BUS_ADDRESS") or ctx.env.get("WAYLAND_DISPLAY")):
        scheme = "prefer-dark" if theme.mode == "dark" else "prefer-light"
        r.run(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", scheme], timeout=5, mutating=True)
        ran.append(f"gsettings color-scheme {scheme}")
        gtk3 = "adw-gtk3-dark" if theme.mode == "dark" else "adw-gtk3"
        if ctx.exists(f"/usr/share/themes/{gtk3}"):
            r.run(["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", gtk3], timeout=5, mutating=True)
            ran.append(f"gsettings gtk-theme {gtk3}")
        icons = "Papirus-Dark" if theme.mode == "dark" else "Papirus-Light"
        if ctx.exists(f"/usr/share/icons/{icons}"):
            r.run(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", icons], timeout=5, mutating=True)
            ran.append(f"gsettings icon-theme {icons}")
    if accent is not None and r.which("gsettings") and (ctx.env.get("DBUS_SESSION_BUS_ADDRESS") or ctx.env.get("WAYLAND_DISPLAY")):
        # libadwaita ≥ 1.6 / GNOME ≥ 47 (also what the portal tells Flatpak apps): closest named accent
        if r.run(["gsettings", "writable", "org.gnome.desktop.interface", "accent-color"], timeout=5).out.strip() == "true":
            r.run(["gsettings", "set", "org.gnome.desktop.interface", "accent-color", accent.gnome], timeout=5, mutating=True)
            ran.append(f"gsettings accent-color {accent.gnome}")
    return ran
