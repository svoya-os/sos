"""``svoya`` — argument parsing and dispatch. Command modules are imported lazily so that the
hot path (``svoya status --json``, polled every 2 s) loads as little Python as possible."""
from __future__ import annotations

import argparse
import os
import sys

from . import __version__, i18n
from .i18n import tr


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="svoya",
        description=tr("Svoya OS system tool: GPU Doctor, modules, models, themes, updates.",
                       "Системный инструмент Svoya OS: доктор ГП, модули, модели, темы, обновления."))
    p.add_argument("--version", action="version", version=f"svoya {__version__}")
    p.add_argument("--no-color", action="store_true", help=tr("plain output", "без цвета"))
    sub = p.add_subparsers(dest="cmd", metavar="<command>")

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
        if verb == "add":
            ma.add_argument("--with", dest="options", action="append", default=[], metavar="OPTION")
            ma.add_argument("--profile")
            ma.add_argument("--offline", action="store_true")
    mp = msub.add_parser("profiles", help=tr("first-run profiles", "профили первого запуска"))
    mp.add_argument("--json", action="store_true")
    mp.add_argument("--offline", action="store_true")

    # models
    mo = cmd("models", "shared model store /srv/ai: fit, licenses, dedup, views",
             "общее хранилище моделей /srv/ai: влезет ли, лицензии, дубликаты, представления")
    mosub = mo.add_subparsers(dest="models_cmd", metavar="<list|pull|fit|rm|dedup|views>")
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
    mop.add_argument("repo", help="org/repo[/file] ")
    mop.add_argument("files", nargs="*")
    mop.add_argument("--revision", default="main")
    mop.add_argument("--include", action="append", default=[])
    mop.add_argument("--ctx", type=int, default=8192)
    mop.add_argument("--yes", "-y", action="store_true")
    mop.add_argument("--accept-license", action="store_true")
    mop.add_argument("--dry-run", action="store_true")
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

    # theme
    t = cmd("theme", "themes: graphite, paper, phosphor, auto", "темы: графит, бумага, фосфор, авто")
    tsub = t.add_subparsers(dest="theme_cmd", metavar="<list|current|apply>")
    tl = tsub.add_parser("list")
    tl.add_argument("--json", action="store_true")
    tc = tsub.add_parser("current")
    tc.add_argument("--json", action="store_true")
    ta = tsub.add_parser("apply")
    ta.add_argument("theme", nargs="?", help="graphite | paper | phosphor | auto")
    ta.add_argument("--dry-run", action="store_true")
    ta.add_argument("--force", action="store_true")
    ta.add_argument("--only", action="append", default=[], metavar="TARGET")
    ta.add_argument("--json", action="store_true")
    ta.add_argument("--quiet", "-q", action="store_true")

    # new
    n = cmd("new", "new AI project (uv) wired to the model store", "новый ИИ-проект (uv), связанный с хранилищем моделей")
    n.add_argument("name")
    n.add_argument("--template", default="torch", choices=["torch", "llm-finetune", "comfy-node", "agent"])
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
    un = cmd("undo", "undo a change svoya made (snapshot pair)", "отменить изменение svoya (пара снимков)")
    un.add_argument("n", nargs="?", type=int, help=tr("pair number from --list (default: latest)",
                                                     "номер пары из --list (по умолчанию последняя)"))
    un.add_argument("--list", action="store_true")
    un.add_argument("--dry-run", action="store_true")
    un.add_argument("--yes", "-y", action="store_true")
    un.add_argument("--json", action="store_true")
    sn = cmd("snapshot", "btrfs snapshots via snapper", "снимки btrfs через snapper")
    snsub = sn.add_subparsers(dest="snapshot_cmd", metavar="<create|list>")
    snc = snsub.add_parser("create")
    snc.add_argument("--description", "-d")
    snc.add_argument("--dry-run", action="store_true")
    snc.add_argument("--json", action="store_true")
    snl = snsub.add_parser("list")
    snl.add_argument("--all", action="store_true")
    snl.add_argument("--json", action="store_true")

    # run / job
    r = cmd("run", "run a script with its environment header and a job for the bar",
            "запустить скрипт с заголовком окружения и задачей для панели")
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
    return p


def main(argv: list[str] | None = None) -> int:
    i18n.set_lang(i18n.detect_lang())
    parser = _parser()
    args = parser.parse_args(argv)
    if args.no_color:
        os.environ["NO_COLOR"] = "1"
    if args.cmd is None:
        parser.print_help()
        return 0
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
        if args.cmd == "theme":
            from .theme import cli as theme_cli
            return theme_cli.main(args, ctx)
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
