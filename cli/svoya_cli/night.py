"""The night rule: heavy work does not start at night when nobody is at the keyboard.

``svoya.toml``::

    [night]
    hours = "23:00-07:00"      # local time; "" or "off" switches the rule off

``sos run`` and ``sos models pull`` (more than ``BIG_DOWNLOAD``) started at night without a
terminal (by Jackson, a script, a timer) do not start: a one-shot systemd user timer starts the
same command with ``--now`` when the night ends, and the output says when and how to cancel it.
``--now`` starts it at once. In a terminal the person is there, and nothing is asked.
"""
from __future__ import annotations

import datetime as dt
import re
import secrets
import shlex
import sys
from pathlib import Path

from .context import Ctx
from .i18n import tr
from .runner import svoya_argv

DEFAULT_HOURS = "23:00-07:00"
BIG_DOWNLOAD = 2 * 2**30          # bytes: a model download bigger than this waits too
_HOURS = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$")


def parse_hours(text: str | None) -> tuple[dt.time, dt.time] | None:
    """``"23:00-07:00"`` → (23:00, 07:00); None when the rule is off or the text is not a range."""
    m = _HOURS.match(text or "")
    if not m:
        return None
    h1, m1, h2, m2 = (int(x) for x in m.groups())
    if h1 > 23 or h2 > 23 or m1 > 59 or m2 > 59 or (h1, m1) == (h2, m2):
        return None
    return dt.time(h1, m1), dt.time(h2, m2)


def hours(cfg: dict) -> tuple[dt.time, dt.time] | None:
    value = (cfg.get("night") or {}).get("hours", DEFAULT_HOURS)
    return parse_hours(value if isinstance(value, str) else None)


def is_night(local: dt.datetime, span: tuple[dt.time, dt.time] | None) -> bool:
    if span is None:
        return False
    start, end = span
    t = local.time().replace(second=0, microsecond=0)
    return start <= t < end if start < end else (t >= start or t < end)


def morning(local: dt.datetime, span: tuple[dt.time, dt.time]) -> dt.datetime:
    """When this night ends: today's or tomorrow's end time."""
    end = local.replace(hour=span[1].hour, minute=span[1].minute, second=0, microsecond=0)
    return end if end > local else end + dt.timedelta(days=1)


def interactive() -> bool:
    try:
        return sys.stdin.isatty() or sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def should_wait(ctx: Ctx, cfg: dict, *, now: bool, attended: bool | None = None) -> dt.datetime | None:
    """The time to start instead of now, or None to start now."""
    if now:
        return None
    span = hours(cfg)
    local = ctx.now().astimezone()
    if not is_night(local, span):
        return None
    if interactive() if attended is None else attended:
        return None
    return morning(local, span)


def put_off(ctx: Ctx, argv: list[str], when: dt.datetime, what: str, cwd: Path | None = None) -> dict:
    """Start ``sos <argv>`` (with its ``--now``) at ``when`` with a transient systemd user timer
    (kept across a sleep: Persistent). → {ok, unit, at, command} or {ok: False, error}."""
    unit = f"sos-later-{re.sub(r'[^a-z0-9]+', '-', what.lower()).strip('-')[:24] or 'job'}-{secrets.token_hex(2)}"
    command = [*svoya_argv(), *argv]
    if not ctx.runner.which("systemd-run"):
        return {"ok": False, "error": "systemd-run is not installed"}
    env = [f"--setenv={k}={ctx.env[k]}" for k in ("PATH", "LANG", "LANGUAGE", "SVOYA_LANG") if ctx.env.get(k)]
    res = ctx.runner.run(["systemd-run", "--user", f"--unit={unit}",
                          f"--description=SOS: {what} (put off until the morning)",
                          f"--on-calendar={when.strftime('%Y-%m-%d %H:%M:%S')}",
                          "--timer-property=Persistent=true", "--timer-property=AccuracySec=1min", "--collect",
                          f"--working-directory={cwd or Path.cwd()}", *env, "--", *command],
                         timeout=15, mutating=True)
    if not res.ok:
        return {"ok": False, "error": (res.err or res.out).strip()[:300] or f"exit {res.rc}"}
    return {"ok": True, "unit": unit, "at": when.isoformat(timespec="minutes"), "command": command}


def say(result: dict, span_text: str, shown: str, ui) -> None:
    """What the person (or Jackson) reads when the work was put off, or could not be."""
    if result.get("ok"):
        at = result["at"][11:16]
        ui.head(tr(f"night ({span_text}): {shown} starts at {at}", f"ночь ({span_text}): {shown} начнётся в {at}"))
        ui.note(tr(f"now instead: add --now · cancel: systemctl --user stop {result['unit']}.timer",
                   f"сейчас: добавь --now · отменить: systemctl --user stop {result['unit']}.timer"))
    else:
        ui.err(tr(f"sos: night ({span_text}): heavy work waits for the morning, and it could not be put off "
                  f"({result.get('error')}); add --now to start it anyway",
                  f"sos: ночь ({span_text}): тяжёлое ждёт утра, а отложить не вышло ({result.get('error')}); "
                  "добавь --now, чтобы запустить всё равно"))


def span_text(cfg: dict) -> str:
    span = hours(cfg)
    return f"{span[0]:%H:%M}-{span[1]:%H:%M}" if span else ""


def shown(argv: list[str]) -> str:
    return "sos " + " ".join(shlex.quote(a) for a in argv)
