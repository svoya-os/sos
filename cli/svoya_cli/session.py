"""``sos session-start`` — Hyprland ``exec-once`` entry (ARCHITECTURE §5). Fast and idempotent:

1. ``sos theme apply <configured|auto>`` (in-process; files are rewritten only if they changed)
   then ``dbus-update-activation-environment --systemd WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE …``
2. ``systemctl --user start --no-block jacksond.service`` (skipped while AI is off: ``sos ai off``)
3. ``quickshell -p /usr/share/svoya/shell`` — unless it is already running — through
   ``/usr/lib/svoya/shell-run``: output to ``$XDG_RUNTIME_DIR/sos-shell.log``, restart after a crash
4. first login only (no ``~/.config/svoya/first-run-done``): ``quickshell -p …/shell/setup`` (logged, no restart);
   in the live session Jackson greets instead and offers the installer (``live.py``)
5. warm the status cache in the background (apt/snapper counts)

A second call in the same session changes nothing. Nothing here waits on the network or on apt.
Each step's outcome is appended to ``~/.local/state/svoya/session.log``.
"""
from __future__ import annotations

import fcntl
import os

from . import config as config_mod
from . import i18n, live, ui
from .context import Ctx
from .i18n import tr
from .runner import svoya_argv
from .util import iso


def running(ctx: Ctx, needle: list[str]) -> bool:
    """Is a process with these argv items (in order, as a subsequence) running for any user?"""
    proc = ctx.sys("/proc")
    try:
        pids = [p for p in proc.iterdir() if p.name.isdigit()]
    except OSError:
        return False
    for p in pids:
        if p.name == str(os.getpid()):
            continue
        try:
            argv = (p / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        args = [a.decode(errors="replace") for a in argv if a]
        if not args:
            continue
        it = iter(args)
        if all(any(n == a or (n == needle[0] and os.path.basename(a) == n) for a in it) for n in needle):
            return True
    return False


def _log(ctx: Ctx, lines: list[str]) -> None:
    path = ctx.paths.state_dir / "session.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 100_000:
            path.write_text("")
        with open(path, "a", encoding="utf-8") as f:
            for ln in lines:
                f.write(f"{iso(ctx.now())} {ln}\n")
    except OSError:
        pass


SHELL_RUN = "/usr/lib/svoya/shell-run"


def _supervised(ctx: Ctx, once: bool = False) -> list[str]:
    """argv prefix for a shell config dir: shell-run (log + restart) when installed, else quickshell -p."""
    if ctx.sys(SHELL_RUN).exists():
        return [SHELL_RUN, "--once"] if once else [SHELL_RUN]
    return ["quickshell", "-p"]


def start(ctx: Ctx) -> list[dict]:
    steps: list[dict] = []
    cfg = config_mod.load(ctx.paths)
    r = ctx.runner

    # 1. theme
    try:
        from .theme.apply import apply_theme
        rep = apply_theme(ctx, str(cfg.get("theme", {}).get("id", "auto")), cfg=cfg)
        steps.append({"step": "theme", "ok": True, "detail": f"{rep['theme']} ({rep['reason']})"})
    except Exception as e:  # a broken template must never block the desktop
        steps.append({"step": "theme", "ok": False, "detail": str(e)})

    # 1b. hand the compositor's environment to systemd --user and D-Bus (jacksond, portals, apps
    #     started by services); svoya-session exported the rest before Hyprland started
    names = [n for n in ("WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "XDG_CURRENT_DESKTOP", "DISPLAY",
                         "LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES")
             if ctx.env.get(n)]
    if names and r.which("dbus-update-activation-environment"):
        res = r.run(["dbus-update-activation-environment", "--systemd", *names], timeout=5, mutating=True)
        steps.append({"step": "environment", "ok": res.ok, "detail": " ".join(names)})
    elif names and r.which("systemctl"):
        res = r.run(["systemctl", "--user", "import-environment", *names], timeout=5, mutating=True)
        steps.append({"step": "environment", "ok": res.ok, "detail": " ".join(names)})

    # 2. Jackson daemon (the daemon, not a model: AI still never runs by itself) — not while AI is off
    from . import ai
    off = ai.off_reason(ctx, cfg)
    ai_on = off is None and cfg.get("session", {}).get("jackson", True)
    if ai_on and r.which("systemctl"):
        res = r.run(["systemctl", "--user", "start", "--no-block", "jacksond.service"], timeout=5, mutating=True)
        steps.append({"step": "jacksond", "ok": res.ok, "detail": res.err.strip()[:200]})
    else:
        why = f"skipped (AI off: {off})" if off else "skipped (session.jackson = false)" if not ai_on else "no systemctl"
        steps.append({"step": "jacksond", "ok": True, "detail": why})

    # 3. the shell
    shell = str(ctx.paths.shell_dir)
    if not cfg.get("session", {}).get("shell", True):
        steps.append({"step": "shell", "ok": True, "detail": "disabled in config"})
    elif running(ctx, ["quickshell", "-p", shell]):
        steps.append({"step": "shell", "ok": True, "detail": "already running"})
    elif r.which("quickshell"):
        ok = r.spawn([*_supervised(ctx), shell])
        steps.append({"step": "shell", "ok": ok, "detail": shell})
    else:
        steps.append({"step": "shell", "ok": False, "detail": "quickshell not installed"})

    # 4. first-run wizard — not in the live session: nothing there persists and a model it offers would
    #    download into RAM. There Jackson greets and offers the installer instead (live.py).
    if live.is_live(ctx):
        steps.append({"step": "first-run", "ok": True, "detail": "skipped (live session)"})
        if r.which("notify-send"):
            app, title, body, button = live.hello(ctx, i18n.lang() == "ru")
            r.spawn(["sh", "-c", live.HELLO_SH, "sh", app, title, body, button, live.INSTALLER], mutating=False)
    elif not ctx.paths.first_run_marker.exists():
        setup = f"{shell}/setup"
        if running(ctx, ["quickshell", "-p", setup]):
            steps.append({"step": "first-run", "ok": True, "detail": "already running"})
        elif r.which("quickshell"):
            steps.append({"step": "first-run", "ok": r.spawn([*_supervised(ctx, once=True), setup]), "detail": setup})
    # 5. warm the status cache (apt/snapper counts) without waiting
    r.spawn([*svoya_argv(), "status", "--refresh-cache"], mutating=False)
    return steps


def main(args, ctx: Ctx | None = None) -> int:
    ctx = ctx or Ctx()
    lock_dir = ctx.paths.runtime_svoya
    lock = None
    try:
        # $XDG_RUNTIME_DIR/svoya is shared with Jackson, which insists on 0700 (its socket lives there)
        lock_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(lock_dir, 0o700)
        lock = open(lock_dir / "session.lock", "w")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        if lock is not None:        # another session-start is running right now: nothing to do
            ui.note(tr("session start already in progress", "запуск сеанса уже идёт"))
            return 0
    steps = start(ctx)
    _log(ctx, [f"{s['step']}: {'ok' if s['ok'] else 'FAIL'} {s['detail']}" for s in steps])
    if args.json:
        ui.print_json({"steps": steps, "dryRun": ctx.dry_run})
    elif ctx.dry_run or os.isatty(1):
        for s in steps:
            ui.out(f"  {ui.mark('ok' if s['ok'] else 'fail')} {s['step'].ljust(10)} {ui.style().faint(s['detail'])}")
    return 0 if all(s["ok"] for s in steps if s["step"] != "first-run") else 1

