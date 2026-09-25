# SPDX-License-Identifier: Apache-2.0
"""`jackson doctor`: is everything Jackson depends on in place?"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import stat
import sys
from typing import Callable

from .i18n import fmt_number


def run_doctor(lang: str = "ru", online: bool = False, start_mcp: bool = False,
               write: Callable[[str], None] | None = None) -> int:
    from .app import Jackson
    from .audit import AuditLog
    from .client import service_running

    out = write or (lambda line: print(line))
    ru = lang == "ru"
    problems = 0

    def ok(text: str) -> None:
        out(f"✓ {text}")

    def warn(text: str) -> None:
        out(f"! {text}")

    def bad(text: str) -> None:
        nonlocal problems
        problems += 1
        out(f"✗ {text}")

    v = sys.version_info
    (ok if v >= (3, 11) else bad)(f"Python {v.major}.{v.minor}.{v.micro}")
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        ok(f"SQLite {sqlite3.sqlite_version} + FTS5")
    except sqlite3.Error as exc:
        bad(f"SQLite FTS5: {exc}")

    app = Jackson()
    cfg = app.config
    if cfg.sources:
        ok(("настройки: " if ru else "settings: ") + ", ".join(cfg.sources))
    else:
        warn(("настроек нет, работаю на умолчаниях (" if ru else "no settings file, using defaults (")
             + str(app.paths.config_file) + ")")
    for w in cfg.warnings:
        warn(w)

    running = asyncio.run(service_running(app.paths))
    if running:
        ok((f"{app.name(lang)} работает в фоне: " if ru else f"{app.name(lang)} is running in the background: ")
           + str(app.paths.socket))
    else:
        warn((f"{app.name(lang)} не запущен в фоне (systemctl --user start jacksond) — CLI ответит сам"
              if ru else f"{app.name(lang)} is not running in the background (systemctl --user start jacksond)"
                         " — the CLI answers itself"))
    ai = app.ai_state()
    if not ai["enabled"]:
        warn(("ИИ выключен (" if ru else "AI is switched off (") + str(ai["off"]) + ") — `sos ai on`")
    rd = app.paths.runtime_dir
    if rd.exists():
        mode = stat.S_IMODE(os.stat(rd).st_mode)
        (ok if mode & 0o077 == 0 else bad)(f"{rd} {mode:04o}")

    sb_ok, sb_why = app.sandbox.probe()
    (ok if sb_ok else bad)(("песочница bwrap: " if ru else "bwrap sandbox: ") + sb_why
                           + ("" if sb_ok else (" — команды будут требовать подтверждения" if ru
                                                else " — commands will need confirmation")))
    if app.runner.which("secret-tool"):
        ok("secret-tool (keyring)")
    else:
        warn("secret-tool: " + ("нет — ключи только из secrets.env" if ru else "missing — keys only from secrets.env"))
    sf = app.paths.secrets_file
    if sf.exists():
        mode = stat.S_IMODE(os.stat(sf).st_mode)
        (ok if mode & 0o077 == 0 else bad)(f"{sf} {mode:04o}" + ("" if mode & 0o077 == 0 else " → chmod 600"))
    (ok if app.svoya.available() else warn)(
        ("команда sos: " if ru else "sos command: ") + (app.svoya.binary or ("нет (снимки и темы недоступны)" if ru
                                                                          else "missing (no snapshots or themes)")))
    if app.runner.which("snapper"):
        ok("snapper")

    app.refresh_health(timeout=1.5)
    any_model = False
    for name, prov in app.providers.items():
        pc = prov.cfg
        if pc.local:
            h = app.health.get(name)
            if h.ok:
                any_model = True
                models = ", ".join(h.models[:4]) or "?"
                ok(f"{pc.display} ({pc.base_url}): {'загружается' if h.loading and ru else 'loading' if h.loading else models}"
                   f" · {fmt_number(h.latency_ms, lang)} ms")
            else:
                warn(f"{pc.display} ({pc.base_url}): {h.detail}")
        else:
            has = app.key_check(name)
            if not has:
                out(f"· {pc.display}: " + ("нет ключа" if ru else "no key"))
                continue
            if online:
                h = prov.health(timeout=4.0)
                (ok if h.ok else bad)(f"{pc.display}: {h.detail}")
                any_model = any_model or h.ok
            else:
                ok(f"{pc.display}: " + ("ключ есть (проверка сети: --online)" if ru else "key found (network check: --online)"))
                any_model = True
    if not any_model:
        bad("нет ни одной доступной модели" if ru else "no model is available")
    if cfg.route.policy == "local-only" and not any(app.health.get(n).ok for n in app.local_provider_names()):
        warn("политика «только локально», но локальная модель не отвечает: `sos models serve`" if ru
             else "policy is local-only but no local model answers: `sos models serve`")

    res = AuditLog(app.paths.audit_file, app.paths.audit_head).verify()
    (ok if res.ok else bad)((f"журнал: {res.count} записей" if ru else f"audit log: {res.count} entries")
                            + ("" if res.ok else f" — {res.reason}"))
    if app.memory is not None:
        try:
            app.memory.ensure()
            mode = ("Obsidian: " + str(app.memory.vault)) if app.memory.obsidian else str(app.memory.dir)
            ok(("память: " if ru else "memory: ") + mode)
        except OSError as exc:
            bad(f"memory: {exc}")

    backends = ["wpctl", "brightnessctl", "nmcli", "loginctl", "grim", "notify-send", "gtk-launch", "systemd-run"]
    missing = [b for b in backends if not app.runner.which(b)]
    if missing:
        warn(("нет для быстрых команд: " if ru else "missing for quick commands: ") + ", ".join(missing))
    else:
        ok("быстрые команды: всё на месте" if ru else "quick-command backends: all present")

    if start_mcp and cfg.mcp_servers:
        app.mcp.start_all()
        for row in app.mcp.status():
            (ok if row["running"] and not row["blocked"] else bad)(
                f"MCP {row['name']}: {row['era']} {row['version']} · tools {len(row['tools'])}"
                + (f" · blocked {sorted(row['blocked'])}" if row["blocked"] else "")
                + (f" · {row['error']}" if row["error"] else ""))
        app.close()
    elif cfg.mcp_servers:
        out(f"· MCP: {len(cfg.mcp_servers)} " + ("серверов (проверка: --mcp)" if ru else "servers (check: --mcp)"))
    return 1 if problems else 0
