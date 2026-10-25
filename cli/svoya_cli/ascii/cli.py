"""``sos eye`` and ``sos art``: settings, then the effect full screen, or one still frame when there
is no terminal (a pipe, SSH without a TTY) or quiet mode is on.

Settings live in ``[ascii]`` of svoya.toml: ``fps`` (30), ``speed`` (1.0), ``quiet`` (false: no
animation, one still frame), ``timezone`` ("Europe/Tallinn": when the pupil opens for the night),
``colors = {bg, fg, accent, noise}`` (#rrggbb) and ``sound`` (reserved; off).
"""
from __future__ import annotations

import datetime as dt
import re
import shutil
import sys

from .. import config, ui
from ..context import Ctx
from ..i18n import tr
from .engine import PALETTE, run, still

ART = {"planets": ("two worlds and an eclipse", "две планеты и затмение"),
       "rain": ("rain at night; now and then it writes the signal into the water",
                "ночной дождь; время от времени он пишет на воде сигнал"),
       "logo": ("the letters SOS out of noise, the boot line, the signal",
                "буквы SOS из шума, линия загрузки, сигнал"),
       "heart": ("a heart beating seventy-two times a minute, and its monitor",
                 "сердце, семьдесят два удара в минуту, и его монитор")}


def settings(ctx: Ctx) -> dict:
    raw = config.load(ctx.paths).get("ascii") or {}
    colors = {k: v for k, v in (raw.get("colors") or {}).items()
              if k in PALETTE and isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v)}
    return {"fps": int(raw.get("fps", 30) or 30), "speed": float(raw.get("speed", 1.0) or 1.0),
            "quiet": bool(raw.get("quiet", False)), "timezone": str(raw.get("timezone") or "Europe/Tallinn"),
            "colors": colors}


def _clock(tz: str):
    def now() -> str:
        try:
            from zoneinfo import ZoneInfo
            return dt.datetime.now(ZoneInfo(tz)).strftime("%H:%M")
        except Exception:
            return dt.datetime.now().strftime("%H:%M")
    return now


def _show(effect, args, ctx: Ctx, cfg: dict, any_key: bool = False) -> int:
    quiet = getattr(args, "quiet", False) or cfg["quiet"] or ctx.env.get("SOS_ASCII_QUIET") == "1"
    tty = sys.stdout.isatty() and sys.stdin.isatty()
    if quiet or not tty:
        w, h = shutil.get_terminal_size((80, 24))
        sys.stdout.write(still(effect, w, h, color=sys.stdout.isatty(), palette=cfg["colors"], env=ctx.env))
        return 0
    return run(effect, fps=getattr(args, "fps", None) or cfg["fps"], speed=cfg["speed"],
               seconds=getattr(args, "seconds", None), any_key_quits=any_key, palette=cfg["colors"], env=ctx.env)


def main_eye(args, ctx: Ctx) -> int:
    from .eye import Eye
    cfg = settings(ctx)
    eye = Eye(state=args.state, hud=not (args.idle or args.story), story=args.story, tz=cfg["timezone"],
              clock=_clock(cfg["timezone"]))
    return _show(eye, args, ctx, cfg, any_key=args.idle)


def main_art(args, ctx: Ctx) -> int:
    if not args.effect:
        st = ui.style()
        ui.out(st.accent(tr("ASCII screensavers: sos art <name>", "ASCII-заставки: sos art <название>")))
        for name, (en, ru) in ART.items():
            ui.out(f"  {name:<9} {tr(en, ru)}")
        return 0
    from .heart import Heart
    from .logo import Logo
    from .planets import Planets
    from .rain import Rain
    effects = {"planets": Planets, "rain": Rain, "logo": Logo, "heart": Heart}
    cfg = settings(ctx)
    return _show(effects[args.effect](), args, ctx, cfg, any_key=True)
