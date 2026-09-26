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
# `sos apps` and the launcher group the catalog like this (apps.toml: category)
CATEGORIES = (("games", "Games", "Игры"), ("chat", "Chat", "Общение"), ("internet", "Internet", "Интернет"),
              ("office", "Office and study", "Офис и учёба"), ("creative", "Photo, video, sound", "Фото, видео, звук"),
              ("media", "Players", "Плееры"), ("dev", "Code", "Код"), ("system", "System", "Система"))


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


def catalog() -> list[dict]:
    """Each app once (``load_apps`` also maps every alias), in apps.toml order."""
    return [a for k, a in load_apps().items() if k == a["key"]]


def installed_flatpaks(ctx: Ctx) -> set[str]:
    if not ctx.runner.which("flatpak"):
        return set()
    res = ctx.runner.run(["flatpak", "list", "--app", "--columns=application"], timeout=10)
    return {line.strip() for line in res.out.splitlines() if line.strip()} if res.ok else set()


def main_apps(args, ctx: Ctx) -> int:
    """``sos apps``: what one word installs (Flathub, per user, no password), by category."""
    from .i18n import pick
    have = installed_flatpaks(ctx)
    rows = [{"key": a["key"], "id": a["id"], "name": a["name"], "summary": a.get("summary", {}),
             "category": a.get("category", "system"), "license": a.get("license", "?"),
             "proprietary": bool(a.get("proprietary")), "aliases": a.get("aliases", []), "installed": a["id"] in have}
            for a in catalog()]
    if args.json:
        ui.print_json({"apps": rows, "categories": [{"id": c, "name": {"en": en, "ru": ru}} for c, en, ru in CATEGORIES]})
        return 0
    try:
        from .modules import load_state
        gaming = "gaming" in load_state(ctx)["modules"]
    except Exception:
        gaming = False
    st = ui.style()
    ui.head(tr("apps", "приложения") + st.faint(tr(" · sos install <name>: Flathub, just for you, no password",
                                                  " · sos install <имя>: Flathub, только для вас, без пароля")))
    for cid, en, ru in CATEGORIES:
        group = [r for r in rows if r["category"] == cid]
        if not group:
            continue
        ui.out("")
        ui.out("  " + st.bold(tr(en, ru)))
        if cid == "games":
            mark = st.ok("✓") if gaming else st.faint("·")
            ui.out(f"  {mark} {'steam'.ljust(12)} {'Steam'.ljust(16)} "
                   + st.faint(tr("+ GameMode, MangoHud, gamescope (module, asks for the password)",
                                 "+ GameMode, MangoHud, gamescope (модуль, спросит пароль)")))
        for r in group:
            mark = st.ok("✓") if r["installed"] else st.faint("·")
            extra = st.warn(tr(" · proprietary", " · проприетарное")) if r["proprietary"] else ""
            ui.out(f"  {mark} {r['key'].ljust(12)} {r['name'].ljust(16)} {st.faint(pick(r['summary']))}{extra}")
    ui.out("")
    ui.note(tr("sos install telegram · sos remove telegram · an app store: sos install bazaar",
               "sos установить telegram · sos удалить telegram · магазин приложений: sos установить магазин"))
    return 0


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


def _ensure_engine(ctx: Ctx, thing: str, args) -> int:
    """A chat model from the ladder answers through llama.cpp (module llm-local): «установи модель»
    must end with Jackson answering, so the engine comes first when it is missing. 0 = ready."""
    from .models.suggest import resolve as ladder
    if ladder(thing) is None or ctx.runner.which("llama-server"):
        return 0
    try:
        from .modules import load_state
        if "llm-local" in load_state(ctx)["modules"]:
            return 0
    except Exception:  # an unreadable state file: let `modules add` decide
        pass
    ui.note(tr("the model runs on llama.cpp: installing the module llm-local first",
               "модель работает на llama.cpp: сначала ставлю модуль «Локальные модели» (llm-local)"))
    from . import modules
    ns = _ns(modules_cmd="add", modules=["llm-local"], options=[], profile=None, offline=False,
             dry_run=ctx.dry_run, yes=args.yes, json=args.json, force=False, show_scripts=False,
             no_snapshot=False, root_only=False)
    return modules.main(ns, ctx)


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
                engine = _ensure_engine(ctx, obj, args)
                if engine:
                    rc = engine
                    continue
                ns = _ns(models_cmd="pull", repo=obj, files=[], revision="main", include=[], ctx=8192, yes=args.yes,
                         accept_license=False, dry_run=ctx.dry_run, json=args.json)
            else:
                from .models.suggest import resolve as ladder
                c = ladder(obj)
                ns = _ns(models_cmd="rm", target=c.model["repo"] if c else obj, dry_run=ctx.dry_run, yes=args.yes)
            rc = models_cli.main(ns, ctx) or rc
    return rc
