"""``sos doctor [--json] [--fix] [--gpu]`` (also ``sos fix``, ``sos gpu``, ``sos починить``)."""
from __future__ import annotations

import os

from .. import ui
from ..context import Ctx
from ..i18n import lang, tr
from ..runner import svoya_argv
from ..snapshots import Guard
from ..util import atomic_write, iso, write_json
from .checks import Check, recommendation, run_all, write_line
from .facts import SLEEP_HOOK, gather

ORDER = {"fail": 0, "warn": 1, "ok": 2, "skip": 3}


def hook_source(ctx: Ctx) -> str | None:
    p = ctx.paths.modules_dir / "nvidia" / "files" / SLEEP_HOOK
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def diagnose(ctx: Ctx, gpu_only: bool = False) -> tuple[list[Check], dict, object]:
    facts = gather(ctx, gpu_only=gpu_only)
    checks = run_all(facts, hook_source=hook_source(ctx),
                     user_env_path=str(ctx.paths.config_home / "environment.d" / "60-svoya-torch.conf"),
                     zram_generator=ctx.exists("/usr/lib/systemd/system-generators/zram-generator"),
                     gpu_only=gpu_only)
    return checks, recommendation(facts), facts


def summary(checks: list[Check]) -> dict:
    out = {"ok": 0, "warn": 0, "fail": 0, "skip": 0}
    for c in checks:
        out[c.status] = out.get(c.status, 0) + 1
    return out


def report(checks: list[Check], rec: dict, now) -> dict:
    return {"checks": [c.as_json() for c in checks], "summary": summary(checks), "gpu": rec,
            "torchBackend": rec.get("torchBackend"),
            "gpuOk": not any(c.status == "fail" and c.gpu for c in checks), "at": iso(now)}


def _sos_argv(cmd: list[str]) -> list[str]:
    return [*svoya_argv(), *cmd[1:]] if cmd and cmd[0] == "sos" else cmd


def apply_fixes(ctx: Ctx, checks: list[Check], *, root: bool) -> list[str]:
    """Apply the root (``root=True``) or user fixes of ``checks``. Returns human log lines."""
    log: list[str] = []
    for c in checks:
        fx = c.fix
        if fx is None or not fx.safe or fx.root != root:
            continue
        for path, content in (fx.files if root else fx.user_files).items():
            target = ctx.sys(path) if root else __import__("pathlib").Path(os.path.expanduser(path))
            log.append(("· " if ctx.dry_run else "✓ ") + write_line(path))
            if not ctx.dry_run:
                atomic_write(target, content, mode=fx.modes.get(path, 0o644))
        for argv in fx.commands:
            argv = _sos_argv(argv)
            res = ctx.runner.run(argv, timeout=600, mutating=True)
            mark = "· " if ctx.dry_run else ("✓ " if res.ok else "× ")
            log.append(mark + " ".join(argv) + ("" if res.ok else f" — {res.err.strip()[:200]}"))
    return log


def render(checks: list[Check], rec: dict, gpu_only: bool) -> None:
    st = ui.style()
    L = 1 if lang() == "ru" else 0
    title = tr("doctor", "доктор") + (tr(" · GPU", " · видеокарта") if gpu_only else "")
    if rec.get("name"):
        title += st.faint(f" · {rec['name']}" + (f" ({rec['archName']})" if rec.get("archName") else ""))
    ui.head(title)
    for c in sorted(checks, key=lambda c: ORDER[c.status]):
        if c.status == "skip":
            continue
        ui.out(f"  {ui.mark(c.status)} {st.dim(c.title[L].ljust(20))} {c.msg[L]}")
        if c.status in ("warn", "fail") and c.fix:
            for line in c.fix.lines():
                ui.out(" " * 25 + (st.accent("$ ") if not c.fix.safe else st.ok("↻ ")) + st.faint(line))
            if c.fix.note:
                ui.note(c.fix.note[L], indent=25)
    s = summary(checks)
    safe = sum(1 for c in checks if c.status in ("warn", "fail") and c.fix and c.fix.safe)
    tail = f"{s['ok']} ✓ · {s['warn']} ! · {s['fail']} ×"
    if safe:
        tail += st.faint(tr(f"   · `sos fix` applies {safe} safe fix(es) after a snapshot (↻)",
                            f"   · `sos fix` применит безопасные исправления ({safe}) после снимка (↻)"))
    ui.out("")
    ui.out("  " + tail)
    if rec.get("torchBackend"):
        ui.note(f"UV_TORCH_BACKEND={rec['torchBackend']}" + (f" · {' '.join(rec['packages'])}" if rec.get("packages") else ""))


def main(args, ctx: Ctx | None = None) -> int:
    ctx = ctx or Ctx()
    gpu_only = bool(args.gpu)
    checks, rec, _facts = diagnose(ctx, gpu_only)
    rep = report(checks, rec, ctx.now())
    try:
        if not ctx.dry_run:
            write_json(ctx.paths.state_dir / "doctor.json", {k: v for k, v in rep.items() if k != "checks"})
    except OSError:
        pass

    if args.apply_root is not None:                # elevated half of `sos fix` (pkexec re-exec)
        wanted = set(args.apply_root)
        todo = [c for c in checks if c.id in wanted and c.status in ("warn", "fail")]
        with Guard(ctx, "sos: doctor --fix") as g:
            if g.reason:
                ui.note(tr(f"no snapshot: {g.reason}", f"без снимка: {g.reason}"))
            for line in apply_fixes(ctx, todo, root=True):
                ui.note(line)
        return 0

    if not args.fix:
        if args.json:
            ui.print_json(rep)
        else:
            render(checks, rec, gpu_only)
        return 1 if rep["summary"]["fail"] else 0

    # ---- sos fix
    todo = [c for c in checks if c.status in ("warn", "fail") and c.fix and c.fix.safe]
    manual = [c for c in checks if c.status in ("warn", "fail") and c.fix and not c.fix.safe]
    L = 1 if lang() == "ru" else 0
    st = ui.style()
    if args.json and not todo:
        ui.print_json({**rep, "applied": []})
        return 0
    if not todo:
        ui.head(tr("nothing to fix automatically", "автоматически чинить нечего"))
        for c in manual:
            ui.out(f"  {ui.mark(c.status)} {c.title[L]}: {c.msg[L]}")
            for line in c.fix.lines():
                ui.out("      " + st.accent("$ ") + st.faint(line))
        return 0
    if not args.json:
        ui.head(tr("safe fixes (a snapshot is taken first)", "безопасные исправления (сначала снимок)"))
        for c in todo:
            ui.out(f"  {ui.mark(c.status)} {c.title[L]}: {c.msg[L]}")
            for line in c.fix.lines():
                ui.out("      " + st.ok("↻ ") + st.faint(line))
    if not ctx.dry_run and not ui.confirm(tr("Apply?", "Применить?"), default=True, assume=True if args.yes else None):
        return 1
    log = apply_fixes(ctx, todo, root=False)
    root_ids = [c.id for c in todo if c.fix.root]
    if root_ids:
        if ctx.is_root or ctx.dry_run:
            with Guard(ctx, "sos: doctor --fix") as g:
                if g.reason and not args.json:
                    ui.note(tr(f"no snapshot: {g.reason}", f"без снимка: {g.reason}"))
                log += apply_fixes(ctx, todo, root=True)
        else:
            rc = ctx.runner.stream(["pkexec", *svoya_argv(), "doctor", "--fix", "--yes", "--apply-root", *root_ids])
            log.append(tr("elevated fixes: ", "исправления с правами root: ") + ("✓" if rc == 0 else f"× ({rc})"))
    after, rec2, _ = diagnose(ctx, gpu_only)
    if args.json:
        ui.print_json({**report(after, rec2, ctx.now()), "applied": log, "dryRun": ctx.dry_run})
        return 0
    for line in log:
        ui.note(line)
    s = summary(after)
    ui.head(tr("after: ", "после: ") + f"{s['ok']} ✓ · {s['warn']} ! · {s['fail']} ×")
    for c in manual:
        ui.out(f"  {st.accent('$')} {c.title[L]}: " + st.faint("; ".join(c.fix.lines())))
    return 0
