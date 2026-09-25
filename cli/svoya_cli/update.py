"""``sos update [--dry-run]`` and ``sos undo [--list|<n>]`` — snapper pre/post pairs around apt.

update: apt-get update → simulate (plan) → pre snapshot → dist-upgrade (+ flatpak) → post snapshot →
verify the NVIDIA module exists for the newest kernel → human summary with the undo command.
undo:   ``snapper undochange pre..post`` of a pair svoya created — itself wrapped in a snapshot pair,
so an undo can be undone too.
"""
from __future__ import annotations

import os
import re

from . import i18n, ui
from .context import Ctx
from .i18n import tr
from .runner import svoya_argv
from .snapshots import Guard, Snapper

APT_ENV = {"DEBIAN_FRONTEND": "noninteractive", "LC_ALL": "C", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"}
APT_OPTS = ["-o", "Dpkg::Options::=--force-confdef", "-o", "Dpkg::Options::=--force-confold"]


def parse_simulation(text: str) -> dict:
    """``apt-get -s dist-upgrade`` → packages, removals, kernel and NVIDIA changes."""
    pkgs, removed = [], []
    for line in text.splitlines():
        m = re.match(r"^Inst (\S+)(?: \[([^\]]+)\])? \((\S+) ([^\[]*?)(?: \[[^\]]+\])?\)", line)
        if m:
            name, old, new, origin = m.group(1), m.group(2), m.group(3), m.group(4).strip()
            pkgs.append({"name": name, "old": old, "new": new, "origin": origin, "security": "-security" in origin})
            continue
        m = re.match(r"^Remv (\S+)(?: \[([^\]]+)\])?", line)
        if m:
            removed.append(m.group(1))
    kernels = sorted({re.sub(r"^linux-image-(unsigned-)?", "", p["name"]) for p in pkgs
                      if re.match(r"^linux-image-(unsigned-)?\d", p["name"])})
    nvidia = [p["name"] for p in pkgs if "nvidia" in p["name"]]
    return {"packages": pkgs, "removed": removed, "count": len(pkgs), "security": sum(p["security"] for p in pkgs),
            "kernels": kernels, "nvidia": nvidia}


def _elevate(args_list: list[str]) -> int:
    os.execvp("pkexec", ["pkexec", *svoya_argv(), *args_list])
    return 126  # not reached


def verify_nvidia(ctx: Ctx) -> dict:
    """After an upgrade: is there an NVIDIA module for the newest kernel? (doctor rule nvidia.kernel)"""
    from .doctor.checks import check_module_match
    from .doctor.facts import gather
    f = gather(ctx, gpu_only=True)
    c = check_module_match(f)
    return {"status": c.status, "message": {"en": c.msg[0], "ru": c.msg[1]},
            "fix": c.fix.lines() if c.fix else None, "kernel": f.kernels[-1] if f.kernels else None}


def main_update(args, ctx: Ctx | None = None) -> int:
    ctx = ctx or Ctx()
    if not ctx.dry_run and not ctx.is_root:
        return _elevate(["update", *(["--yes"] if args.yes else []), *(["--json"] if args.json else []),
                         *(["--no-flatpak"] if args.no_flatpak else [])])
    r = ctx.runner
    st = ui.style()
    if not r.which("apt-get"):
        ui.err(tr("sos: apt-get not found", "sos: apt-get не найден"))
        return 2
    if not ctx.dry_run:
        r.stream(["apt-get", "update"], env=APT_ENV)
    sim = r.run(["apt-get", "-s", "-o", "Debug::NoLocking=1", "dist-upgrade"], timeout=300, env=APT_ENV)
    if not sim.ok:
        ui.err(f"sos: apt-get -s failed: {sim.err.strip()[:300]}")
        return 1
    plan = parse_simulation(sim.out)
    flatpak = r.which("flatpak") is not None and not args.no_flatpak
    if args.json and ctx.dry_run:
        ui.print_json({"plan": plan, "flatpak": flatpak, "dryRun": True})
        return 0
    ui.head(tr("update", "обновление") + st.faint(f" · {i18n.count(plan['count'], 'package', 'packages', 'пакет', 'пакета', 'пакетов')}"
                                               + (tr(f" · {plan['security']} security", f" · {plan['security']} безопасности") if plan["security"] else "")))
    if plan["kernels"]:
        ui.kv(tr("kernel", "ядро"), ", ".join(plan["kernels"]), width=10)
    if plan["nvidia"]:
        ui.kv("nvidia", ", ".join(plan["nvidia"][:6]) + (" …" if len(plan["nvidia"]) > 6 else ""), width=10)
    if plan["removed"]:
        ui.kv(tr("removes", "удалит"), st.warn(", ".join(plan["removed"][:10])), width=10)
    if ctx.dry_run:
        ui.note(tr("dry run: package lists were not refreshed; nothing changed",
                   "пробный запуск: списки пакетов не обновлялись, ничего не изменено"))
        for c in (["apt-get", "update"], ["apt-get", "-y", *APT_OPTS, "dist-upgrade"]):
            ui.note("$ " + " ".join(c))
        return 0
    if plan["count"] == 0 and not flatpak:
        ui.note(tr("everything is up to date", "всё уже обновлено"))
        return 0
    if not ui.confirm(tr("Update now?", "Обновить сейчас?"), default=True, assume=True if args.yes else None):
        return 1
    with Guard(ctx, f"sos: update ({plan['count']} packages)") as g:
        if g.reason:
            ui.note(tr(f"no snapshot: {g.reason}", f"без снимка: {g.reason}"))
        rc = r.stream(["apt-get", "-y", *APT_OPTS, "dist-upgrade"], env=APT_ENV)
        if flatpak:
            r.stream(["flatpak", "update", "-y", "--noninteractive"])
    check = verify_nvidia(ctx)
    L = 1 if i18n.lang() == "ru" else 0
    reboot = ctx.exists("/var/run/reboot-required") or ctx.exists("/run/reboot-required")
    res = {"ok": rc == 0, "plan": plan, "snapshot": {"pre": g.pre, "post": g.post}, "nvidia": check, "reboot": reboot}
    if args.json:
        ui.print_json(res)
        return 0 if rc == 0 else rc
    ui.head((tr("updated", "обновлено") if rc == 0 else st.bad(tr("update failed", "обновление не удалось")))
            + st.faint(f" · {i18n.count(plan['count'], 'package', 'packages', 'пакет', 'пакета', 'пакетов')}"))
    if g.pre is not None:
        ui.kv(tr("snapshot", "снимок"), f"#{g.pre}…#{g.post}  " + st.faint(tr(f"undo: sos undo {g.pre}", f"откат: sos undo {g.pre}")), width=10)
    if check["status"] in ("fail", "warn"):
        ui.kv("nvidia", st.bad(check["message"]["ru" if L else "en"]), width=10)
        for line in check["fix"] or []:
            ui.note("$ sudo " + line if not line.startswith("sos") else "$ " + line, indent=12)
    elif check["status"] == "ok":
        ui.kv("nvidia", st.ok("✓ ") + check["message"]["ru" if L else "en"], width=10)
    if reboot:
        ui.note(tr("reboot to use the new kernel/driver", "перезагрузитесь, чтобы включить новое ядро/драйвер"))
    return 0 if rc == 0 else rc


def undo_targets(sn: Snapper) -> list[dict]:
    """What can be undone, newest last: sos pre/post pairs and single sos snapshots (Jackson's)."""
    snaps = sn.list()
    posts = {s.pre_number: s for s in snaps if s.type == "post" and s.pre_number}
    out = []
    for s in snaps:
        if not s.is_svoya:
            continue
        if s.type == "pre":
            post = posts.get(s.number)
            out.append({"n": s.number, "pre": s.number, "post": post.number if post else None, "to": post.number if post else 0,
                        "date": s.as_json()["date"], "description": s.description, "kind": "pair"})
        elif s.type == "single":
            out.append({"n": s.number, "pre": s.number, "post": None, "to": 0, "date": s.as_json()["date"],
                        "description": s.description, "kind": "single"})
    return sorted(out, key=lambda t: t["n"])


def _snapshot_number(ident) -> int | None:
    """``7``, ``"7"``, ``"#7"``, ``"snap-7"`` → 7; anything else → None."""
    if ident is None or isinstance(ident, bool):
        return None
    if isinstance(ident, int):
        return ident
    t = str(ident).strip().lstrip("#")
    t = t[5:] if t.startswith("snap-") else t
    return int(t) if t.isdigit() else None


def _look_rows(ctx: Ctx) -> list[dict]:
    """Look changes (theme, accent) from the user's undo journal, in the ``--list`` row shape."""
    from . import journal
    return [{"id": e["id"], "n": None, "pre": None, "post": None, "to": None, "date": e.get("at"),
             "description": i18n.pick(e.get("description"), e["id"]), "kind": e.get("kind", "look")}
            for e in journal.entries(ctx.paths)]


def _undo_look(args, ctx: Ctx, entry_id: str) -> int:
    from . import config as config_mod
    from .theme import cli as theme_cli
    from .theme import look
    from .theme.apply import ThemeError
    try:
        res = look.undo(ctx, config_mod.load(ctx.paths), entry_id)
    except ThemeError as e:
        ui.err(f"sos: {e}")
        return 2
    if res is None:
        ui.err(tr(f"sos: no change {entry_id} — see `sos undo --list`", f"sos: нет изменения {entry_id} — см. `sos undo --list`"))
        return 2
    return theme_cli.print_undone(res, as_json=bool(getattr(args, "json", False)))


def main_undo(args, ctx: Ctx | None = None) -> int:
    """``sos undo``: the newest change — a look change from the journal (no snapshot, no password) or an
    sos snapshot pair (``snapper undochange``). ``sos undo <n>`` / ``sos undo look-3`` pick one."""
    import sys
    from . import journal
    ctx = ctx or Ctx()
    ident = getattr(args, "n", None)
    num = _snapshot_number(ident)
    if ident is not None and num is None:
        if journal.is_id(str(ident)) and journal.find(ctx.paths, str(ident)):
            return _undo_look(args, ctx, str(ident))
        ui.err(tr(f"sos: no change {ident} — see `sos undo --list`", f"sos: нет изменения {ident} — см. `sos undo --list`"))
        return 2
    sn = Snapper(ctx, getattr(args, "config", None) or "root")
    st = ui.style()
    available = sn.available()
    looks = _look_rows(ctx) if num is None else []
    targets = undo_targets(sn) if available else []
    for t in targets:
        t.setdefault("id", str(t["n"]))
    if args.list or (args.json and ident is None and not args.yes):
        rows = sorted(targets + looks, key=lambda t: t.get("date") or "")
        if args.json:
            ui.print_json(rows)
            return 0
        ui.head(tr("changes you can undo", "изменения, которые можно отменить"))
        if not rows:
            ui.note(tr("none yet", "пока нет"))
        for t in reversed(rows[-20:]):
            when = t["date"][5:16].replace("T", " ") if t["date"] else "—"
            state = st.warn(tr("  (incomplete)", "  (не завершено)")) if t["kind"] == "pair" and t["post"] is None else ""
            ui.out(f"  {st.accent(str(t['id']).rjust(7))}  {st.dim(when)}  {t['description']}{state}")
        if not available:
            ui.note(tr(f"system changes: {sn.why_unavailable()}", f"системные изменения: {sn.why_unavailable()}"))
        ui.note(tr("sos undo <id>", "sos undo <id>"))
        return 0
    if num is None and looks:
        newest_snap = targets[-1]["date"] if targets else None
        if not newest_snap or (looks[-1]["date"] or "") >= newest_snap:
            return _undo_look(args, ctx, looks[-1]["id"])
    if not available:
        ui.err(tr(f"sos: undo needs btrfs snapshots — {sn.why_unavailable()}", f"sos: для отката нужны снимки btrfs — {sn.why_unavailable()}"))
        return 2
    if not targets and num is None:
        ui.head(tr("nothing to undo", "отменять нечего"))
        return 0
    if num is None:
        chosen = targets[-1]
    else:
        chosen = next((t for t in targets if num in (t["pre"], t["post"])), None)
        if chosen is None:          # any snapshot id (e.g. one Jackson created with another tool)
            snap = next((x for x in sn.list() if x.number == num), None)
            chosen = {"n": num, "pre": num, "to": 0, "description": snap.description if snap else "", "kind": "single"} if snap else None
    if chosen is None:
        ui.err(tr(f"sos: no change #{num} — see `sos undo --list`", f"sos: нет изменения №{num} — см. `sos undo --list`"))
        return 2
    pre, to = chosen["pre"], chosen["to"]
    changes = sn.status(pre, to)
    ui.head(tr(f"undo #{pre}: {chosen['description']}", f"отменить №{pre}: {chosen['description']}")
            + st.faint(f" · {i18n.count(len(changes), 'file', 'files', 'файл', 'файла', 'файлов')}"))
    for line in changes[:8]:
        ui.note(line)
    if len(changes) > 8:
        ui.note("…")
    if ctx.dry_run:
        ui.note(f"$ snapper -c {sn.config} undochange {pre}..{to}")
        return 0
    if not args.yes and not sys.stdin.isatty():
        ui.err(tr("sos: not a terminal — confirm with --yes", "sos: не терминал — подтвердите флагом --yes"))
        return 3
    if not ui.confirm(tr("Undo this change?", "Отменить это изменение?"), default=False, assume=True if args.yes else None):
        return 1
    with Guard(ctx, f"sos: undo #{pre}") as g:
        ok = sn.undochange(pre, to)
    if not ok and not ctx.is_root and sys.stdin.isatty():
        # snapperd refused this user: do it as root (polkit asks once)
        return _elevate(["undo", str(pre), "--yes", "--config", sn.config])
    if args.json:
        ui.print_json({"ok": ok, "undone": pre, "snapshot": {"pre": g.pre, "post": g.post}})
    else:
        ui.head((tr("undone", "отменено") if ok else st.bad(tr("undo failed", "откат не удался")))
                + st.faint(tr(f" · this undo is #{g.pre} (sos undo {g.pre} brings it back)",
                              f" · этот откат — №{g.pre} (sos undo {g.pre} вернёт как было)") if g.pre else ""))
        ui.note(tr("reboot if the kernel or drivers changed", "перезагрузитесь, если менялись ядро или драйверы"))
    return 0 if ok else 1
