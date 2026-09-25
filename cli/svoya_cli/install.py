"""``sos install <thing>`` / ``sos remove <thing>`` — one verb for modules, apps and models.

Resolution order (first hit wins): module id or alias (``obsidian`` → module ``notes``) → app alias
(``data/apps.toml`` → Flathub, per user) → local model id from ``sos models suggest``
(``qwen3.5-9b``) → Hugging Face repo (``org/repo[/file.gguf]``). Unknown names get suggestions.
"""
from __future__ import annotations

import argparse
import difflib
import re
import tomllib
from pathlib import Path

from . import ui
from .context import Ctx
from .i18n import tr

FLATHUB = "https://dl.flathub.org/repo/flathub.flatpakrepo"


def load_apps(data_dir: Path | None = None) -> dict[str, dict]:
    base = data_dir or Path(__file__).resolve().parent / "data"
    with open(base / "apps.toml", "rb") as f:
        apps = tomllib.load(f).get("app", {})
    out = {}
    for key, a in apps.items():
        a = dict(a, key=key)
        out[key] = a
        for al in a.get("aliases", []):
            out.setdefault(al.lower(), a)
    return out


def resolve(ctx: Ctx, thing: str) -> tuple[str, object] | None:
    from .modules import find, load_catalog
    t = thing.strip()
    m = find(load_catalog(ctx.paths.modules_dir), t)
    if m is not None:
        return "module", m
    apps = load_apps()
    if t.lower() in apps:
        return "app", apps[t.lower()]
    from .models.suggest import resolve as ladder
    c = ladder(t)
    if c is not None:
        return "model", t
    if re.fullmatch(r"(hf://)?[A-Za-z0-9][\w.-]*/[\w.-]+(/.+)?", t) or t.startswith("https://huggingface.co/"):
        return "model", t
    return None


def _candidates(ctx: Ctx) -> list[str]:
    from .commands import _ladder_ids, _module_ids
    return _module_ids() + sorted(load_apps()) + _ladder_ids()


def _ns(**kw) -> argparse.Namespace:
    return argparse.Namespace(**kw)


def install_app(ctx: Ctx, app: dict, args) -> int:
    st = ui.style()
    ui.head(f"{app['name']} {st.faint('· Flathub · ' + app['id'])}")
    ui.kv(tr("license", "лицензия"), app.get("license", "?") + (st.warn(tr("  proprietary", "  проприетарная")) if app.get("proprietary") else ""), width=11)
    cmds = [["flatpak", "remote-add", "--user", "--if-not-exists", "flathub", FLATHUB],
            ["flatpak", "install", "--user", "-y", "--noninteractive", "flathub", app["id"]]]
    if ctx.dry_run:
        for c in cmds:
            ui.note("$ " + " ".join(c))
        return 0
    if not ctx.runner.which("flatpak"):
        ui.err(tr("sos: flatpak is missing — `sos install notes` sets it up (or apt install flatpak)",
                  "sos: нет flatpak — его поставит `sos install notes` (или apt install flatpak)"))
        return 2
    if not ui.confirm(tr("Install?", "Установить?"), default=not app.get("proprietary"), assume=True if args.yes else None):
        return 1
    for c in cmds:
        rc = ctx.runner.stream(c)
        if rc != 0:
            return rc
    ui.head(tr("installed · remove with: sos remove ", "установлено · удалить: sos remove ") + app["key"])
    return 0


def remove_app(ctx: Ctx, app: dict, args) -> int:
    c = ["flatpak", "uninstall", "--user", "-y", "--noninteractive", app["id"]]
    if ctx.dry_run:
        ui.note("$ " + " ".join(c))
        return 0
    if not ui.confirm(tr(f"Remove {app['name']}?", f"Удалить {app['name']}?"), assume=True if args.yes else None):
        return 1
    return ctx.runner.stream(c)


def main(args, ctx: Ctx) -> int:
    rc = 0
    verb = args.cmd
    for thing in args.things:
        hit = resolve(ctx, thing)
        if hit is None:
            close = difflib.get_close_matches(thing.lower(), _candidates(ctx), n=4, cutoff=0.55)
            ui.err(tr(f"sos: don't know '{thing}'", f"sos: не знаю «{thing}»") +
                   (tr(". Did you mean: ", ". Может быть: ") + ", ".join(close) + "?" if close else
                    tr(" — see `sos modules list` or `sos models suggest`", " — см. `sos modules list` или `sos models suggest`")))
            rc = 2
            continue
        kind, obj = hit
        if kind == "module":
            from . import modules
            ns = _ns(modules_cmd="add" if verb == "install" else "remove", modules=[obj["id"]], options=[],
                     profile=None, offline=False, dry_run=ctx.dry_run, yes=args.yes, json=args.json, force=False,
                     show_scripts=False, no_snapshot=False, root_only=False)
            rc = modules.main(ns, ctx) or rc
        elif kind == "app":
            rc = (install_app if verb == "install" else remove_app)(ctx, obj, args) or rc
        else:
            from .models import cli as models_cli
            if verb == "install":
                ns = _ns(models_cmd="pull", repo=obj, files=[], revision="main", include=[], ctx=8192, yes=args.yes,
                         accept_license=False, dry_run=ctx.dry_run, json=args.json)
            else:
                from .models.suggest import resolve as ladder
                c = ladder(obj)
                ns = _ns(models_cmd="rm", target=c.model["repo"] if c else obj, dry_run=ctx.dry_run, yes=args.yes)
            rc = models_cli.main(ns, ctx) or rc
    return rc
