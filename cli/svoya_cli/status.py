"""``sos status [--json] [--write] [--watch N]`` — ARCHITECTURE §4.2, polled by the shell every 2 s.

Fast path only: one ``nvidia-smi`` query, sysfs reads, small JSON files. Anything slow (apt,
snapper) is read from a cache under ``~/.local/state/svoya/cache/`` and refreshed by a detached
``sos status --refresh-cache`` at most once per TTL, so a poll never waits for apt.

Output (every field optional)::

    {"gpu": [{"index":0,"vendor":"nvidia","name":"RTX 4090","tempC":64,"vramUsedMiB":11468,
              "vramTotalMiB":24564,"util":93,"powerW":301,"driver":"595.58","ok":true}],
     "jobs": [{"id":"train-1832","label":"обучение","progress":0.62,"etaSec":1080}],
     "ai": {"local":true,"cloudActiveSince":null},
     "updates": {"available":3,"security":1},
     "snapshots": {"last":"2026-09-24T18:02:11Z"}}

Extra keys (documented, ignorable): ``gpu[].integrated``, ``gpu[].gttUsedMiB``/``gttTotalMiB``
(AMD APUs), ``updates.checkedAt``, ``ts`` (when this status was produced).
"""
from __future__ import annotations

import fcntl
import json
import re
import sys
import time

from . import i18n, jobs, ui
from .context import Ctx
from .hw import gpu as gpu_mod
from .i18n import tr
from .runner import svoya_argv
from .util import iso, parse_iso, read_json, write_json

UPDATES_TTL = 6 * 3600
SNAPSHOTS_TTL = 10 * 60
REFRESH_BACKOFF = 120          # do not respawn a refresher more often than this
HOT_C = 90


# ---------------------------------------------------------------- slow sources (cached)

def count_updates(ctx: Ctx) -> dict | None:
    """``{"available": n, "security": m}`` from apt's current package lists (no network)."""
    apt_check = ctx.sys("/usr/lib/update-notifier/apt-check")
    if apt_check.exists():
        r = ctx.runner.run([str(apt_check)], timeout=60)
        m = re.search(r"(\d+);(\d+)", r.err + r.out)
        if m:
            return {"available": int(m.group(1)), "security": int(m.group(2))}
    if not ctx.runner.which("apt-get"):
        return None
    r = ctx.runner.run(["apt-get", "-s", "-o", "Debug::NoLocking=1", "dist-upgrade"], timeout=120,
                       env={"LC_ALL": "C", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"})
    if not r.ok:
        return None
    return parse_apt_simulation(r.out)


def parse_apt_simulation(text: str) -> dict:
    """Count ``Inst`` lines; security = origin mentions ``-security``."""
    avail = sec = 0
    for line in text.splitlines():
        if not line.startswith("Inst "):
            continue
        avail += 1
        m = re.search(r"\(([^)]*)\)", line)
        if m and "-security" in m.group(1):
            sec += 1
    return {"available": avail, "security": sec}


def last_snapshot(ctx: Ctx) -> str | None:
    from .snapshots import Snapper  # lazy: only the refresher needs it
    t = Snapper(ctx).last_date()
    return iso(t) if t else None


def refresh_cache(ctx: Ctx) -> int:
    """Body of the detached refresher. Holds a lock so concurrent pollers never pile up."""
    cache = ctx.paths.cache_dir
    cache.mkdir(parents=True, exist_ok=True)
    lock_path = cache / "refresh.lock"
    with open(lock_path, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return 0
        now = iso(ctx.now())
        upd = count_updates(ctx)
        if upd is not None:
            write_json(cache / "updates.json", {**upd, "checkedAt": now})
        snap = last_snapshot(ctx)
        write_json(cache / "snapshots.json", {"last": snap, "checkedAt": now})
    return 0


def _stale(data: dict | None, ttl: int, now) -> bool:
    if not isinstance(data, dict):
        return True
    t = parse_iso(data.get("checkedAt"))
    return t is None or (now - t).total_seconds() > ttl


def _maybe_spawn_refresh(ctx: Ctx) -> None:
    marker = ctx.paths.cache_dir / "refresh.spawned"
    try:
        if time.time() - marker.stat().st_mtime < REFRESH_BACKOFF:
            return
    except OSError:
        pass
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except OSError:
        return
    ctx.runner.spawn([*svoya_argv(), "status", "--refresh-cache"], mutating=False)


# ---------------------------------------------------------------- collect

def ai_state(ctx: Ctx, now) -> dict:
    """``ai`` for the bar: jacksond's runtime state (``$XDG_RUNTIME_DIR/svoya/ai.json``: local,
    cloudActiveSince, …) + the AI switch (``enabled``/``off``: ``sos ai off`` markers or ``[ai] enabled``
    in svoya.toml) + today's totals from Jackson's spend ledger (``~/.local/share/svoya/jackson/spend.json``)."""
    out: dict = {}
    rt = read_json(ctx.paths.runtime_svoya / "ai.json")
    if isinstance(rt, dict):
        out.update({k: v for k, v in rt.items() if isinstance(k, str)})
        if "local" in out:
            out["local"] = bool(out["local"])
            out.setdefault("cloudActiveSince", None)
    # the AI switch: ~/.config/svoya/ai.off, /etc/svoya/ai.off (sos ai off) or [ai] enabled = false
    if ctx.sys("/etc/svoya/ai.off").exists():
        out["enabled"], out["off"] = False, "system"
    elif (ctx.paths.user_config_dir / "ai.off").exists():
        out["enabled"], out["off"] = False, "user"
    else:
        from . import config as config_mod
        out["enabled"] = config_mod.load(ctx.paths).get("ai", {}).get("enabled") is not False
        if not out["enabled"]:
            out["off"] = "config"
    ledger = read_json(ctx.paths.data_home / "svoya" / "jackson" / "spend.json")
    if isinstance(ledger, dict) and isinstance(ledger.get("days"), dict):
        day = ledger["days"].get(now.astimezone().strftime("%Y-%m-%d")) or {}
        out["todayCostEur"] = round(float(day.get("eur", 0.0)), 4)
        out["todayCloudRequests"] = int(day.get("left", 0))
    return out


def _gpu_ok(g: dict, doctor: dict | None) -> bool:
    if g.get("tempC") is not None and g["tempC"] >= HOT_C:
        return False
    if isinstance(doctor, dict) and doctor.get("gpuOk") is False:
        return False
    return True


def collect(ctx: Ctx, *, background: bool = True) -> dict:
    now = ctx.now()
    status: dict = {}

    gpus = gpu_mod.live_stats(ctx)
    if gpus:
        doctor = read_json(ctx.paths.state_dir / "doctor.json")
        for g in gpus:
            g.pop("card", None)
            g["ok"] = _gpu_ok(g, doctor)
        status["gpu"] = gpus

    status["jobs"] = jobs.for_status(ctx.paths.jobs_dir, now)

    ai = ai_state(ctx, now)
    if ai:
        status["ai"] = ai

    cache = ctx.paths.cache_dir
    upd = read_json(cache / "updates.json")
    snaps = read_json(cache / "snapshots.json")
    if isinstance(upd, dict) and "available" in upd:
        status["updates"] = {"available": int(upd.get("available", 0)),
                             "security": int(upd.get("security", 0)),
                             "checkedAt": upd.get("checkedAt")}
    # svoya's own snapshots are recorded instantly in the history file (no snapper call needed)
    last = snaps.get("last") if isinstance(snaps, dict) else None
    hist = read_json(ctx.paths.history_file)
    if isinstance(hist, dict) and hist.get("snapshots"):
        at = hist["snapshots"][-1].get("at")
        if at and (last is None or at > last):
            last = at
    if last or isinstance(snaps, dict):
        status["snapshots"] = {"last": last}

    if background and (_stale(upd, UPDATES_TTL, now) or _stale(snaps, SNAPSHOTS_TTL, now)):
        _maybe_spawn_refresh(ctx)
    status["ts"] = iso(now)
    return status


# ---------------------------------------------------------------- human output

def render(status: dict) -> None:
    st = ui.style()
    ui.head(tr("status", "состояние"))
    for g in status.get("gpu", []):
        parts = [g.get("name", "GPU")]
        if g.get("tempC") is not None:
            parts.append(f"{g['tempC']}°")
        if g.get("vramTotalMiB"):
            used = (g.get("vramUsedMiB") or 0) / 1024
            parts.append(f"{i18n.smart(used)}/{i18n.smart(g['vramTotalMiB'] / 1024)} {tr('GB', 'ГБ')}")
        if g.get("util") is not None:
            parts.append(f"{g['util']}%")
        if g.get("powerW") is not None:
            parts.append(f"{g['powerW']} {tr('W', 'Вт')}")
        if g.get("driver"):
            parts.append(st.faint(tr("driver ", "драйвер ") + g["driver"]))
        line = f" {st.faint('·')} ".join(parts)
        ui.kv(tr("gpu", "гп"), line if g.get("ok", True) else st.bad(line), width=12)
    if not status.get("gpu"):
        ui.kv(tr("gpu", "гп"), st.faint(tr("no GPU data", "нет данных о ГП")), width=12)
    for j in status.get("jobs", []):
        bits = [j.get("label") or j.get("id")]
        if j.get("progress") is not None:
            bits.append(f"{round(j['progress'] * 100)}%")
        if j.get("etaSec") is not None:
            bits.append(st.faint(tr("left ", "ещё ") + i18n.duration(j["etaSec"])))
        ui.kv(tr("job", "задача"), " ".join(bits), width=12)
    ai = status.get("ai")
    if ai:
        ui.kv(tr("ai", "ии"), tr("local", "локально") if ai.get("local") else st.cloud(tr("cloud", "облако")), width=12)
    upd = status.get("updates")
    if upd:
        txt = str(upd["available"]) if upd["available"] else tr("none", "нет")
        if upd.get("security"):
            txt += " " + st.warn(tr(f"({upd['security']} security)", f"({upd['security']} безопасности)"))
        ui.kv(tr("updates", "обновления"), txt, width=12)
    snaps = status.get("snapshots")
    if snaps is not None:
        t = parse_iso(snaps.get("last"))
        from .util import utcnow
        ui.kv(tr("snapshot", "снимок"), i18n.ago((utcnow() - t).total_seconds() if t else None), width=12)


def main(args, ctx: Ctx | None = None) -> int:
    ctx = ctx or Ctx()
    if getattr(args, "refresh_cache", False):
        return refresh_cache(ctx)
    watch = getattr(args, "watch", None)
    if watch:
        interval = max(0.5, float(watch))
        try:
            while True:
                s = collect(ctx)
                if args.write:
                    write_json(ctx.paths.status_json, s)
                sys.stdout.write(json.dumps(s, ensure_ascii=False, separators=(",", ":")) + "\n")
                sys.stdout.flush()
                time.sleep(interval)
        except KeyboardInterrupt:
            return 0
        except BrokenPipeError:            # reader went away (e.g. `| head`): exit quietly
            import os
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
            return 0
    s = collect(ctx)
    if args.write:
        write_json(ctx.paths.status_json, s)
    if args.json:
        print(json.dumps(s, ensure_ascii=False, separators=(",", ":")))
    else:
        render(s)
    return 0
