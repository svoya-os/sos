"""Quiet mode for the graphics card: a lower power limit for long renders and night work.

The card draws less, heats less and its fans turn slower; the work takes a little longer
(at 70 % of the default limit, typically 5–15 % slower). Until a reboot or ``sos quiet off``.

NVIDIA: ``nvidia-smi -pl`` (laptop GPUs often refuse it). AMD: ``power1_cap`` in the amdgpu
hwmon folder. Changing the limit needs root: the user half asks polkit (pkexec) to run
``sos quiet on --root-only``, and polkit shows that exact command.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import gpu as gpu_mod

DEFAULT_PERCENT = 70
QUERY = ["nvidia-smi", "--query-gpu=index,name,power.limit,power.default_limit,power.min_limit,power.max_limit",
         "--format=csv,noheader,nounits"]


def _w(text: str) -> float | None:
    try:
        return float(text.strip())
    except ValueError:
        return None                          # "[N/A]", "[Not Supported]"


def parse_nvidia(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        f = [x.strip() for x in line.split(",")]
        if len(f) < 6:
            continue
        if len(f) > 6:                       # a comma in the name
            f = [f[0], ",".join(f[1:len(f) - 4])] + f[len(f) - 4:]
        idx = _w(f[0])
        out.append({"vendor": "nvidia", "index": int(idx) if idx is not None else len(out),
                    "name": gpu_mod.short_name(f[1]), "limit": _w(f[2]), "default": _w(f[3]),
                    "min": _w(f[4]), "max": _w(f[5])})
    return out


def nvidia(ctx) -> list[dict]:
    if not ctx.runner.which("nvidia-smi"):
        return []
    r = ctx.runner.run(QUERY, timeout=5)
    return parse_nvidia(r.out) if r.ok else []


def _uw(p: Path) -> float | None:
    try:
        return int(p.read_text().strip()) / 1e6
    except (OSError, ValueError):
        return None


def amd(ctx) -> list[dict]:
    out = []
    drm = ctx.sys("/sys/class/drm")
    try:
        cards = sorted((c for c in drm.iterdir() if re.fullmatch(r"card\d+", c.name)), key=lambda c: int(c.name[4:]))
    except OSError:
        return out
    for card in cards:
        dev = card / "device"
        try:
            if (dev / "vendor").read_text().strip().lower() != "0x1002":
                continue
        except OSError:
            continue
        for hw in sorted((dev / "hwmon").glob("hwmon*")) if (dev / "hwmon").is_dir() else []:
            if (hw / "power1_cap").exists():
                name = next((g["name"] for g in gpu_mod.amd_stats(ctx) if g.get("card") == card.name), "Radeon GPU")
                out.append({"vendor": "amd", "card": card.name, "name": name, "path": str(hw / "power1_cap"),
                            "limit": _uw(hw / "power1_cap"), "default": _uw(hw / "power1_cap_default"),
                            "min": _uw(hw / "power1_cap_min"), "max": _uw(hw / "power1_cap_max")})
                break
    return out


def cards(ctx) -> list[dict]:
    """GPUs whose power limit can be read; ``quiet`` says whether the limit is below the default."""
    out = [g for g in nvidia(ctx) + amd(ctx) if g.get("limit") and g.get("default")]
    for g in out:
        g["quiet"] = g["limit"] < g["default"] * 0.97
    return out


def target(g: dict, on: bool, percent: int = DEFAULT_PERCENT) -> int:
    """The limit to set, in whole watts: ``percent`` of the default, never below the card's minimum."""
    if not on:
        return int(round(g["default"]))
    want = g["default"] * max(10, min(100, percent)) / 100
    if g.get("min"):
        want = max(want, g["min"])
    return int(round(want))


def apply(ctx, g: dict, watts: int) -> tuple[bool, str]:
    """Set the limit (as root). → (ok, what went wrong)."""
    if g["vendor"] == "nvidia":
        r = ctx.runner.run(["nvidia-smi", "-i", str(g["index"]), "-pl", str(watts)], timeout=15, mutating=True)
        return r.ok, "" if r.ok else (r.err or r.out).strip()[:200]
    if ctx.dry_run:
        return True, ""
    try:
        Path(g["path"]).write_text(str(watts * 1_000_000))
        return True, ""
    except OSError as e:
        return False, str(e)


def main(args, ctx) -> int:
    """``sos quiet [on|off|status] [--percent N]`` (``sos тихо вкл``, ``sos gpu quiet on``)."""
    import json

    from .. import ui
    from ..i18n import tr
    from ..runner import svoya_argv

    state = args.state or "status"
    on = state == "on"
    percent = int(args.percent or DEFAULT_PERCENT)
    st = ui.style()

    def row(g: dict, watts: int | None = None, ok: bool = True, error: str = "") -> dict:
        return {"vendor": g["vendor"], "name": g["name"], "limitW": g["limit"], "defaultW": g["default"],
                "minW": g.get("min"), "maxW": g.get("max"), "quiet": g["quiet"],
                **({} if watts is None else {"setW": watts, "ok": ok, **({"error": error} if error else {})})}

    if getattr(args, "root_only", False):                      # the pkexec half
        if not ctx.is_root:
            ui.err(tr("sos: this step runs as root", "sos: этот шаг выполняется от root"))
            return 2
        done = []
        for g in cards(ctx):
            w = target(g, on, percent)
            ok, error = apply(ctx, g, w)
            done.append(row(g, w, ok, error))
        ui.print_json({"cards": done})
        return 0 if done and all(d["ok"] for d in done) else 1

    gs = cards(ctx)
    if not gs:
        if args.json:
            ui.print_json({"cards": []})
        else:
            ui.head(tr("no graphics card here lets SOS change its power limit",
                       "ни одна видеокарта здесь не даёт менять предел мощности"))
            ui.note(tr("quiet mode works with NVIDIA (nvidia-smi) and AMD (amdgpu) cards",
                       "тихий режим умеет видеокарты NVIDIA (nvidia-smi) и AMD (amdgpu)"))
        return 0 if state == "status" else 2
    if state == "status":
        if args.json:
            ui.print_json({"cards": [row(g) for g in gs]})
            return 0
        for g in gs:
            mode = st.accent(tr("quiet", "тихий")) if g["quiet"] else tr("normal", "обычный")
            ui.kv(g["name"], f"{g['limit']:.0f} {tr('W', 'Вт')} · {mode}"
                  + st.faint(tr(f"  (default {g['default']:.0f} W)", f"  (по умолчанию {g['default']:.0f} Вт)")), width=12)
        ui.note(tr("quiet: sos quiet on · normal: sos quiet off", "тихо: sos тихо вкл · обычно: sos тихо выкл"))
        return 0

    if ctx.is_root:
        done = []
        for g in gs:
            w = target(g, on, percent)
            ok, error = apply(ctx, g, w)
            done.append(row(g, w, ok, error))
    elif ctx.dry_run:
        done = [row(g, target(g, on, percent)) for g in gs]
    else:
        if not ctx.runner.which("pkexec"):
            ui.err(tr("sos: pkexec is not installed", "sos: pkexec не установлен"))
            return 2
        r = ctx.runner.run(["pkexec", *svoya_argv(), "quiet", state, "--percent", str(percent), "--root-only"],
                           timeout=120, mutating=True)
        try:
            done = json.loads(r.out)["cards"]
        except (ValueError, KeyError, TypeError):
            ui.err(tr("sos: the power limit was not changed (no administrator rights?)",
                      "sos: предел мощности не изменён (нет прав администратора?)"))
            return 1
    if args.json:
        ui.print_json({"state": state, "cards": done, "dryRun": ctx.dry_run})
    else:
        for d in done:
            if d.get("ok", True):
                ui.kv(d["name"], f"{d['setW']} {tr('W', 'Вт')}" + st.faint(
                    tr(f"  (was {d['limitW']:.0f} W, default {d['defaultW']:.0f} W)",
                       f"  (было {d['limitW']:.0f} Вт, по умолчанию {d['defaultW']:.0f} Вт)")), width=12)
            else:
                ui.kv(d["name"], st.bad(tr("not changed: ", "не изменено: ") + d.get("error", "")), width=12)
        if on and any(d.get("ok", True) for d in done):
            ui.note(tr("quieter and cooler, a little slower; until a reboot or sos quiet off",
                       "тише и холоднее, чуть медленнее; до перезагрузки или sos тихо выкл"))
    return 0 if all(d.get("ok", True) for d in done) else 1
