"""``sos`` (alias ``svoya``) — argument parsing and dispatch.

Command modules are imported lazily so the hot path (``sos status --json``, polled every 2 s)
loads as little Python as possible. Friendly forms (``sos fix``, ``sos тема ночь``,
``sos установить obsidian``) are rewritten by ``commands.normalize`` before argparse sees them.
"""
from __future__ import annotations

import argparse
import os
import sys

from . import __version__, i18n
from .i18n import tr


# argparse's own words (usage, section titles, -h, errors) in Russian too: it looks `_` up in its
# module globals at call time, so a lookup table is enough (no .mo files).
_ARGPARSE_RU = {
    "usage: ": "использование: ",
    "positional arguments": "аргументы",
    "options": "параметры",
    "show this help message and exit": "показать эту справку",
    "show program's version number and exit": "показать версию",
    "%(prog)s: error: %(message)s\n": "%(prog)s: ошибка: %(message)s\n",
    "invalid choice: %(value)r (choose from %(choices)s)": "нет такого варианта: %(value)r (есть: %(choices)s)",
    "the following arguments are required: %s": "не хватает аргументов: %s",
    "unrecognized arguments: %s": "непонятные аргументы: %s",
    "expected one argument": "нужно одно значение",
    "argument %(argument_name)s: %(message)s": "аргумент %(argument_name)s: %(message)s",
    "invalid %(type)s value: %(value)r": "неверное значение (%(type)s): %(value)r",
}


def _localize_argparse() -> None:
    if i18n.lang() == "ru":
        argparse._ = lambda text: _ARGPARSE_RU.get(text, text)  # type: ignore[attr-defined]


def _parser() -> argparse.ArgumentParser:
    _localize_argparse()
    p = argparse.ArgumentParser(
        prog="sos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=tr("SOS — Svoya Operating System. `sos` alone opens the menu.",
                       "СОС — Своя Операционная Система. Просто `sos` открывает меню."),
        epilog=tr(
            "everyday:\n"
            "  sos install obsidian | llm-local | qwen3.5-9b   install an app, a module or a model\n"
            "  sos remove <thing>                            remove it again\n"
            "  sos fix · sos gpu                             repair · check the graphics card\n"
            "  sos update · sos undo                         update (with a snapshot) · roll back\n"
            "  sos theme night|day|auto · sos accent lilac   theme · accent color (undo: sos undo)\n"
            "  sos ai off | on                               the AI switch\n"
            "  sos models suggest                            the best local model for this machine\n"
            "Russian works too: sos установить, удалить, починить, видеокарта, обновить, откатить, тема, модели.",
            "каждый день:\n"
            "  sos установить obsidian | llm-local | qwen3.5-9b   приложение, модуль или модель\n"
            "  sos удалить <что>                                 удалить обратно\n"
            "  sos починить · sos видеокарта                     починить · проверить видеокарту\n"
            "  sos обновить · sos откатить                       обновить (со снимком) · откатить\n"
            "  sos тема ночь|день|авто · sos акцент сирень       тема · цвет акцента (отменить: sos откатить)\n"
            "  sos ии выкл | вкл                                 выключатель ИИ\n"
            "  sos модели подобрать                              лучшая локальная модель для этой машины\n"
            "По-английски тоже можно: sos install, remove, fix, gpu, update, undo, theme, models."))
    p.add_argument("--version", action="version", version=f"sos {__version__}")
    p.add_argument("--no-color", action="store_true", help=tr("plain output", "без цвета"))
    p._positionals.title = tr("commands", "команды")
    sub = p.add_subparsers(dest="cmd", metavar=tr("<command>", "<команда>"))

    def cmd(name: str, en: str, ru: str, **kw) -> argparse.ArgumentParser:
        return sub.add_parser(name, help=tr(en, ru), description=tr(en, ru), **kw)

    # status
    s = cmd("status", "machine state for the bar (GPU, jobs, updates, snapshots)",
            "состояние машины для панели (ГП, задачи, обновления, снимки)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--write", action="store_true", help=tr("also write ~/.local/state/svoya/status.json",
                                                           "также записать ~/.local/state/svoya/status.json"))
    s.add_argument("--watch", metavar="SEC", type=float,
                   help=tr("print one JSON line every SEC seconds", "печатать строку JSON каждые SEC секунд"))
    s.add_argument("--refresh-cache", action="store_true", help=argparse.SUPPRESS)

    # doctor
    d = cmd("doctor", "GPU Doctor: drivers, CUDA/ROCm, suspend, containers, storage, snapshots",
            "Доктор ГП: драйверы, CUDA/ROCm, сон, контейнеры, диск, снимки")
    d.add_argument("--json", action="store_true")
    d.add_argument("--fix", action="store_true", help=tr("apply safe fixes (snapshot first)",
                                                         "применить безопасные исправления (сначала снимок)"))
    d.add_argument("--gpu", action="store_true", help=tr("GPU checks only", "только проверки ГП"))
    d.add_argument("--dry-run", action="store_true")
    d.add_argument("--yes", "-y", action="store_true")
    d.add_argument("--apply-root", nargs="*", help=argparse.SUPPRESS)

    # modules
    m = cmd("modules", "feature modules: nothing is forced", "модули возможностей: ничего не навязываем")
    msub = m.add_subparsers(dest="modules_cmd", metavar="<list|info|add|remove|profiles>")
    ml = msub.add_parser("list", help=tr("catalog and installed modules", "каталог и установленные модули"))
    ml.add_argument("--json", action="store_true")
    mi = msub.add_parser("info", help=tr("details of one module", "подробности модуля"))
    mi.add_argument("module")
    mi.add_argument("--json", action="store_true")
    mi.add_argument("--show-scripts", action="store_true")
    for verb, en, ru in (("add", "install modules", "установить модули"), ("remove", "remove modules", "удалить модули")):
        ma = msub.add_parser(verb, help=tr(en, ru))
        ma.add_argument("modules", nargs="*")
        ma.add_argument("--dry-run", action="store_true")
        ma.add_argument("--yes", "-y", action="store_true")
        ma.add_argument("--json", action="store_true")
        ma.add_argument("--force", action="store_true")
        ma.add_argument("--show-scripts", action="store_true")
        ma.add_argument("--no-snapshot", action="store_true")
        ma.add_argument("--root-only", action="store_true", help=argparse.SUPPRESS)
        if verb == "add":
            ma.add_argument("--with", dest="options", action="append", default=[], metavar="OPTION")
            ma.add_argument("--profile")
            ma.add_argument("--offline", action="store_true")
    mp = msub.add_parser("profiles", help=tr("first-run profiles", "профили первого запуска"))
    mp.add_argument("--json", action="store_true")
    mp.add_argument("--offline", action="store_true")

    # install / remove (anything: module, app, model)
    ins = cmd("install", "install a module, an app (Flathub) or a model", "установить модуль, приложение (Flathub) или модель")
    ins.add_argument("things", nargs="+", metavar="thing")
    ins.add_argument("--dry-run", action="store_true")
    ins.add_argument("--yes", "-y", action="store_true")
    ins.add_argument("--json", action="store_true")
    rem = cmd("remove", "remove a module, an app or a model", "удалить модуль, приложение или модель")
    rem.add_argument("things", nargs="+", metavar="thing")
    rem.add_argument("--dry-run", action="store_true")
    rem.add_argument("--yes", "-y", action="store_true")
    rem.add_argument("--json", action="store_true")
    cmd("menu", "interactive menu (same as plain `sos`)", "интерактивное меню (как просто `sos`)")

    # models
    mo = cmd("models", "shared model store /srv/ai: fit, licenses, dedup, views",
             "общее хранилище моделей /srv/ai: влезет ли, лицензии, дубликаты, представления")
    mosub = mo.add_subparsers(dest="models_cmd", metavar="<list|suggest|pull|fit|serve|rm|dedup|views>")
    mos = mosub.add_parser("suggest", help=tr("best local model for this machine (+2 alternatives); offers to download it",
                                              "лучшая локальная модель для этой машины (+2 варианта); предложит скачать"))
    mos.add_argument("--json", action="store_true")
    mos.add_argument("--yes", "-y", action="store_true",
                     help=tr("download the suggested model without asking", "скачать предложенную модель без вопроса"))
    mol = mosub.add_parser("list", help=tr("installed models (or --catalog)", "установленные модели (или --catalog)"))
    mol.add_argument("--catalog", action="store_true")
    mol.add_argument("--all", action="store_true", help=tr("include models your region/use may not allow",
                                                           "включая модели, недоступные для вашего региона/использования"))
    mol.add_argument("--kind")
    mol.add_argument("--json", action="store_true")
    mof = mosub.add_parser("fit", help=tr("will it fit my GPU?", "влезет ли в мою видеокарту?"))
    mof.add_argument("model", help="path.gguf | org/repo/file.gguf | https://huggingface.co/...")
    mof.add_argument("--ctx", type=int, default=8192)
    mof.add_argument("--gpu", default="auto", help="auto | <index> | <GiB>")
    mof.add_argument("--kv", default="f16", help="f16 | q8_0 | q4_0 | bf16 | f32")
    mof.add_argument("--no-flash-attn", action="store_true")
    mof.add_argument("--revision", default="main")
    mof.add_argument("--json", action="store_true")
    mop = mosub.add_parser("pull", help=tr("download into the store (HF cache layout)", "скачать в хранилище (формат кэша HF)"))
    mop.add_argument("repo", help="org/repo[/file] | id from `sos models suggest`")
    mop.add_argument("files", nargs="*")
    mop.add_argument("--revision", default="main")
    mop.add_argument("--include", action="append", default=[])
    mop.add_argument("--ctx", type=int, default=8192)
    mop.add_argument("--yes", "-y", action="store_true")
    mop.add_argument("--accept-license", action="store_true")
    mop.add_argument("--dry-run", action="store_true")
    mop.add_argument("--json", action="store_true", help=tr("progress as JSON lines", "прогресс строками JSON"))
    mor = mosub.add_parser("rm", help=tr("remove from the store", "удалить из хранилища"))
    mor.add_argument("target", help="org/repo | path | sha256")
    mor.add_argument("--dry-run", action="store_true")
    mor.add_argument("--yes", "-y", action="store_true")
    mod = mosub.add_parser("dedup", help=tr("find duplicate files; reflink them on btrfs", "найти дубликаты; reflink на btrfs"))
    mod.add_argument("roots", nargs="*")
    mod.add_argument("--apply", action="store_true", help=tr("replace duplicates with reflinks", "заменить дубликаты на reflink"))
    mod.add_argument("--dry-run", action="store_true")
    mod.add_argument("--json", action="store_true")
    mov = mosub.add_parser("views", help=tr("per-tool views: llama.cpp dir, ComfyUI yaml, Ollama imports",
                                            "представления: папка llama.cpp, yaml ComfyUI, импорт в Ollama"))
    mov.add_argument("--out", help=tr("views root (default /srv/ai/views)", "корень представлений (по умолчанию /srv/ai/views)"))
    mov.add_argument("--dry-run", action="store_true")
    mov.add_argument("--json", action="store_true")
    mov.add_argument("--quiet", "-q", action="store_true")
    mse = mosub.add_parser("serve", help=tr("start the local model server (llama.cpp, 127.0.0.1:8080)",
                                            "запустить локальный сервер моделей (llama.cpp, 127.0.0.1:8080)"))
    mse.add_argument("--stop", action="store_true")
    mse.add_argument("--status", action="store_true")
    mse.add_argument("--foreground", action="store_true")
    mse.add_argument("--port", type=int, default=8080)
    mse.add_argument("--json", action="store_true")
    mse.add_argument("--dry-run", action="store_true")

    # theme
    t = cmd("theme", "themes (graphite, paper, phosphor, auto) and the accent color",
            "темы (графит, бумага, фосфор, авто) и цвет акцента")
    tsub = t.add_subparsers(dest="theme_cmd", metavar="<list|current|apply|accent|accents>")
    tl = tsub.add_parser("list", help=tr("base themes", "базовые темы"))
    tl.add_argument("--json", action="store_true")
    tc = tsub.add_parser("current", help=tr("what is applied now", "что применено сейчас"))
    tc.add_argument("--json", action="store_true")
    ta = tsub.add_parser("apply", help=tr("switch the base theme (or re-apply)", "сменить базовую тему (или применить снова)"))
    ta.add_argument("theme", nargs="?", help="graphite | paper | phosphor | auto")
    ta.add_argument("--dry-run", action="store_true")
    ta.add_argument("--force", action="store_true")
    ta.add_argument("--only", action="append", default=[], metavar="TARGET")
    ta.add_argument("--system", action="store_true", help=tr("also the login screen (asks for the admin password)",
                                                             "и на экране входа (спросит пароль администратора)"))
    ta.add_argument("--json", action="store_true")
    ta.add_argument("--quiet", "-q", action="store_true")
    tac = tsub.add_parser("accent", help=tr("accent color: signal amber ink phosphor ice lilac rose mono or #hex",
                                            "цвет акцента: сигнал янтарь чернила фосфор лёд сирень роза моно или #hex"))
    tac.add_argument("value", nargs="*", help=tr("id, name (RU/EN), color word or #rrggbb; `default` resets",
                                                 "id, имя, цвет словом или #rrggbb; `default` — по умолчанию"))
    tac.add_argument("--undo", action="store_true", help=tr("back to the previous look", "вернуть предыдущий вид"))
    tac.add_argument("--system", action="store_true", help=tr("also the login screen (asks for the admin password)",
                                                              "и на экране входа (спросит пароль администратора)"))
    tac.add_argument("--dry-run", action="store_true")
    tac.add_argument("--json", action="store_true")
    tas = tsub.add_parser("accents", help=tr("all accent colors", "все цвета акцента"))
    tas.add_argument("--json", action="store_true")
    tsw = tsub.add_parser("system-write")                  # root half of --system (pkexec); ids only
    tsw.add_argument("--theme", dest="theme_id", required=True)
    tsw.add_argument("--accent", required=True)
    tsw.add_argument("--avatar", default=None)          # Jackson's look, key=value;… (validated again)
    tsw.add_argument("--dry-run", action="store_true")
    tsw.add_argument("--quiet", "-q", action="store_true")

    # ai
    ai = cmd("ai", "the AI switch: Jackson, local model servers, agents", "выключатель ИИ: Джексон, локальные модели, агенты")
    aisub = ai.add_subparsers(dest="ai_cmd", metavar="<off|on|status>")
    for name, en, ru in (("off", "stop Jackson and local model servers; keep them off", "остановить Джексона и локальные модели"),
                         ("on", "allow AI again and start Jackson", "снова разрешить ИИ и запустить Джексона"),
                         ("status", "is AI on? what is running?", "включён ли ИИ и что запущено")):
        ap = aisub.add_parser(name, help=tr(en, ru))
        ap.add_argument("--json", action="store_true")
        if name != "status":
            ap.add_argument("--system", action="store_true", help=tr("for every user of this computer (admin password)",
                                                                     "для всех пользователей (пароль администратора)"))
            ap.add_argument("--dry-run", action="store_true")
            ap.add_argument("--root-only", action="store_true", help=argparse.SUPPRESS)

    # new
    n = cmd("new", "new AI project (uv) wired to the model store", "новый ИИ-проект (uv), связанный с хранилищем моделей")
    n.add_argument("name")
    n.add_argument("--template", default="torch", choices=["torch", "llm-finetune", "comfy-node", "agent", "upsil"])
    n.add_argument("--dir", help=tr("parent directory (default: current)", "родительская папка (по умолчанию текущая)"))
    n.add_argument("--no-git", action="store_true")
    n.add_argument("--dry-run", action="store_true")
    n.add_argument("--json", action="store_true")

    # update / undo / snapshot
    u = cmd("update", "update the system (snapshot first)", "обновить систему (сначала снимок)")
    u.add_argument("--dry-run", action="store_true")
    u.add_argument("--yes", "-y", action="store_true")
    u.add_argument("--json", action="store_true")
    u.add_argument("--no-flatpak", action="store_true")
    un = cmd("undo", "undo the latest change (look, or a system change via its snapshot pair)",
             "отменить последнее изменение (вид или системное — по паре снимков)")
    un.add_argument("n", nargs="?", metavar="id", help=tr("id from --list: a snapshot number or look-N (default: the latest change)",
                                                         "id из --list: номер снимка или look-N (по умолчанию последнее изменение)"))
    un.add_argument("--list", action="store_true")
    un.add_argument("--dry-run", action="store_true")
    un.add_argument("--yes", "-y", action="store_true")
    un.add_argument("--json", action="store_true")
    un.add_argument("--config", default="root", help=tr("snapper config (root, home…)", "конфигурация snapper (root, home…)"))
    sn = cmd("snapshot", "btrfs snapshots via snapper", "снимки btrfs через snapper")
    snsub = sn.add_subparsers(dest="snapshot_cmd", metavar="<create|list>")
    snc = snsub.add_parser("create")
    snc.add_argument("--description", "--reason", "-d", dest="description")
    snc.add_argument("--config", default="root", help=tr("snapper config (root, home…)", "конфигурация snapper (root, home…)"))
    snc.add_argument("--dry-run", action="store_true")
    snc.add_argument("--json", action="store_true")
    snl = snsub.add_parser("list")
    snl.add_argument("--all", action="store_true")
    snl.add_argument("--config", default="root")
    snl.add_argument("--json", action="store_true")

    # run / job
    r = cmd("run", "run a script (.py, .sh, UpsiL .upl) with its environment header and a job for the bar",
            "запустить скрипт (.py, .sh, UpsiL .upl) с заголовком окружения и задачей для панели")
    r.add_argument("--label")
    r.add_argument("--no-job", action="store_true")
    r.add_argument("--no-header", action="store_true")
    r.add_argument("script")
    r.add_argument("args", nargs=argparse.REMAINDER)
    j = cmd("job", "report job progress to the bar", "сообщить прогресс задачи панели")
    jsub = j.add_subparsers(dest="job_cmd", metavar="<progress|list|done|start>")
    jp = jsub.add_parser("progress")
    jp.add_argument("id")
    jp.add_argument("progress", type=float)
    jp.add_argument("--eta", type=int)
    jp.add_argument("--message")
    jp.add_argument("--label")
    jd = jsub.add_parser("done")
    jd.add_argument("id")
    jd.add_argument("--exit-code", type=int, default=0)
    js = jsub.add_parser("start")
    js.add_argument("label")
    js.add_argument("--pid", type=int)
    jlist = jsub.add_parser("list")
    jlist.add_argument("--json", action="store_true")
    jlist.add_argument("--all", action="store_true")

    ss = cmd("session-start", "start the desktop session (Hyprland exec-once)", "запуск сеанса (exec-once в Hyprland)")
    ss.add_argument("--dry-run", action="store_true")
    ss.add_argument("--json", action="store_true")
    # plumbing, not for people: works, but stays out of `sos --help`
    sub._choices_actions = [a for a in sub._choices_actions if a.dest != "session-start"]
    return p


def main(argv: list[str] | None = None) -> int:
    i18n.set_lang(i18n.detect_lang())
    argv = list(sys.argv[1:] if argv is None else argv)
    from . import commands
    if argv[:1] == ["__complete"]:
        for w in commands.complete(argv[1:] or [""]):
            print(w)
        return 0
    flags = [a for a in argv if a in ("--no-color",)]
    rest = [a for a in argv if a not in flags]
    rest = commands.normalize(rest)
    argv = flags + rest
    first = next((a for a in rest if not a.startswith("-")), None)
    if first is not None and first not in commands.COMMANDS and not rest[0].startswith("-"):
        hints = commands.suggest(first)
        msg = tr(f"sos: unknown command '{first}'.", f"sos: неизвестная команда «{first}».")
        if hints:
            msg += " " + tr("Did you mean: ", "Может быть: ") + ", ".join(hints) + "?"
        print(msg, file=sys.stderr)
        print(tr("  sos help — all commands · sos — menu", "  sos help — все команды · sos — меню"), file=sys.stderr)
        return 2
    parser = _parser()
    args = parser.parse_args(argv)
    if args.no_color:
        os.environ["NO_COLOR"] = "1"
    if args.cmd is None:
        parser.print_help()
        return 0
    if args.cmd == "menu":
        from . import menu
        return menu.main()
    dry = bool(getattr(args, "dry_run", False))
    from . import ui
    from .context import make
    ctx = make(dry_run=dry, echo=(lambda line: ui.note("$ " + line)) if dry and not getattr(args, "json", False) else None)
    try:
        if args.cmd == "status":
            from . import status
            return status.main(args, ctx)
        if args.cmd == "doctor":
            from .doctor import cli as doctor_cli
            return doctor_cli.main(args, ctx)
        if args.cmd == "modules":
            from . import modules
            return modules.main(args, ctx)
        if args.cmd == "models":
            from .models import cli as models_cli
            return models_cli.main(args, ctx)
        if args.cmd in ("install", "remove"):
            from . import install
            return install.main(args, ctx)
        if args.cmd == "theme":
            from .theme import cli as theme_cli
            return theme_cli.main(args, ctx)
        if args.cmd == "ai":
            from . import ai
            return ai.main(args, ctx)
        if args.cmd == "new":
            from . import new
            return new.main(args, ctx)
        if args.cmd == "update":
            from . import update
            return update.main_update(args, ctx)
        if args.cmd == "undo":
            from . import update
            return update.main_undo(args, ctx)
        if args.cmd == "snapshot":
            from . import snapshots
            if not args.snapshot_cmd:
                args.snapshot_cmd, args.all, args.json = "list", False, False
            return snapshots.main(args, ctx)
        if args.cmd == "run":
            from . import run
            return run.main(args, ctx)
        if args.cmd == "job":
            from . import run
            return run.main_job(args, ctx)
        if args.cmd == "session-start":
            from . import session
            return session.main(args, ctx)
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
