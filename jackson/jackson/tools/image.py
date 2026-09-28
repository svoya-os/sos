# SPDX-License-Identifier: Apache-2.0
"""image.draw: the model asks the Studio for a picture (jackson/draw.py). «Нарисуй …» on its own
goes there without a model; this tool is for requests the model plans ("a logo for my cafe, then
put it in the README")."""

from __future__ import annotations

from typing import Any

from .. import draw as draw_mod
from .base import T1, Tool, ToolContext, ToolResult


def image_draw(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    drawer = ctx.extra.get("draw")
    ru = ctx.lang.startswith("ru")
    if drawer is None:
        return ToolResult(False, "Drawing is not available in this client.",
                          "рисование недоступно" if ru else "drawing unavailable")
    prompt = " ".join(str(args.get("prompt") or "").split())
    if not prompt:
        return ToolResult(False, "Empty prompt: describe the picture.", "нет описания" if ru else "no description")
    size = str(args.get("size") or "square")
    req = draw_mod.DrawRequest(prompt=prompt[:2000], size=size if size in draw_mod.SIZES else "square",
                               text=prompt[:2000], describe=False)       # the model wrote the description
    res = drawer.draw(req, ctx.cancel, ctx.extra.get("progress"))
    answer = ctx.extra.get("draw_answer")
    said = answer(res, ctx.lang) if callable(answer) else str(res.path or res.code)
    if not res.ok or res.path is None:
        return ToolResult(False, f"Not drawn ({res.code}). Tell the user: {said}", res.code)
    w, h = res.size
    return ToolResult(True, f"Saved the picture to {res.path} ({w}×{h}, {draw_mod.KITS[res.kit].name}). "
                            "Jackson's panel already shows it; tell the user where it is in one short sentence.",
                      f"{draw_mod.KITS[res.kit].name} · {w}×{h}", data={"image": str(res.path)}, verified=True)


def tools() -> list[Tool]:
    return [
        Tool("image.draw",
             "Draw a picture on this computer (FLUX.2 klein in the SOS Studio; saved to ~/Pictures/Jackson). "
             "prompt: one English paragraph, 40-90 words: subject, setting, composition, light, colors, style.",
             {"type": "object", "properties": {
                 "prompt": {"type": "string"},
                 "size": {"type": "string", "enum": sorted(draw_mod.SIZES)}},
              "required": ["prompt"]},
             image_draw, T1, frozenset({"exec"}), None, {"ru": "рисунок", "en": "drawing"}, timeout=2400.0),
    ]
