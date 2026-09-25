# SPDX-License-Identifier: Apache-2.0
"""`jackson` / `j` — ask Jackson from a terminal, and manage him.

    j найди мои датасеты                 stream an answer (Markdown) to stdout
    git diff | j "что тут не так?"       stdin becomes selected text
    j -                                  the question itself comes from stdin
    j                                    interactive chat (Ctrl+D to leave)

Decorations (route, tool rows, approvals, the meta footer) go to stderr, the answer to stdout,
so `j … > answer.md` stays clean. Subcommands: status, models, memory, notes, audit, undo,
approve, route, persona, doctor, mcp, version.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import select
import signal
import stat
import sys
from pathlib import Path
from typing import Any, TextIO

from . import __version__
from .i18n import fmt_cost, fmt_number, meta_line, norm_lang
from .paths import Paths

SUBCOMMANDS = ("ask", "status", "models", "memory", "notes", "audit", "undo", "approve", "route", "persona",
               "avatar", "doctor", "mcp", "version", "help")

# Graphite defaults (themes/graphite.toml); theme.json overrides them when present.
# Semantic colors never reuse the accent (DESIGN §10): warn is yellow, not amber.
DEFAULT_COLORS = {"accent": "#ffb547", "ok": "#8fd48a", "warn": "#f5cf52", "bad": "#ff6b6b", "cloud": "#7ad3e6",
                  "textDim": "#9d9a92", "textFaint": "#67655f"}


# ---------------------------------------------------------------------------
# terminal style (design/DESIGN.md: one signal color, mono meta lines, honest status)

class Style:
    def __init__(self, stream: TextIO, paths: Paths | None = None, force: bool | None = None) -> None:
        self.stream = stream
        if force is not None:
            self.enabled = force
        else:
            self.enabled = (hasattr(stream, "isatty") and stream.isatty() and "NO_COLOR" not in os.environ
                            and os.environ.get("TERM") != "dumb")
        self.truecolor = os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")
        self.colors = dict(DEFAULT_COLORS)
        if paths is not None:
            try:
                data = json.loads(paths.theme_json.read_text(encoding="utf-8"))
                for key in self.colors:
                    value = data.get(key) or (data.get("color") or {}).get(key)
                    if isinstance(value, str) and value.startswith("#") and len(value) in (7, 9):
                        self.colors[key] = "#" + value[-6:]
            except (OSError, ValueError, AttributeError):
                pass

    def _code(self, role: str) -> str:
        hexcolor = self.colors.get(role, "#ffffff")
        r, g, b = int(hexcolor[1:3], 16), int(hexcolor[3:5], 16), int(hexcolor[5:7], 16)
        if self.truecolor:
            return f"\x1b[38;2;{r};{g};{b}m"
        idx = 16 + 36 * round(r / 255 * 5) + 6 * round(g / 255 * 5) + round(b / 255 * 5)
        return f"\x1b[38;5;{idx}m"

    def color(self, text: str, role: str) -> str:
        return f"{self._code(role)}{text}\x1b[0m" if self.enabled else text

    def dim(self, text: str) -> str:
        return self.color(text, "textFaint") if self.enabled else text

    def bold(self, text: str) -> str:
        return f"\x1b[1m{text}\x1b[0m" if self.enabled else text

    def dot(self, role: str) -> str:
        return self.color("●", role)


def _lang(args_lang: str | None = None) -> str:
    if args_lang:
        return norm_lang(args_lang)
    try:
        from .config import load_config
        return load_config(Paths.from_env()).language
    except Exception:
        return "ru"


def say(lang: str, ru: str, en: str) -> str:
    return ru if lang == "ru" else en


def my_name(lang: str, paths: Paths | None = None) -> str:
    """Jackson's name from ~/.config/svoya/avatar.json (default «Джексон» / "Jackson")."""
    from . import avatar as avatar_mod
    return avatar_mod.load((paths or Paths.from_env()).avatar_file).display_name(lang)


# ---------------------------------------------------------------------------
# asking

class Renderer:
    def __init__(self, conn: Any, turn_id: str, lang: str, out: TextIO, err: TextIO, json_mode: bool,
                 paths: Paths) -> None:
        self.conn = conn
        self.turn_id = turn_id
        self.lang = lang
        self.out = out
        self.err = err
        self.json_mode = json_mode
        self.so = Style(out, paths)
        self.se = Style(err, paths)
        self.mid_line = False
        self.route_local = True
        self.shared_tty = self._same_tty()

    def _same_tty(self) -> bool:
        try:
            return os.isatty(self.out.fileno()) and os.isatty(self.err.fileno())
        except (AttributeError, OSError, ValueError):
            return False

    def _break_line(self) -> None:
        if self.mid_line:
            self.out.write("\n")
            self.out.flush()
            self.mid_line = False

    def meta(self, text: str) -> None:
        if self.shared_tty:
            self._break_line()
        self.err.write(text + "\n")
        self.err.flush()

    async def run(self) -> int:
        while True:
            ev = await self.conn.recv()
            if ev is None:
                self.meta(self.se.color("✗ " + say(self.lang, "связь оборвалась", "lost the connection"), "bad"))
                return 1
            if ev.get("id") not in (self.turn_id, None) or ev.get("type") in ("state", "welcome", "pong"):
                continue
            if self.json_mode:
                self.out.write(json.dumps(ev, ensure_ascii=False) + "\n")
                self.out.flush()
            kind = ev.get("type")
            if kind == "route" and not self.json_mode:
                self.route_local = bool(ev.get("local"))
                model = str(ev.get("model") or "")
                if not ev.get("local"):
                    model = f"{ev.get('label') or ev.get('provider')} · {model}"
                dot = self.se.dot("ok" if ev.get("local") else "cloud")
                self.meta(f"{dot} {self.se.dim(model + ' — ' + str(ev.get('reason') or ''))}")
            elif kind == "token" and not self.json_mode:
                text = str(ev.get("text") or "")
                self.out.write(text)
                self.out.flush()
                self.mid_line = bool(text) and not text.endswith("\n")
            elif kind == "tool" and not self.json_mode:
                if ev.get("state") in ("done", "failed") and not str(ev.get("name", "")).startswith("fast."):
                    ok = ev.get("state") == "done"
                    mark = self.se.color("✓", "ok") if ok else self.se.color("✗", "bad")
                    summary = str(ev.get("summary") or "")
                    self.meta(f"  {mark} {self.se.dim(str(ev.get('name')) + (' — ' + summary if summary else ''))}")
            elif kind == "approval":
                await self.approval(ev)
            elif kind == "done":
                if not self.json_mode:
                    self._break_line()
                    self.footer(ev)
                return 0
            elif kind == "error":
                if not self.json_mode:
                    if ev.get("aiOff"):  # a calm switch state, not a failure
                        self.meta(self.se.color("⏻ " + str(ev.get("message")), "warn"))
                    else:
                        self.meta(self.se.color("✗ " + str(ev.get("message") or "error"), "bad"))
                return 1

    def footer(self, ev: dict[str, Any]) -> None:
        usage = ev.get("usage") or {}
        tokens = int(usage.get("inTokens") or 0) + int(usage.get("outTokens") or 0)
        left = bool(ev.get("leftMachine"))
        text = meta_line(float(ev.get("latencyMs") or 0), tokens, ev.get("costEur"), left, ev.get("leftTo") or [],
                         self.lang, bool(ev.get("costEstimated")))
        if ev.get("cancelled"):
            text = say(self.lang, "остановлено · ", "stopped · ") + text
        actions = ev.get("actions") or []
        dot = self.se.dot("cloud" if left else "ok")
        self.meta(f"{dot} {self.se.dim(text)}")
        if actions:
            self.meta(self.se.dim(say(self.lang, f"  откатить: jackson undo {actions[-1]}  (или Super+Z)",
                                      f"  undo: jackson undo {actions[-1]}  (or Super+Z)")))

    async def approval(self, ev: dict[str, Any]) -> None:
        se = self.se
        tier = ev.get("tier")
        decisions = ev.get("decisions") or ["once", "always-project", "deny"]
        title = say(self.lang, "нужно разрешение", "permission needed")
        lines = [se.color(f"┌─ {title} · T{tier} · {ev.get('name')}", "accent")]
        for line in str(ev.get("preview") or "").splitlines()[:40]:
            lines.append(se.color("│ ", "accent") + line)
        for reason in ev.get("reasons") or []:
            lines.append(se.color("│ ", "accent") + se.dim(say(self.lang, "почему: ", "why: ") + str(reason)))
        options = []
        labels = {"once": say(self.lang, "[1] разрешить один раз", "[1] allow once"),
                  "always-project": say(self.lang, "[2] всегда в этом проекте", "[2] always in this project"),
                  "deny": say(self.lang, "[3] отклонить", "[3] deny")}
        for d in ("once", "always-project", "deny"):
            if d in decisions:
                options.append(labels[d])
        lines.append(se.color("└─ ", "accent") + "  ".join(options))
        lines.append(se.dim(f"   id: {ev.get('callId')}"))
        self.meta("\n".join(lines))
        decision = await asyncio.to_thread(self._read_decision, decisions, str(ev.get("callId")))
        if decision is None:
            self.meta(se.dim(say(self.lang,
                                 f"   нет терминала — ответь из другого окна: jackson approve {ev.get('callId')} once|deny",
                                 f"   no terminal — answer elsewhere: jackson approve {ev.get('callId')} once|deny")))
            return
        await self.conn.send({"type": "approve", "id": self.turn_id, "callId": ev.get("callId"),
                              "decision": decision})

    def _read_decision(self, decisions: list[str], call_id: str) -> str | None:
        try:
            tty = open("/dev/tty", "r+", encoding="utf-8")
        except OSError:
            return None
        with tty:
            while True:
                tty.write("   › ")
                tty.flush()
                answer = tty.readline()
                if not answer:
                    return "deny"
                a = answer.strip().lower()
                if a in ("1", "y", "yes", "д", "да", "once", "ok", "ок"):
                    return "once"
                if a in ("2", "a", "always", "в", "всегда") and "always-project" in decisions:
                    return "always-project"
                if a in ("3", "n", "no", "н", "нет", "deny", ""):
                    return "deny"


def _new_turn_id() -> str:
    return "t-" + secrets.token_hex(4)


async def _ask(question: str, context: dict[str, Any], opts: argparse.Namespace) -> int:
    from .client import open_connection

    paths = Paths.from_env()
    err = sys.stderr
    try:
        conn = await open_connection(paths, allow_embedded=not opts.no_local_fallback)
    except (OSError, asyncio.TimeoutError) as exc:
        lang = _lang(opts.lang)
        name = my_name(lang, paths)
        err.write(say(lang, f"✗ {name} недоступен: {exc}\n", f"✗ {name} is unavailable: {exc}\n"))
        return 3
    try:
        welcome = await conn.hello("jackson-cli", opts.lang)
        lang = norm_lang((welcome or {}).get("lang") or opts.lang or "ru")
        if opts.verbose and conn.in_process:
            name = str((welcome or {}).get("name") or my_name(lang, paths))
            err.write(Style(err, paths).dim(say(lang, f"{name} не запущен в фоне — отвечаю прямо здесь.\n",
                                                f"{name} is not running in the background — answering here.\n")))
        return await _turn_loop(conn, question, context, opts, lang, paths)
    finally:
        await conn.close()


async def _turn_loop(conn: Any, question: str | None, context: dict[str, Any], opts: argparse.Namespace,
                     lang: str, paths: Paths) -> int:
    loop = asyncio.get_running_loop()
    interactive = question is None
    code = 0
    first = True
    while True:
        if interactive:
            prompt = Style(sys.stderr, paths).color("› ", "accent")
            try:
                line = await asyncio.to_thread(_input, prompt)
            except EOFError:
                sys.stderr.write("\n")
                return code
            line = line.strip()
            if not line:
                continue
            if line in ("exit", "quit", "выход", ":q"):
                return code
            text = line
        else:
            text = question or ""
        turn_id = _new_turn_id()
        msg: dict[str, Any] = {"type": "ask", "id": turn_id, "text": text}
        if context and first:
            msg["context"] = context
        if opts.route:
            msg["route"] = opts.route
        if opts.new and first:
            msg["new"] = True
        first = False
        await conn.send(msg)
        renderer = Renderer(conn, turn_id, lang, sys.stdout, sys.stderr, opts.json, paths)
        interrupted = {"n": 0}

        def on_sigint() -> None:
            interrupted["n"] += 1
            if interrupted["n"] == 1:
                loop.create_task(conn.send({"type": "cancel", "id": turn_id}))
            else:
                raise KeyboardInterrupt

        try:
            loop.add_signal_handler(signal.SIGINT, on_sigint)
        except (NotImplementedError, RuntimeError):
            pass
        try:
            code = await renderer.run()
        finally:
            try:
                loop.remove_signal_handler(signal.SIGINT)
            except (NotImplementedError, RuntimeError):
                pass
        if interrupted["n"]:
            code = 130
        if not interactive:
            return code


def _input(prompt: str) -> str:
    sys.stderr.write(prompt)
    sys.stderr.flush()
    line = sys.stdin.readline()
    if not line:
        raise EOFError
    return line


def read_stdin(explicit: bool, lang: str = "ru", patience: float = 2.0) -> str | None:
    """stdin as input: always for `j -`; otherwise only when it is a pipe or a file.

    With a question on the command line, a pipe that stays silent for *patience* seconds is
    treated as "no input" — an inherited, never-closing pipe (some runners do that) must not
    hang `j`. Producers like `make 2>&1 | j "почему упало?"` start writing right away and are
    then read to the end. `--no-stdin` skips stdin entirely.
    """
    stream = sys.stdin
    if stream is None:
        return None
    try:
        if stream.isatty():
            return stream.read() if explicit else None
        mode = os.fstat(stream.fileno()).st_mode
    except (OSError, ValueError):
        return None
    if not explicit and not (stat.S_ISFIFO(mode) or stat.S_ISREG(mode)):
        return None  # e.g. /dev/null or a socket from a service manager
    if stat.S_ISFIFO(mode) and not explicit:
        ready, _, _ = select.select([stream], [], [], patience)
        if not ready:
            return None
    return stream.read()


def cmd_ask(words: list[str], opts: argparse.Namespace) -> int:
    context: dict[str, Any] = {"cwd": os.getcwd()}
    question: str | None = " ".join(words).strip()
    lang = norm_lang(opts.lang or "ru")
    if question == "-":
        question = (read_stdin(True, lang) or "").strip()
        if not question:
            return 2
    elif not opts.no_stdin:
        # `echo вопрос | j` → the question itself comes from stdin, so wait for it.
        data = read_stdin(not question and not sys.stdin.isatty(), lang)
        if data and data.strip():
            context["selection"] = data[:200_000]
    if not question:
        if context.get("selection"):
            question, context = str(context.pop("selection")).strip(), {"cwd": os.getcwd()}
        elif sys.stdin is not None and sys.stdin.isatty():
            question = None  # interactive chat
        else:
            return 2
    if opts.screenshot:
        context["screenshot"] = str(Path(opts.screenshot).expanduser().resolve())
    try:
        return asyncio.run(_ask(question, context, opts))
    except KeyboardInterrupt:
        return 130


# ---------------------------------------------------------------------------
# subcommands

def _app() -> Any:
    from .app import Jackson
    return Jackson()


async def _service_request(msg: dict[str, Any], want: tuple[str, ...], lang: str | None = None,
                           timeout: float = 30.0) -> list[dict[str, Any]] | None:
    """Send one message to the running service; collect events until one of *want* arrives."""
    from .client import connect
    paths = Paths.from_env()
    try:
        conn = await connect(paths.socket, timeout=0.5)
    except (OSError, asyncio.TimeoutError):
        return None
    try:
        await conn.hello("jackson-cli", lang)
        await conn.send(msg)
        events = []
        while True:
            ev = await conn.recv(timeout=timeout)
            if ev is None:
                return events
            if ev.get("type") == "state" and ev.get("id") not in (None, msg.get("id")):
                continue
            events.append(ev)
            if ev.get("type") in want:
                return events
    finally:
        await conn.close()


def cmd_status(args: argparse.Namespace) -> int:
    lang = _lang(args.lang)
    out = Style(sys.stdout, Paths.from_env())
    events = asyncio.run(_service_request({"type": "status", "id": "status"}, ("status",), lang))
    status = next((e for e in events or [] if e.get("type") == "status"), None)
    running = status is not None
    if status is None:
        app = _app()
        status = {"version": __version__, **app.engine.status(), "persona": app.persona(lang),
                  "models": app.router.model_table(), "name": app.name(lang), "avatar": app.avatar.to_event(),
                  "ai": app.ai_state()}
    if args.json:
        print(json.dumps({"running": running, **status}, ensure_ascii=False, indent=1))
        return 0
    persona = status.get("persona") or {}
    name = str(status.get("name") or my_name(lang))
    look = status.get("avatar") or {}
    who = say(lang, "кот", "cat") if look.get("character") == "cat" else say(lang, "чёрт", "imp")
    print(out.bold(name) + out.dim(f" · {persona.get('name', '')} · {who} · {status.get('version')}"))
    ai = status.get("ai") or {}
    if ai and not ai.get("enabled", True):
        how = "sos ai on --system" if ai.get("off") == "system" else "sos ai on"
        print(out.color(say(lang, f"ИИ         выключен — только быстрые команды (включить: {how})",
                            f"AI         off — quick commands only (turn on: {how})"), "warn"))
    if running:
        state = out.color(say(lang, "работает", "running"), "ok")
    else:
        state = out.dim(say(lang, "не запущен (systemctl --user start jacksond)",
                            "not running (systemctl --user start jacksond)"))
    print(out.dim(say(lang, "в фоне     ", "background ")) + state)
    route = status.get("route") or {}
    pol = {"local-only": say(lang, "только локально", "local only"), "eu": say(lang, "ЕС", "EU"),
           "any": say(lang, "любая", "any")}.get(route.get("policy"), route.get("policy"))
    mode = {"auto": say(lang, "авто", "auto"), "local": say(lang, "локально", "local"),
            "cloud": say(lang, "облако", "cloud")}.get(route.get("mode"), route.get("mode"))
    print(out.dim(say(lang, "маршрут    ", "route      ")) + f"{mode} · "
          + say(lang, "политика: ", "policy: ") + str(pol) + (say(lang, " · офлайн", " · offline") if route.get("offline") else ""))
    ready = [m for m in status.get("models") or [] if m.get("available")]
    if ready:
        m = ready[0]
        where = say(lang, "локально", "local") if m.get("local") else m.get("label")
        print(out.dim(say(lang, "модель     ", "model      ")) + f"{out.dot('ok' if m.get('local') else 'cloud')} "
              f"{where} · {m.get('model')}" + out.dim(f"  (+{len(ready) - 1})" if len(ready) > 1 else ""))
    else:
        print(out.dim(say(lang, "модель     ", "model      ")) + out.color(say(lang, "нет доступных", "none available"), "warn"))
    budget = route.get("dailyBudgetEur")
    print(out.dim(say(lang, "сегодня    ", "today      ")) + fmt_cost(status.get("spentTodayEur") or 0, lang)
          + (f" / {fmt_cost(budget, lang)}" if budget is not None else "")
          + say(lang, f" · запросов наружу: {status.get('leftMachineToday', 0)}",
                f" · requests that left: {status.get('leftMachineToday', 0)}"))
    print(out.dim(say(lang, "защита     ", "safety     ")) + f"bwrap {'✓' if status.get('sandbox') else '✗'} · "
          f"sos {'✓' if status.get('svoya') else '✗'}")
    for p in status.get("pendingApprovals") or []:
        print(out.color(say(lang, f"ждёт ответа  {p['callId']} · {p['name']} · T{p['tier']}",
                            f"waiting      {p['callId']} · {p['name']} · T{p['tier']}"), "accent"))
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    lang = _lang(args.lang)
    app = _app()
    app.refresh_health(timeout=1.0)
    rows = app.router.model_table()
    from .providers import price_for
    for r in rows:
        (p_in, p_out), known = price_for(app.config, r["provider"], r["model"], r["local"])
        r["priceEurPerMTok"] = [p_in, p_out]
        r["priceKnown"] = known
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    out = Style(sys.stdout, app.paths)
    for r in rows:
        dot = out.dot("ok" if r["available"] else "bad")
        where = say(lang, "локально", "local") if r["local"] else f"{r['label']} ({r.get('region', '')})"
        price = say(lang, "бесплатно", "free") if r["local"] else \
            f"{fmt_number(r['priceEurPerMTok'][0], lang, 2)}/{fmt_number(r['priceEurPerMTok'][1], lang, 2)} € " + \
            say(lang, "за 1 млн", "per 1M")
        detail = str(r.get("detail") or "")
        if lang == "ru":
            detail = {"no key": "нет ключа", "disabled": "выключена", "loading": "загружается"}.get(detail, detail)
        state = say(lang, "готова", "ready") if r["available"] else detail
        print(f"{dot} {r['id']:<38} {out.dim(where):<20} {out.dim(price)}  {out.dim(state)}")
    return 0


def cmd_memory(args: argparse.Namespace) -> int:
    lang = _lang(args.lang)
    app = _app()
    mem = app.memory
    if mem is None:
        print(say(lang, "Память выключена в настройках.", "Memory is disabled in the settings."))
        return 1
    mem.ensure()
    action = args.action
    if action == "path":
        print(mem.dir)
        if mem.obsidian:
            print(say(lang, f"хранилище Obsidian: {mem.vault}", f"Obsidian vault: {mem.vault}"))
        return 0
    if action == "show":
        names = [args.arg] if args.arg else ["USER.md", "MEMORY.md"]
        for name in names:
            try:
                text = mem.read(name)
            except Exception as exc:
                print(f"✗ {exc}", file=sys.stderr)
                return 1
            print(Style(sys.stdout).dim(f"── {mem.path_of(name)}"))
            print(text.rstrip() or say(lang, "(пусто)", "(empty)"))
        return 0
    if action == "search":
        hits = mem.search(args.arg or "", limit=args.limit)
        for h in hits:
            print(f"{h.file}:{h.line}: {h.text}")
        if not hits:
            print(say(lang, "Ничего не нашёл.", "Nothing found."))
        return 0
    if action == "forget":
        query = args.arg or ""
        from .memory import normalize
        found = []
        for name in ("USER.md", "MEMORY.md"):
            for line in mem.read(name).splitlines():
                if line.lstrip().startswith(("- ", "* ")) and normalize(query) in normalize(line):
                    found.append(f"{name}: {line.strip()}")
        if not found:
            print(say(lang, "В памяти нет такого.", "Nothing matches in memory."))
            return 1
        print("\n".join(found))
        if not args.yes:
            if not sys.stdin.isatty():
                print(say(lang, "Добавь --yes, чтобы забыть.", "Add --yes to forget."), file=sys.stderr)
                return 1
            answer = input(say(lang, f"Забыть {len(found)}? [y/N] ", f"Forget {len(found)}? [y/N] ")).strip().lower()
            if answer not in ("y", "yes", "д", "да"):
                return 1
        from .tools.base import UndoSpec
        from .i18n import entries_word, t
        changes = mem.forget(query)
        ids = []
        for c in changes:
            summary = t("memory.forgot", lang, n=len(c.lines), entries=entries_word(len(c.lines), lang))
            a = app.undo.register(UndoSpec("memory", summary, c.undo_data()), "", "cli")
            app.audit.append("memory", op="forget", file=c.file, action=a.id, source="cli")
            ids.append(a.id)
        print(say(lang, f"Забыл. Вернуть: jackson undo {ids[-1]}", f"Forgotten. Undo: jackson undo {ids[-1]}"))
        return 0
    return 2


def cmd_notes(args: argparse.Namespace) -> int:
    lang = _lang(args.lang)
    app = _app()
    mem = app.memory
    if mem is None:
        return 1
    if args.action == "search":
        for h in mem.search(args.arg or "", limit=args.limit):
            print(f"{h.file}:{h.line}: {h.text}")
        return 0
    if args.action == "read":
        path = mem.resolve_note(args.arg or "")
        if path is None:
            print(say(lang, "Не нашёл заметку.", "Note not found."), file=sys.stderr)
            return 1
        print(path.read_text(encoding="utf-8", errors="replace"), end="")
        return 0
    if args.action == "where":
        print(mem.root)
        return 0
    return 2


def cmd_audit(args: argparse.Namespace) -> int:
    lang = _lang(args.lang)
    from .audit import AuditLog
    paths = Paths.from_env()
    log = AuditLog(paths.audit_file, paths.audit_head)
    if args.action == "tail":
        for e in log.tail(args.n):
            print(json.dumps(e, ensure_ascii=False))
        return 0
    res = log.verify()
    out = Style(sys.stdout, paths)
    if res.ok:
        print(out.color("✓", "ok") + say(lang, f" журнал цел: {fmt_number(res.count, lang)} записей, "
                                              f"последний хеш {res.last_hash[:16]}…",
                                         f" audit log intact: {res.count} entries, last hash {res.last_hash[:16]}…"))
        return 0
    where = say(lang, f"строка {res.bad_line}", f"line {res.bad_line}") if res.bad_line else ""
    print(out.color("✗", "bad") + say(lang, f" журнал повреждён {where}: {res.reason}",
                                      f" audit log is broken {where}: {res.reason}"))
    return 1


def cmd_undo(args: argparse.Namespace) -> int:
    lang = _lang(args.lang)
    if args.list:
        app = _app()
        out = Style(sys.stdout, app.paths)
        for a in app.undo.list(limit=args.n):
            mark = out.dim("↺") if a.undone else out.dim("·") if a.auto else out.color("•", "accent")
            summary = out.dim(a.summary) if a.auto else a.summary
            print(f"{mark} {a.id}  {out.dim(a.ts)}  {summary}" + (out.dim(say(lang, "  (отменено)", "  (undone)"))
                                                                if a.undone else ""))
        return 0
    msg: dict[str, Any] = {"type": "undo", "id": "u-" + secrets.token_hex(3)}
    if args.action_id:
        msg["actionId"] = args.action_id
    events = asyncio.run(_service_request(msg, ("done", "error"), lang))
    if events is None:  # not running in the background: undo directly
        outcome = _app().undo.undo(args.action_id, lang)
        print(("✓ " if outcome.ok else "✗ ") + outcome.message)
        return 0 if outcome.ok else 1
    last = events[-1] if events else {}
    if last.get("type") == "done":
        tok = next((e.get("text") for e in events if e.get("type") == "token"), "")
        print("✓ " + str(tok))
        return 0
    print("✗ " + str(last.get("message", "?")))
    return 1


def cmd_approve(args: argparse.Namespace) -> int:
    lang = _lang(args.lang)
    try:
        events = asyncio.run(_service_request({"type": "approve", "id": "approve", "callId": args.call_id,
                                               "decision": args.decision}, ("error",), lang, timeout=1.0))
    except asyncio.TimeoutError:
        events = []  # no error within a second: the approval was accepted
    if events is None:
        name = my_name(lang)
        print(say(lang, f"{name} не запущен в фоне — отвечать некому.", f"{name} is not running — nothing to answer."),
              file=sys.stderr)
        return 1
    err = next((e for e in events if e.get("type") == "error"), None)
    if err:
        print("✗ " + str(err.get("message")), file=sys.stderr)
        return 1
    print("✓")
    return 0


def cmd_route(args: argparse.Namespace) -> int:
    lang = _lang(args.lang)
    from .config import load_config, set_toml_value
    paths = Paths.from_env()
    cfg = load_config(paths)
    if args.action in (None, "show"):
        rc = cfg.route
        print(json.dumps({"mode": rc.default, "policy": rc.policy, "offline": rc.offline,
                          "dailyBudgetEur": rc.daily_budget_eur, "preferLocal": rc.prefer_local,
                          "task": rc.task}, ensure_ascii=False, indent=1))
        return 0
    key, value = args.key, args.value
    parsed: Any
    if key == "policy" and value in ("local-only", "eu", "any"):
        parsed = value
    elif key in ("default", "mode") and value in ("auto", "local", "cloud"):
        key, parsed = "default", value
    elif key == "offline" and value in ("on", "off", "true", "false"):
        parsed = value in ("on", "true")
    elif key == "budget":
        try:
            parsed = float(value.replace(",", "."))
        except ValueError:
            return 2
        key = "daily_budget_eur"
    else:
        print(say(lang, "Можно: policy local-only|eu|any · default auto|local|cloud · offline on|off · budget <евро>",
                  "Use: policy local-only|eu|any · default auto|local|cloud · offline on|off · budget <eur>"),
              file=sys.stderr)
        return 2
    prev = getattr(cfg.route, key)
    set_toml_value(paths.config_file, "route", key, parsed)
    from .audit import AuditLog
    from .trash import Trash
    from .undo import UndoLog
    from .tools.base import UndoSpec
    undo = UndoLog(paths.actions_file, Trash(paths.trash_dir))
    a = undo.register(UndoSpec("config", f"route.{key}: {prev} → {parsed}",
                               {"table": "route", "key": key, "prev": prev, "new": parsed}), "", "cli")
    AuditLog(paths.audit_file, paths.audit_head).append("settings", key=f"route.{key}", value=parsed, prev=prev,
                                                        source="cli", action=a.id)
    print(f"✓ route.{key} = {parsed}" + Style(sys.stdout).dim(say(lang, f"  (вернуть: jackson undo {a.id})",
                                                                  f"  (undo: jackson undo {a.id})")))
    return 0


def cmd_persona(args: argparse.Namespace) -> int:
    lang = _lang(args.lang)
    from .config import PERSONAS, load_config, set_toml_value
    from .persona import persona_title
    paths = Paths.from_env()
    cfg = load_config(paths)
    if args.action in (None, "show"):
        for pid in PERSONAS:
            mark = "●" if pid == cfg.persona else "○"
            print(f"{mark} {pid:<11} {persona_title(pid, lang)}")
        print(say(lang, f"юмор: {cfg.humor} (0–2) · внешний вид: j avatar", f"humor: {cfg.humor} (0–2) · look: j avatar"))
        return 0
    if args.action == "set" and args.value in PERSONAS:
        set_toml_value(paths.config_file, "", "persona", args.value)
        print(f"✓ {persona_title(args.value, lang)}")
        return 0
    if args.action == "humor" and args.value in ("0", "1", "2"):
        set_toml_value(paths.config_file, "", "humor", int(args.value))
        print(f"✓ humor = {args.value}")
        return 0
    print(say(lang, "Можно: persona set kent|sysop|dispatcher|pirate · persona humor 0|1|2 (внешний вид: j avatar)",
              "Use: persona set kent|sysop|dispatcher|pirate · persona humor 0|1|2 (look: j avatar)"),
          file=sys.stderr)
    return 2


def cmd_avatar(args: argparse.Namespace) -> int:
    """`j avatar [show|set <key> <value>|reset]` — ~/.config/svoya/avatar.json (DESIGN.md §13)."""
    from . import avatar as av
    lang = _lang(args.lang)
    paths = Paths.from_env()
    path = paths.avatar_file
    out = Style(sys.stdout, paths)
    if args.action == "show":
        look = av.load(path)
        if args.json:
            print(json.dumps({**look.to_event(), "file": str(path), "exists": path.exists()}, ensure_ascii=False,
                             indent=1))
            return 0
        rows = [("character", say(lang, "персонаж", "character")), ("skin", say(lang, "окрас", "skin")),
                ("outfit", say(lang, "одежда", "outfit")), ("style", say(lang, "стиль", "style")),
                ("headphones", say(lang, "наушники", "headphones")), ("glasses", say(lang, "очки", "glasses")),
                ("hood", say(lang, "капюшон", "hood")), ("name", say(lang, "имя", "name"))]
        for key, title in rows:
            if key == "hood" and look.data["character"] == "cat":
                continue
            value = look.display_name(lang) if key == "name" else look.label(key, lang)
            print(out.dim(f"{title:<11}") + value)
        print(out.dim(say(lang, f"файл: {path}" + ("" if path.exists() else " (ещё нет — всё по умолчанию)"),
                               f"file: {path}" + ("" if path.exists() else " (not yet — all defaults)"))))
        return 0
    prev = av.read_stored(path)
    if args.action == "reset":
        new = {k: v for k, v in (prev or {}).items() if k not in av.KEYS}  # keep what a newer shell wrote
        summary = say(lang, "внешний вид по умолчанию", "default look")
    else:
        if not args.key or not args.value:
            print(say(lang, "Как: j avatar set <ключ> <значение>, например: j avatar set персонаж кот · "
                            "j avatar set очки круглые · j avatar set имя Макс",
                      "Use: j avatar set <key> <value>, e.g. j avatar set character cat · "
                      "j avatar set glasses round · j avatar set name Max"), file=sys.stderr)
            return 2
        try:
            key = av.parse_key(args.key)
            new = av.apply_change(dict(prev or {}), key, " ".join(args.value))
        except av.AvatarError as exc:
            print("✗ " + exc.text(lang), file=sys.stderr)
            return 2
        summary = f"{key} = {av.resolve(new)[key]}"
    if av.resolve(new) == av.resolve(prev or {}) and args.action != "reset":
        print(say(lang, "Уже так.", "Already like that."))
        return 0
    av.write(path, new)
    check = av.load(path)
    from .audit import AuditLog
    from .tools.base import UndoSpec
    from .trash import Trash
    from .undo import UndoLog
    action = UndoLog(paths.actions_file, Trash(paths.trash_dir)).register(
        UndoSpec("avatar", say(lang, "мой вид: ", "my look: ") + summary, {"prev": prev}), "", "cli")
    AuditLog(paths.audit_file, paths.audit_head).append("avatar", change=summary, source="cli", action=action.id)
    verified = check.data == av.resolve(new)
    print(("✓ " if verified else "✗ ") + summary + out.dim(say(lang, f"  (вернуть: jackson undo {action.id})",
                                                              f"  (undo: jackson undo {action.id})")))
    return 0 if verified else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    lang = _lang(args.lang)
    from .doctor import run_doctor
    return run_doctor(lang, online=args.online, start_mcp=args.mcp)


def cmd_mcp(args: argparse.Namespace) -> int:
    lang = _lang(args.lang)
    app = _app()
    if args.action == "trust":
        from .tools.mcp import McpError
        try:
            n = app.mcp.trust(args.server)
        except McpError as exc:
            print(f"✗ {exc}", file=sys.stderr)
            return 1
        finally:
            app.close()
        print(say(lang, f"✓ {args.server}: закрепил {n} инструм.", f"✓ {args.server}: pinned {n} tools"))
        return 0
    app.mcp.start_all()
    try:
        rows = app.mcp.status()
    finally:
        app.close()
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    if not rows:
        print(say(lang, "MCP-серверов нет. Добавь в ~/.config/svoya/jackson.toml: [mcp.servers.<имя>] command = [...]",
                  "No MCP servers. Add to ~/.config/svoya/jackson.toml: [mcp.servers.<name>] command = [...]"))
    for r in rows:
        state = "✓" if r["running"] else "✗"
        print(f"{state} {r['name']}  {r['era']} {r['version']}  sandbox={'yes' if r['sandboxed'] else 'no'}  "
              f"tools={len(r['tools'])}" + (f"  error={r['error']}" if r["error"] else ""))
        for tool, why in (r["blocked"] or {}).items():
            print(f"    ⛔ {tool}: {why}")
    return 0


# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jackson", description="Джексон / Jackson — ассистент СОС. Короче: j <вопрос>.")
    p.add_argument("--lang", choices=["ru", "en"])
    p.add_argument("-V", "--version", action="version", version=f"jackson {__version__}")
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("ask", help="задать вопрос / ask")
    a.add_argument("words", nargs="*")
    _ask_flags(a)
    s = sub.add_parser("status", help="состояние")
    s.add_argument("--json", action="store_true")
    m = sub.add_parser("models", help="модели и цены")
    m.add_argument("--json", action="store_true")
    mem = sub.add_parser("memory", help="память: show|search|forget|path")
    mem.add_argument("action", choices=["show", "search", "forget", "path"])
    mem.add_argument("arg", nargs="?")
    mem.add_argument("--yes", action="store_true")
    mem.add_argument("--limit", type=int, default=10)
    nt = sub.add_parser("notes", help="заметки: search|read|where")
    nt.add_argument("action", choices=["search", "read", "where"])
    nt.add_argument("arg", nargs="?")
    nt.add_argument("--limit", type=int, default=10)
    au = sub.add_parser("audit", help="журнал: verify|tail")
    au.add_argument("action", choices=["verify", "tail"])
    au.add_argument("-n", type=int, default=20)
    u = sub.add_parser("undo", help="отменить действие")
    u.add_argument("action_id", nargs="?")
    u.add_argument("--list", action="store_true")
    u.add_argument("-n", type=int, default=20)
    ap = sub.add_parser("approve", help="ответить на запрос разрешения")
    ap.add_argument("call_id")
    ap.add_argument("decision", choices=["once", "always-project", "deny"])
    r = sub.add_parser("route", help="маршрут: show | set <key> <value>")
    r.add_argument("action", nargs="?", choices=["show", "set"])
    r.add_argument("key", nargs="?")
    r.add_argument("value", nargs="?")
    pe = sub.add_parser("persona", help="образ: show | set <id> | humor 0-2")
    pe.add_argument("action", nargs="?", choices=["show", "set", "humor"])
    av = sub.add_parser("avatar", help="внешний вид и имя: show | set <ключ> <значение> | reset")
    av.add_argument("action", nargs="?", choices=["show", "set", "reset"], default="show")
    av.add_argument("key", nargs="?")
    av.add_argument("value", nargs="*")
    av.add_argument("--json", action="store_true")
    pe.add_argument("value", nargs="?")
    d = sub.add_parser("doctor", help="проверка")
    d.add_argument("--online", action="store_true", help="also check cloud providers over the network")
    d.add_argument("--mcp", action="store_true", help="also start MCP servers and check their pins")
    mc = sub.add_parser("mcp", help="MCP: list | trust <server>")
    mc.add_argument("action", nargs="?", choices=["list", "trust"], default="list")
    mc.add_argument("server", nargs="?")
    mc.add_argument("--json", action="store_true")
    sub.add_parser("version")
    sub.add_parser("help")
    return p


def _ask_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--local", dest="route", action="store_const", const="local", help="только локальная модель")
    p.add_argument("--cloud", dest="route", action="store_const", const="cloud", help="облачная модель")
    p.add_argument("--route", dest="route", help="auto | local | cloud | provider/model")
    p.add_argument("--new", action="store_true", help="новый разговор")
    p.add_argument("--json", action="store_true", help="события протокола как JSON Lines")
    p.add_argument("--screenshot", help="приложить изображение")
    p.add_argument("--no-stdin", action="store_true", help="не читать stdin")
    p.add_argument("--no-local-fallback", action="store_true",
                   help="не отвечать в этом процессе, если ассистент не запущен в фоне")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--lang", choices=["ru", "en"])


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("-h", "--help"):
        build_parser().print_help()
        return 0
    if argv and argv[0] in ("-V", "--version", "version"):
        print(f"jackson {__version__}")
        return 0
    first = next((a for a in argv if not a.startswith("--lang")), None)
    if argv and first in SUBCOMMANDS and first not in ("ask",):
        args = build_parser().parse_args(argv)
        if args.cmd == "help":
            build_parser().print_help()
            return 0
        handler = {"status": cmd_status, "models": cmd_models, "memory": cmd_memory, "notes": cmd_notes,
                   "audit": cmd_audit, "undo": cmd_undo, "approve": cmd_approve, "route": cmd_route,
                   "persona": cmd_persona, "avatar": cmd_avatar, "doctor": cmd_doctor, "mcp": cmd_mcp}[args.cmd]
        return handler(args)
    # Anything else is a question: `jackson найди мои датасеты`, `j -`, `j` (chat).
    if argv and argv[0] == "ask":
        argv = argv[1:]
    ap = argparse.ArgumentParser(prog="jackson", add_help=False)
    _ask_flags(ap)
    opts, words = ap.parse_known_args(argv)
    if words and words[0] == "--":
        words = words[1:]
    return cmd_ask(words, opts)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
