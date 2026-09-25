"""``sos theme list | current | apply [<id>|auto]``."""
from __future__ import annotations

from .. import config as config_mod
from .. import i18n, ui
from ..context import Ctx
from ..i18n import tr
from ..util import read_json
from .apply import ThemeError, apply_theme, list_themes, next_switch


def main(args, ctx: Ctx | None = None) -> int:
    ctx = ctx or Ctx()
    cmd = args.theme_cmd or "current"
    cfg = config_mod.load(ctx.paths)
    lang = i18n.lang()
    st = ui.style()

    if cmd == "list":
        themes = list_themes(ctx.paths)
        cur = (read_json(ctx.paths.theme_json) or {}).get("id")
        if args.json:
            ui.print_json([{"id": t.id, "name": t.name, "mode": t.mode, "pair": t.pair,
                            "current": t.id == cur, "path": str(t.path)} for t in themes] +
                          [{"id": "auto", "name": {"en": "Auto", "ru": "Авто"}, "mode": None, "pair": None,
                            "current": False, "path": None}])
            return 0
        ui.head(tr("themes", "темы"))
        for t in themes:
            mark = st.accent("●") if t.id == cur else st.faint("○")
            ui.out(f"  {mark} {t.id.ljust(10)} {t.label(lang).ljust(9)} {st.faint(t.mode)}")
        ui.out(f"  {st.faint('○')} {'auto'.ljust(10)} {tr('Auto', 'Авто').ljust(9)} "
               f"{st.faint(tr('graphite by night, paper by day', 'графит ночью, бумага днём'))}")
        return 0

    if cmd == "current":
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
        if data.get("choice") == "auto":
            nxt = next_switch(ctx.now(), cfg)
            if nxt:
                ui.kv(tr("switch", "смена"), nxt.astimezone().strftime("%H:%M"))
        return 0

    # apply
    choice = args.theme or cfg.get("theme", {}).get("id", "auto")
    try:
        report = apply_theme(ctx, choice, force=args.force, only=args.only or None, cfg=cfg)
    except ThemeError as e:
        ui.err(f"sos: {e}")
        return 2
    if args.theme and not ctx.dry_run and cfg.get("theme", {}).get("id") != args.theme:
        # remember an explicit choice: the auto timer and session start respect it
        from ..config import set_user_value
        try:
            set_user_value(ctx.paths, "theme", "id", args.theme)
        except OSError:
            pass
    if args.json:
        ui.print_json(report)
        return 0
    if args.quiet:
        return 0
    changed = [t for t in report["targets"] if t["changed"]]
    title = (report.get("name") or {}).get(lang) or report["theme"]
    if report["choice"] == "auto":
        why = report["reason"]
        title += st.faint(f"  (auto · {tr('by the sun', 'по солнцу') if why == 'sun' else why})")
    ui.head(tr("theme ", "тема ") + title + (st.faint(tr("  · dry run", "  · пробный запуск")) if ctx.dry_run else ""))
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
    return 0

