"""``sos ai off | on | status`` — the one AI switch (design/WORKFLOWS.md §8).

Off means: Jackson (``jacksond``) and every local model server stop, and stay stopped until
``sos ai on``. The switch is a file, so everything can check it without asking anyone:

* ``~/.config/svoya/ai.off``   this user (``sos ai off``)
* ``/etc/svoya/ai.off``        every user of the machine (``sos ai off --system``, admin password)

``sos status --json`` reports ``ai.enabled``; ``sos session-start`` does not start jacksond while
off; ``svoya-llm.service`` / ``svoya-ollama.service`` carry ``ConditionPathExists=!…ai.off``;
``sos models serve`` refuses. ``sos ai on`` starts Jackson again and restarts exactly the servers
that ``sos ai off`` stopped (remembered in ``~/.local/state/svoya/ai-stopped.json``).
"""
from __future__ import annotations

from . import config as config_mod
from . import ui
from .context import Ctx
from .i18n import tr
from .runner import svoya_argv
from .util import atomic_write, iso, read_json, write_json

# user services that run AI (jacksond first: it is the one that talks to the others)
USER_UNITS = ("jacksond.service", "svoya-llm.service", "llama-swap.service", "llama-server.service", "ollama.service")
# system services (--system): our Ollama unit (modules/llm-local) and upstream's
SYSTEM_UNITS = ("svoya-ollama.service", "ollama.service", "llama-swap.service")
# model servers started by hand or by `sos models serve` without the unit (this user's only)
PROCESSES = ("llama-server", "llama-swap")


def user_marker(ctx: Ctx):
    return ctx.paths.user_config_dir / "ai.off"


def system_marker(ctx: Ctx):
    return ctx.sys("/etc/svoya/ai.off")


def _stopped_file(ctx: Ctx, system: bool):
    return (ctx.paths.var_lib if system else ctx.paths.state_dir) / "ai-stopped.json"


def _since(path) -> str | None:
    try:
        import datetime as dt
        return iso(dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc))
    except OSError:
        return None


def off_reason(ctx: Ctx, cfg: dict | None = None) -> str | None:
    """Why AI is off: "system" | "user" | "config" — or None when it is on."""
    if system_marker(ctx).exists():
        return "system"
    if user_marker(ctx).exists():
        return "user"
    try:
        cfg = cfg if cfg is not None else config_mod.load(ctx.paths)
    except Exception:
        cfg = {}
    if (cfg.get("ai") or {}).get("enabled") is False:
        return "config"
    return None


def enabled(ctx: Ctx, cfg: dict | None = None) -> bool:
    return off_reason(ctx, cfg) is None


# ---------------------------------------------------------------- services and processes

def _units(ctx: Ctx, system: bool) -> list[dict]:
    """Known AI units that exist here: ``[{"unit", "scope", "active"}]`` (one systemctl call)."""
    r = ctx.runner
    if not r.which("systemctl"):
        return []
    names = SYSTEM_UNITS if system else USER_UNITS
    argv = ["systemctl"] + ([] if system else ["--user"]) + ["show", "-p", "Id,LoadState,ActiveState", *names]
    res = r.run(argv, timeout=10)
    if not res.ok and not res.out:
        return []
    out = []
    for block in res.out.strip().split("\n\n"):
        props = dict(ln.split("=", 1) for ln in block.splitlines() if "=" in ln)
        if props.get("LoadState") == "loaded" and props.get("Id"):
            out.append({"unit": props["Id"], "scope": "system" if system else "user",
                        "active": props.get("ActiveState") in ("active", "activating", "reloading")})
    return out


def _processes(ctx: Ctx) -> list[dict]:
    """This user's stray model servers (``llama-server`` started by hand, …) from /proc."""
    uid = ctx.uid
    out = []
    proc = ctx.sys("/proc")
    try:
        pids = [p for p in proc.iterdir() if p.name.isdigit()]
    except OSError:
        return out
    for p in pids:
        try:
            comm = (p / "comm").read_text().strip()
            if comm not in PROCESSES:
                continue
            owner = next((int(ln.split()[1]) for ln in (p / "status").read_text().splitlines() if ln.startswith("Uid:")), None)
        except (OSError, ValueError, IndexError):
            continue
        if owner == uid:
            out.append({"pid": int(p.name), "name": comm})
    return out


def status(ctx: Ctx, cfg: dict | None = None) -> dict:
    reason = off_reason(ctx, cfg)
    marker = system_marker(ctx) if reason == "system" else user_marker(ctx) if reason == "user" else None
    return {"enabled": reason is None, "off": reason, "since": _since(marker) if marker else None,
            "services": _units(ctx, False) + _units(ctx, True), "processes": _processes(ctx)}


# ---------------------------------------------------------------- switching

def _write_marker(path, now) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, f"AI switched off by `sos ai off` at {iso(now)}. Remove this file or run `sos ai on`.\n",
                 mode=0o644)


def switch_off(ctx: Ctx, system: bool = False) -> dict:
    """Write the marker, stop what runs. ``system`` = the root half (marker in /etc, system units)."""
    r = ctx.runner
    stopped: list[str] = []
    killed: list[int] = []
    marker = system_marker(ctx) if system else user_marker(ctx)
    if not ctx.dry_run:
        _write_marker(marker, ctx.now())
    base = ["systemctl"] + ([] if system else ["--user"])
    for u in _units(ctx, system):
        if u["active"]:
            res = r.run([*base, "stop", u["unit"]], timeout=60, mutating=True)
            if res.ok:
                stopped.append(u["unit"])
    if not system:
        for p in _processes(ctx):
            if r.run(["kill", "-TERM", str(p["pid"])], timeout=5, mutating=True).ok:
                killed.append(p["pid"])
    if stopped and not ctx.dry_run:
        path = _stopped_file(ctx, system)
        prev = (read_json(path) or {}).get("units", [])
        write_json(path, {"units": sorted(set(prev) | set(stopped)), "at": iso(ctx.now())})
    return {"marker": str(marker), "stopped": stopped, "killed": killed}


def switch_on(ctx: Ctx, cfg: dict, system: bool = False) -> dict:
    r = ctx.runner
    marker = system_marker(ctx) if system else user_marker(ctx)
    if not ctx.dry_run:
        try:
            marker.unlink()
        except FileNotFoundError:
            pass
    started: list[str] = []
    path = _stopped_file(ctx, system)
    wanted = list((read_json(path) or {}).get("units", []))
    if system_marker(ctx).exists() and not system:
        return {"marker": str(marker), "started": started, "blocked": "system"}
    if not system and (cfg.get("ai") or {}).get("enabled") is False and not ctx.dry_run:
        config_mod.set_user_value(ctx.paths, "ai", "enabled", True)
    known = {u["unit"]: u for u in _units(ctx, system)}
    if not system and cfg.get("session", {}).get("jackson", True) and "jacksond.service" in known:
        wanted = ["jacksond.service"] + [u for u in wanted if u != "jacksond.service"]
    base = ["systemctl"] + ([] if system else ["--user"])
    for unit in wanted:
        if unit in known and not known[unit]["active"]:
            if r.run([*base, "start", "--no-block", unit], timeout=30, mutating=True).ok:
                started.append(unit)
    if not ctx.dry_run:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    return {"marker": str(marker), "started": started, "blocked": None}


def _elevate(ctx: Ctx, action: str) -> dict:
    """The --system half runs as root via pkexec (polkit shows the exact command)."""
    if ctx.is_root:
        return {"ok": True}
    if not ctx.runner.which("pkexec"):
        return {"ok": False, "error": "pkexec is not installed"}
    res = ctx.runner.run(["pkexec", *svoya_argv(), "ai", action, "--system", "--root-only", "--json"],
                         timeout=300, mutating=True)
    return {"ok": res.ok, **({} if res.ok else {"error": (res.err or res.out).strip()[:300] or f"exit {res.rc}"})}


def main(args, ctx: Ctx | None = None) -> int:
    ctx = ctx or Ctx()
    cmd = args.ai_cmd or "status"
    cfg = config_mod.load(ctx.paths)
    st = ui.style()
    as_json = getattr(args, "json", False)

    if cmd == "status":
        s = status(ctx, cfg)
        if as_json:
            ui.print_json(s)
            return 0
        running = [u["unit"].removesuffix(".service") for u in s["services"] if u["active"]] + [p["name"] for p in s["processes"]]
        if s["enabled"]:
            ui.head(tr("AI on", "ИИ включён") + st.faint(" · " + (", ".join(running) if running else
                                                                   tr("nothing running", "ничего не запущено"))))
        else:
            why = {"system": tr("for everyone (admin)", "для всех (администратор)"),
                   "user": tr("by you", "вами"), "config": "svoya.toml [ai] enabled = false"}[s["off"]]
            ui.head(tr("AI off", "ИИ выключен") + st.faint(f" · {why}" + (f" · {s['since'][:16].replace('T', ' ')}" if s["since"] else "")))
            if running:
                ui.note(tr("still running: ", "всё ещё работает: ") + ", ".join(running) + " — sos ai off")
            ui.note(tr("turn on: sos ai on", "включить: sos ai on"))
        return 0

    system = bool(getattr(args, "system", False))
    if getattr(args, "root_only", False):                  # pkexec half
        if not ctx.is_root:
            ui.err(tr("sos: this step runs as root — use --system", "sos: этот шаг выполняется от root — используйте --system"))
            return 2
        res = switch_off(ctx, system=True) if cmd == "off" else switch_on(ctx, cfg, system=True)
        if as_json:
            ui.print_json(res)
        return 0

    result: dict = {"action": cmd, "system": None, "dryRun": ctx.dry_run}
    if cmd == "off":
        if not ctx.is_root or not system:
            result["user"] = switch_off(ctx)
        if system:
            result["system"] = switch_off(ctx, system=True) if ctx.is_root else _elevate(ctx, "off")
    else:
        if system:
            result["system"] = switch_on(ctx, cfg, system=True) if ctx.is_root else _elevate(ctx, "on")
        if not ctx.is_root or not system:
            result["user"] = switch_on(ctx, cfg)
    sys_ok = result["system"] is None or result["system"].get("ok", True)
    result["enabled"] = enabled(ctx) if not ctx.dry_run else (cmd == "on")
    if as_json:
        ui.print_json(result)
        return 0 if sys_ok and not (result.get("user") or {}).get("blocked") else 1

    user = result.get("user") or {}
    where = st.faint(tr(" · for everyone", " · для всех")) if system and sys_ok else ""
    if ctx.dry_run:   # nothing was switched: say what would happen
        where += st.faint(tr(" · dry run, nothing changed", " · пробный запуск, ничего не изменено"))
    if cmd == "off":
        stopped = [u.removesuffix(".service") for u in user.get("stopped", [])] + \
                  [str(p) for p in user.get("killed", [])]
        detail = tr("stopped: ", "остановлено: ") + ", ".join(stopped) if stopped else tr("nothing was running", "ничего не работало")
        if ctx.dry_run:
            ui.head(tr("AI would be turned off", "ИИ будет выключен") + where)
        else:
            ui.head(tr("AI off", "ИИ выключен") + where + st.faint(f" · {detail} · " + tr("turn on: sos ai on", "включить: sos ai on")))
    else:
        if user.get("blocked") == "system":
            ui.head(tr("AI stays off for everyone on this computer", "ИИ выключен для всех на этом компьютере")
                    + st.faint(" · sos ai on --system"))
            return 1
        started = [u.removesuffix(".service") for u in user.get("started", [])]
        detail = tr("started: ", "запущено: ") + ", ".join(started) if started else tr("nothing to start", "запускать нечего")
        if ctx.dry_run:
            ui.head(tr("AI would be turned on", "ИИ будет включён") + where)
        else:
            ui.head(tr("AI on", "ИИ включён") + where + st.faint(f" · {detail}"))
    if not sys_ok:
        ui.err(tr(f"sos: the system-wide switch was not changed: {result['system'].get('error', '')}",
                  f"sos: общий выключатель не изменён: {result['system'].get('error', '')}"))
        return 1
    return 0
