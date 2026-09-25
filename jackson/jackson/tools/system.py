# SPDX-License-Identifier: Apache-2.0
"""system.info (T0), apps.open (T1; URLs are external), notify (T0), settings.theme (T1)."""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

from ..i18n import fmt_bytes, fmt_number, norm_lang
from ..osctl import OsControl
from .base import T0, T1, Assessment, Tool, ToolContext, ToolResult, UndoSpec, obj
from .fs import check, display, expand, real

THEMES = {"graphite", "paper", "phosphor", "auto"}
THEME_ALIASES = {"dark": "graphite", "light": "paper", "тёмная": "graphite", "темная": "graphite",
                 "светлая": "paper", "фосфор": "phosphor", "графит": "graphite", "бумага": "paper", "авто": "auto"}


def _os(ctx: ToolContext) -> OsControl:
    return OsControl(ctx.runner, ctx.paths, ctx.svoya)


def _ru(ctx: ToolContext) -> bool:
    return norm_lang(ctx.lang) == "ru"


# ---------------------------------------------------------------------------
# system.info

def system_info(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    section = args.get("section", "all")
    osc = _os(ctx)
    info: dict[str, Any] = {}
    if section in ("all", "gpu"):
        info["gpu"] = osc.gpus()
    if section in ("all", "disk"):
        info["disks"] = osc.disks()
    if section in ("all", "memory"):
        m = osc.meminfo()
        info["memory"] = {"totalBytes": m.get("MemTotal"), "availableBytes": m.get("MemAvailable")}
    if section in ("all", "cpu"):
        info["cpu"] = osc.cpu()
        info["uptimeSec"] = osc.uptime()
    if section in ("all", "battery"):
        info["battery"] = osc.battery()
    if section in ("all", "status"):
        status = ctx.svoya.status()
        if status:
            info["svoya"] = {k: v for k, v in status.items() if k != "gpu"}
    parts = []
    for g in info.get("gpu") or []:
        vram = ""
        if g.get("vramTotalMiB"):
            used = (g.get("vramUsedMiB") or 0) / 1024
            vram = f" {fmt_number(used, ctx.lang, 1)}/{fmt_number(g['vramTotalMiB'] / 1024, ctx.lang, 0)} " \
                   + ("ГБ" if _ru(ctx) else "GB")
        parts.append(f"{g.get('name', 'GPU')}{vram}")
    for d in info.get("disks") or []:
        parts.append(f"{d['mount']} {fmt_bytes(d['free'], ctx.lang)} " + ("свободно" if _ru(ctx) else "free"))
    summary = " · ".join(parts[:3]) or section
    return ToolResult(True, json.dumps(info, ensure_ascii=False, indent=1), summary, data=info, verified=True)


# ---------------------------------------------------------------------------
# apps.open

def _classify_target(target: str) -> str:
    scheme = urllib.parse.urlsplit(target).scheme.lower()
    if scheme in ("http", "https", "ftp", "mailto", "tel", "sms", "xmpp", "irc", "magnet", "ssh"):
        return "url"
    if target.startswith(("/", "~", "./", "../")) or scheme == "file":
        return "path"
    return "app"


def _assess_open(ctx: ToolContext, args: dict[str, Any]) -> Assessment:
    target = str(args.get("target") or "").strip()
    kind = _classify_target(target)
    ru = _ru(ctx)
    if not target:
        return Assessment(T1, blocked="empty target")
    if kind == "url":
        host = urllib.parse.urlsplit(target).netloc or target
        return Assessment(T1, preview=(f"Открыть ссылку: {target}" if ru else f"Open link: {target}"),
                          scope=f"net:{host}", external=True)
    if kind == "path":
        path = real(expand(ctx, target.removeprefix("file://")))
        a = check(ctx, path, write=False)
        a.tier = max(a.tier, T1)
        a.preview = f"Открыть {display(ctx, path)}" if ru else f"Open {display(ctx, path)}"
        return a
    return Assessment(T1, preview=(f"Запустить приложение «{target}»" if ru else f"Launch app “{target}”"),
                      scope=f"app:{target.lower()}")


def apps_open(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    target = str(args.get("target") or "").strip()
    kind = _classify_target(target)
    osc = _os(ctx)
    ru = _ru(ctx)
    if kind in ("url", "path"):
        arg = target if kind == "url" else str(real(expand(ctx, target.removeprefix("file://"))))
        ok = osc.xdg_open(arg)
        summary = (f"открыл {target}" if ok else f"не открылось: {target}") if ru else \
            (f"opened {target}" if ok else f"failed to open {target}")
        return ToolResult(ok, f"xdg-open {'started' if ok else 'failed'} for {arg}", summary, verified=None,
                          left_to=urllib.parse.urlsplit(target).netloc if kind == "url" and ok else None)
    entry = osc.find_app(target)
    if entry is None:
        msg = f"application not found: {target}"
        return ToolResult(False, msg, (f"нет приложения «{target}»" if ru else f"no app “{target}”"))
    started, seen = osc.launch(entry)
    if not started:
        return ToolResult(False, f"failed to launch {entry.name}", (f"не запустилось: {entry.name}" if ru
                                                                   else f"failed: {entry.name}"))
    note = "" if seen else (" (процесс пока не виден)" if ru else " (process not seen yet)")
    return ToolResult(True, f"launched {entry.name} ({entry.id}); process seen: {seen}",
                      (f"запустил {entry.name}{note}" if ru else f"launched {entry.name}{note}"), verified=seen)


# ---------------------------------------------------------------------------
# notify / settings.theme

def notify(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    title = str(args.get("title") or "Джексон")[:120]
    body = str(args.get("body") or "")[:500]
    ok = _os(ctx).notify(title, body)
    return ToolResult(ok, "notification shown" if ok else "notify-send is not available",
                      title if ok else ("уведомления недоступны" if _ru(ctx) else "notifications unavailable"),
                      verified=None)


def _theme_arg(args: dict[str, Any]) -> str:
    raw = str(args.get("theme") or "").strip().lower()
    return THEME_ALIASES.get(raw, raw)


def _assess_theme(ctx: ToolContext, args: dict[str, Any]) -> Assessment:
    theme = _theme_arg(args)
    if theme not in THEMES:
        return Assessment(T1, blocked=f"unknown theme {theme!r}; use one of {sorted(THEMES)}")
    return Assessment(T1, preview=(f"Тема: {theme}" if _ru(ctx) else f"Theme: {theme}"), scope="theme")


def apply_theme(ctx: ToolContext, theme: str) -> ToolResult:
    ru = _ru(ctx)
    prev = ctx.svoya.theme_current()
    ok, out = ctx.svoya.theme_apply(theme)
    if not ok:
        return ToolResult(False, f"sos theme apply failed: {out}",
                          (f"тема не сменилась: {out}" if ru else f"theme not changed: {out}"))
    now = ctx.svoya.theme_current()
    verified = now is not None and (now == theme or theme == "auto")
    undo = [UndoSpec("theme", (f"тема {prev} → {theme}" if ru else f"theme {prev} → {theme}"),
                     {"prev": prev or "auto", "new": theme})] if prev and prev != theme else []
    summary = (f"тема: {theme}" if ru else f"theme: {theme}") + ("" if verified else " (?)")
    return ToolResult(True, f"theme applied: {theme}; theme.json now says {now!r}", summary, undo=undo,
                      verified=verified)


def settings_theme(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    return apply_theme(ctx, _theme_arg(args))


def tools() -> list[Tool]:
    return [
        Tool("system.info", "Hardware and system status: GPU/VRAM, disks, memory, CPU, battery.",
             obj({"section": {"type": "string", "enum": ["all", "gpu", "disk", "memory", "cpu", "battery", "status"]}}),
             system_info, T0, frozenset({"read"}), None, {"ru": "о системе", "en": "system info"}),
        Tool("apps.open", "Launch an installed application by name, or open a file/folder/URL with the default app.",
             obj({"target": {"type": "string", "description": "App name (e.g. firefox), path or URL"}}, ["target"]),
             apps_open, T1, frozenset({"exec"}), _assess_open, {"ru": "открыть", "en": "open"}),
        Tool("notify", "Show a desktop notification.",
             obj({"title": {"type": "string"}, "body": {"type": "string"}}, ["title"]),
             notify, T0, frozenset({"read"}), None, {"ru": "уведомление", "en": "notification"}),
        Tool("settings.theme", "Switch the SOS theme: graphite (dark), paper (light), phosphor, auto.",
             obj({"theme": {"type": "string", "enum": sorted(THEMES | {"dark", "light"})}}, ["theme"]),
             settings_theme, T1, frozenset({"write"}), _assess_theme, {"ru": "тема", "en": "theme"}),
    ]
