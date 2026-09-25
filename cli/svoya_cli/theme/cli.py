"""``sos theme list | current | apply [<id>|auto] | accent [<id|#hex|name>] | accents``."""
from __future__ import annotations

import difflib

from .. import config as config_mod
from .. import i18n, ui
from ..context import Ctx
from ..i18n import tr
from ..util import read_json
from . import accents
from . import look
from .apply import ThemeError, list_themes, load_theme, next_switch, resolve, resolve_accent


def _name(d: dict | None, fallback: str = "") -> str:
    return i18n.pick(d, fallback) if d else fallback


def _accent_label(acc: dict) -> str:
    """«Сирень» / «#7f00ff» — how an accent is called in one-line confirmations."""
    return acc["custom"] if acc.get("custom") else _name(acc.get("name"), acc.get("id", ""))


def _current(ctx: Ctx, cfg: dict):
    """(theme, resolved accent) for what is configured right now."""
    theme_id, _ = resolve(str(cfg.get("theme", {}).get("id", "auto")), cfg, ctx.now(), ctx.paths)
    theme = load_theme(ctx.paths, theme_id)
    return theme, resolve_accent(theme, cfg, ctx.paths)


def _undo_hint() -> str:
    return tr(" · undo: sos undo", " · отменить: sos undo")


def _system_note(res: dict | None) -> str:
    if not res:
        return ""
    return ui.style().faint(tr(" · login screen too", " · и на экране входа")) if res.get("ok") else ""


def _system_error(res: dict | None) -> None:
    if res and not res.get("ok"):
        ui.err(tr(f"sos: the login screen was not changed: {res.get('error', '')}",
                  f"sos: экран входа не изменён: {res.get('error', '')}"))


def _unknown_accent(text: str, catalog: accents.Catalog, err: accents.AccentError) -> int:
    ids = list(catalog.accents) or ["signal", "amber", "ink", "phosphor", "ice", "lilac", "rose", "mono"]
    if err.hint:
        a = catalog.get(err.hint)
        alt = f"{err.hint} ({_name(a.name, err.hint)})" if a else err.hint
        ui.err(tr(f"sos: red is reserved for errors — try {alt} or your own '#hex'",
                  f"sos: красный занят ошибками — попробуйте {alt} или свой '#hex'"))
        return 2
    names = {}
    for a in catalog.accents.values():
        for n in a.name.values():
            names[str(n).lower()] = a.id
    close = difflib.get_close_matches(text.lower(), ids + list(names), n=2, cutoff=0.6)
    hint = (tr(" Did you mean: ", " Может быть: ") + ", ".join(close) + "?") if close else ""
    ui.err(tr(f"sos: unknown accent '{text}'.{hint}", f"sos: неизвестный акцент «{text}».{hint}"))
    ui.err(tr(f"  accents: {', '.join(ids)} — or '#rrggbb' (sos theme accents)",
              f"  акценты: {', '.join(ids)} — или '#rrggbb' (sos theme accents)"))
    return 2


def cmd_list(args, ctx: Ctx, cfg: dict) -> int:
    lang = i18n.lang()
    st = ui.style()
    themes = list_themes(ctx.paths)
    cur = (read_json(ctx.paths.theme_json) or {}).get("id")
    if args.json:
        ui.print_json([{"id": t.id, "name": t.name, "mode": t.mode, "pair": t.pair,
                        "accentDefault": t.data.get("accentDefault"),
                        "current": t.id == cur, "path": str(t.path)} for t in themes] +
                      [{"id": "auto", "name": {"en": "Auto", "ru": "Авто"}, "mode": None, "pair": None,
                        "accentDefault": None, "current": False, "path": None}])
        return 0
    ui.head(tr("themes", "темы"))
    for t in themes:
        mark = "●" if t.id == cur else st.faint("○")          # selected = text, never the accent (DESIGN §11)
        ui.out(f"  {mark} {t.id.ljust(10)} {t.label(lang).ljust(9)} {st.faint(t.mode)}")
    ui.out(f"  {st.faint('○')} {'auto'.ljust(10)} {tr('Auto', 'Авто').ljust(9)} "
           f"{st.faint(tr('graphite by night, paper by day', 'графит ночью, бумага днём'))}")
    ui.note(tr("accent colors: sos theme accents", "цвет акцента: sos theme accents"))
    return 0


def cmd_current(args, ctx: Ctx, cfg: dict) -> int:
    lang = i18n.lang()
    st = ui.style()
    data = read_json(ctx.paths.theme_json)
    if args.json:
        ui.print_json(data or {})
        return 0
    if not data:
        ui.head(tr("no theme applied yet — run `sos theme apply auto`",
                   "тема ещё не применялась — `sos theme apply auto`"))
        return 0
    name = data.get("nameRu" if lang == "ru" else "nameEn") or data.get("id")
    ui.head(f"{name} {st.faint('(' + data.get('id', '') + ')')}")
    ui.kv(tr("choice", "выбор"), data.get("choice", "—"))
    ui.kv(tr("mode", "режим"), data.get("mode", "—"))
    if data.get("accentId"):
        acc_name = data.get("accentCustom") or data.get("accentNameRu" if lang == "ru" else "accentNameEn")
        color = "#" + str(data.get("accent", ""))[-6:]
        ui.kv(tr("accent", "акцент"), " ".join(x for x in (st.swatch(color), acc_name, st.faint(color)) if x))
    if data.get("choice") == "auto":
        nxt = next_switch(ctx.now(), cfg)
        if nxt:
            ui.kv(tr("switch", "смена"), nxt.astimezone().strftime("%H:%M"))
    return 0


def cmd_accents(args, ctx: Ctx, cfg: dict) -> int:
    st = ui.style()
    catalog = accents.load_catalog(ctx.paths)
    try:
        theme, acc = _current(ctx, cfg)
    except ThemeError as e:
        ui.err(f"sos: {e}")
        return 2
    surfaces = {"dark": theme.colors["surface"], "light": theme.colors["surface"]}
    for tid in (theme.pair, "graphite", "paper"):
        try:
            t = load_theme(ctx.paths, tid) if tid else None
        except ThemeError:
            t = None
        if t is not None and t.mode != theme.mode:
            surfaces[t.mode] = t.colors["surface"]
            break
    rows = accents.listing(catalog, acc.id, acc.custom, surfaces)
    if args.json:
        ui.print_json(rows)
        return 0
    ui.head(tr("accents", "акценты") + st.faint(tr(f"  · now {_accent_label(acc.as_json())}",
                                                   f"  · сейчас {_accent_label(acc.as_json())}")))
    for r in rows:
        mark = "●" if r["current"] else st.faint("○")
        label = _name(r["name"], r["id"]).ljust(9)
        if r["id"] == "custom":
            detail = (" ".join(x for x in (st.swatch(r["dark"]), r["custom"]) if x) if r.get("custom") else
                      st.faint(tr("sos theme accent '#rrggbb'", "sos theme accent '#rrggbb'")))
            ui.out(f"  {mark} {'custom'.ljust(9)} {label} {detail}")
            continue
        colors = "  ".join(" ".join(x for x in (st.swatch(r[m]), st.faint(r[m])) if x) for m in ("dark", "light"))
        note = st.faint("  " + _name(r["note"])) if r.get("note") else ""
        ui.out(f"  {mark} {r['id'].ljust(9)} {label} {colors}{note}")
    ui.note(tr("sos theme accent <name> · Russian names work too: сирень, лёд…",
               "sos theme accent <имя> · можно по-русски: сирень, лёд…"))
    return 0


def cmd_accent(args, ctx: Ctx, cfg: dict) -> int:
    st = ui.style()
    if args.undo:
        return _undo(args, ctx, cfg)
    text = " ".join(args.value or []).strip()
    if not text:                                            # `sos theme accent`: what is it now?
        try:
            _, acc = _current(ctx, cfg)
        except ThemeError as e:
            ui.err(f"sos: {e}")
            return 2
        if args.json:
            ui.print_json(acc.as_json())
            return 0
        ui.head(" ".join(x for x in (tr("accent", "акцент"), st.swatch(acc.color.hex), _accent_label(acc.as_json()),
                                     st.faint(acc.color.hex)) if x))
        ui.note(tr("change it: sos theme accent <name|#hex> · all: sos theme accents",
                   "сменить: sos theme accent <имя|#hex> · все: sos theme accents"))
        return 0
    catalog = accents.load_catalog(ctx.paths)
    try:
        choice = accents.parse_choice(text, catalog)
        if choice and not choice.startswith("#") and catalog.accents and choice not in catalog.accents:
            raise accents.AccentError(f"unknown accent: {text}")
        if choice and not choice.startswith("#") and not catalog.accents:
            raise accents.AccentError(f"no accents installed ({accents.accents_path(ctx.paths)})")
    except accents.AccentError as e:
        if args.json:
            ui.print_json({"ok": False, "error": str(e), "hint": e.hint})
            return 2
        return _unknown_accent(text, catalog, e)
    try:
        res = look.change(ctx, cfg, accent=choice, set_accent=True, system=args.system)
    except ThemeError as e:
        ui.err(f"sos: {e}")
        return 2
    acc = res["report"]["accent"]
    if args.json:
        ui.print_json({"ok": True, "accent": acc, "changed": res["changed"], "visible": res["visible"],
                       "previous": res["previous"], "undo": res["undo"], "system": res["system"],
                       "theme": res["report"]["theme"], "dryRun": ctx.dry_run})
        return 0 if not res["system"] or res["system"].get("ok") else 1
    label = _accent_label(acc)
    sw = st.swatch(acc["color"])
    if not res["visible"] and not ctx.dry_run:
        ui.head(tr(f"accent is already {label}", f"акцент уже {label}") + _system_note(res["system"]))
        _system_error(res["system"])
        return 0
    line = tr("accent ", "акцент ") + (f"{sw} " if sw else "")
    if acc["custom"] and acc["adjusted"]:
        ratio = i18n.num(acc["contrast"], 1)
        direction = tr("lighter", "светлее") if res["report"]["mode"] == "dark" else tr("darker", "темнее")
        line += f"{acc['custom']} → {acc['color']} " + st.faint(
            tr(f"({direction} for readability, {ratio}:1)", f"({direction} — для читаемости, {ratio}:1)"))
    else:
        line += label
    if ctx.dry_run:
        line += st.faint(tr("  · dry run", "  · пробный запуск"))
    else:
        line += st.faint(_undo_hint()) + _system_note(res["system"])
    ui.head(line)
    if acc.get("clash"):
        word = {"ok": tr("«all good»", "«всё хорошо»"), "warn": tr("warnings", "предупреждений"),
                "bad": tr("errors", "ошибок"), "cloud": tr("the cloud", "облака")}.get(acc["clash"], acc["clash"])
        ui.note(tr(f"close to the color of {word} — icons and words still tell them apart",
                   f"похож на цвет {word} — значки и слова всё равно их различат"))
    _system_error(res["system"])
    return 0 if not res["system"] or res["system"].get("ok") else 1


def _undo(args, ctx: Ctx, cfg: dict) -> int:
    try:
        res = look.undo(ctx, cfg)
    except ThemeError as e:
        ui.err(f"sos: {e}")
        return 2
    if res is None:
        if args.json:
            ui.print_json({"ok": True, "undone": None})
        else:
            ui.head(tr("nothing to undo", "отменять нечего"))
        return 0
    return print_undone(res, as_json=args.json)


def print_undone(res: dict, as_json: bool = False) -> int:
    """One calm line after a look undo (also used by `sos undo`)."""
    rep, entry = res["report"], res["entry"]
    if as_json:
        ui.print_json({"ok": True, "undone": entry["id"], "description": entry.get("description"),
                       "accent": rep["accent"], "theme": rep["theme"], "system": res["system"]})
        return 0 if not res["system"] or res["system"].get("ok") else 1
    what = _name(entry.get("description"), entry["id"])
    theme = _name(rep.get("name"), rep["theme"])
    if rep.get("choice") == "auto":
        theme = tr("Auto", "Авто") + f" ({theme})"
    now = tr(f"now {theme} · accent {_accent_label(rep['accent'])}",
             f"сейчас {theme} · акцент {_accent_label(rep['accent'])}")
    ui.head(tr(f"undone: {what}", f"отменено: {what}") + ui.style().faint(f" · {now}") + _system_note(res["system"]))
    _system_error(res["system"])
    return 0 if not res["system"] or res["system"].get("ok") else 1


def cmd_apply(args, ctx: Ctx, cfg: dict) -> int:
    lang = i18n.lang()
    st = ui.style()
    try:
        if args.theme:
            res = look.change(ctx, cfg, theme=args.theme, system=args.system)
            report = res["report"]
        else:
            from .apply import apply_theme
            choice = cfg.get("theme", {}).get("id", "auto")
            report = apply_theme(ctx, choice, force=args.force, only=args.only or None, cfg=cfg)
            res = {"undo": None, "system": look.system_write(ctx, report["theme"], cfg.get("theme", {}).get("accent"))
                   if args.system else None}
    except ThemeError as e:
        ui.err(f"sos: {e}")
        return 2
    if args.json:
        ui.print_json({**report, "undo": res["undo"], "system": res["system"]})
        return 0
    if args.quiet:
        _system_error(res["system"])
        return 0
    changed = [t for t in report["targets"] if t["changed"]]
    title = (report.get("name") or {}).get(lang) or report["theme"]
    if report["choice"] == "auto":
        why = report["reason"]
        title += st.faint(f"  (auto · {tr('by the sun', 'по солнцу') if why == 'sun' else why})")
    ui.head(tr("theme ", "тема ") + title + (st.faint(tr("  · dry run", "  · пробный запуск")) if ctx.dry_run else "")
            + (st.faint(_undo_hint()) if res["undo"] else "") + _system_note(res["system"]))
    for t in report["targets"]:
        if t["skipped"]:
            ui.kv(t["id"], st.faint(tr("skipped (config)", "пропущено (настройки)")), width=14)
        elif t["changed"]:
            extra = st.faint(tr(" · your original kept: ", " · ваш файл сохранён: ") + t["backup"]) if t["backup"] else ""
            ui.kv(t["id"], t["path"] + extra, width=14)
    if not changed:
        ui.note(tr("everything already up to date", "всё уже применено"))
    for h in report["hooks"]:
        ui.note(f"↻ {h}")
    fb = (report.get("accent") or {}).get("fallback")
    if fb:
        ui.note(tr(f"[theme] accent in svoya.toml: {fb} — using {_accent_label(report['accent'])}",
                   f"[theme] accent в svoya.toml: {fb} — используется {_accent_label(report['accent'])}"))
    _system_error(res["system"])
    return 0


def cmd_system_write(args, ctx: Ctx) -> int:
    """Root half of ``--system``: re-derive the look from system files and write /etc/svoya/theme.json."""
    if not ctx.is_root:
        ui.err(tr("sos: this step runs as root — use `sos theme accent … --system`",
                  "sos: этот шаг выполняется от root — используйте `sos theme accent … --system`"))
        return 2
    try:
        path = look.write_system_theme(ctx, args.theme_id, args.accent)
    except (ThemeError, accents.AccentError, OSError) as e:
        ui.err(f"sos: {e}")
        return 2
    if not args.quiet:
        ui.note(tr(f"login screen: {path}", f"экран входа: {path}"))
    return 0


def main(args, ctx: Ctx | None = None) -> int:
    ctx = ctx or Ctx()
    cmd = args.theme_cmd or "current"
    if cmd == "system-write":
        return cmd_system_write(args, ctx)
    cfg = config_mod.load(ctx.paths)
    return {"list": cmd_list, "current": cmd_current, "accents": cmd_accents, "accent": cmd_accent,
            "apply": cmd_apply}[cmd](args, ctx, cfg)
