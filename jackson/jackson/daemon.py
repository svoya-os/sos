# SPDX-License-Identifier: Apache-2.0
"""jacksond: the Unix-socket service behind Super+J (docs/ARCHITECTURE.md §4.3).

Socket: ``$XDG_RUNTIME_DIR/svoya/jackson.sock`` (directory 0700, socket 0600), JSON Lines.

Client → service: hello, ask, approve, cancel, status, undo (+ ``ping``).
Service → client: welcome, route, token, tool, approval, done, error, state (+ ``status``, ``pong``).

* Many clients at once; one active turn per client; turns of different clients run concurrently.
* ``state`` events are broadcast to every client (the bar's mini-scope follows any turn);
  all other turn events go to the client that asked.
* Approvals may be answered from any client (e.g. `jackson approve` from another terminal).
* A client that disconnects cancels its running turn.
* SIGTERM/SIGINT: stop accepting, end running turns with an ``error``, remove the socket.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import socket
import time
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION, __version__
from .app import Jackson
from .engine import Session, Turn, new_id
from .i18n import norm_lang, t

log = logging.getLogger("jackson.service")

LINE_LIMIT = 4 * 1024 * 1024
DECISIONS = ("once", "always-project", "deny")


def sd_notify(message: str) -> None:
    """Tell systemd about readiness/stopping (Type=notify); no-op outside systemd."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(addr)
            sock.sendall(message.encode())
    except OSError:
        pass


class Client:
    def __init__(self, cid: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, lang: str) -> None:
        self.id = cid
        self.reader = reader
        self.writer = writer
        self.name = "unknown"
        self.version = ""
        self.session = Session(client=cid, lang=lang)
        self.turn: Turn | None = None
        self.task: asyncio.Task[None] | None = None
        self.queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self.closed = False

    def send(self, event: dict[str, Any]) -> None:
        if not self.closed:
            self.queue.put_nowait(event)

    async def writer_loop(self) -> None:
        try:
            while True:
                event = await self.queue.get()
                if event is None:
                    break
                line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
                self.writer.write(line.encode("utf-8"))
                await self.writer.drain()
        except (ConnectionError, OSError, asyncio.CancelledError):
            pass
        finally:
            self.closed = True


class JacksonService:
    def __init__(self, app: Jackson, socket_path: Path | None = None, health_interval: float = 15.0) -> None:
        self.app = app
        self.socket_path = Path(socket_path) if socket_path else app.paths.socket
        self.health_interval = health_interval
        self.clients: dict[str, Client] = {}
        self.server: asyncio.AbstractServer | None = None
        self._stop = asyncio.Event()
        self._background: list[asyncio.Task[Any]] = []
        self.started = time.monotonic()
        self.stopping = False

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        path = self.socket_path
        if path == self.app.paths.socket:
            self.app.paths.ensure_runtime_dir()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() or path.is_socket():
            if await self._alive(path):
                raise RuntimeError(f"Jackson is already running on {path}")
            path.unlink()
        self.server = await asyncio.start_unix_server(self._handle, path=str(path), limit=LINE_LIMIT)
        os.chmod(path, 0o600)
        self.app.audit.append("service", event="start", version=__version__, socket=str(path))
        loop = asyncio.get_running_loop()
        self._background.append(loop.create_task(self._health_loop()))
        self._background.append(loop.create_task(self._start_background()))
        sd_notify("READY=1\nSTATUS=Jackson is listening")
        log.info("listening on %s", path)

    async def _alive(self, path: Path) -> bool:
        try:
            _r, w = await asyncio.wait_for(asyncio.open_unix_connection(str(path)), timeout=1.0)
        except (OSError, asyncio.TimeoutError):
            return False
        w.close()
        try:
            await w.wait_closed()
        except OSError:
            pass
        return True

    async def _start_background(self) -> None:
        warnings = await asyncio.to_thread(self.app.start_background)
        for w in warnings:
            log.warning("%s", w)

    async def _health_loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self.app.config_changed():
                    changed = await asyncio.to_thread(self.app.reload_config)
                    log.info("settings reloaded: %s", ", ".join(changed) or "no changes")
                await asyncio.to_thread(self.app.refresh_health)
                self.app.mcp.refresh_changed()
            except Exception:  # pragma: no cover - defensive
                log.debug("health refresh failed", exc_info=True)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.health_interval)
            except asyncio.TimeoutError:
                pass

    async def serve_forever(self, handle_signals: bool = True) -> None:
        loop = asyncio.get_running_loop()
        if handle_signals:
            for sig in (signal.SIGTERM, signal.SIGINT):
                try:
                    loop.add_signal_handler(sig, self._stop.set)
                except (NotImplementedError, RuntimeError):
                    pass
        await self._stop.wait()
        await self.shutdown()

    def request_stop(self) -> None:
        self._stop.set()

    async def shutdown(self) -> None:
        if self.stopping:
            return
        self.stopping = True
        self._stop.set()
        sd_notify("STOPPING=1")
        if self.server is not None:
            self.server.close()
        for client in list(self.clients.values()):
            turn = client.turn
            if turn is not None and not turn.finished:
                turn.finished = True  # our own error below is the terminal event
                client.send({"type": "error", "id": turn.id, "message": t("err.shutdown", client.session.lang),
                             "retryable": True})
                client.send({"type": "state", "id": turn.id, "state": "idle",
                             "persona": self.app.config.persona, "avatar": self.app.config.avatar, "mood": "calm"})
            if client.task is not None:
                client.task.cancel()
        tasks = [c.task for c in self.clients.values() if c.task is not None]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for client in list(self.clients.values()):
            client.queue.put_nowait(None)
        await asyncio.sleep(0.05)
        for client in list(self.clients.values()):
            try:
                client.writer.close()
            except Exception:
                pass
        for task in self._background:
            task.cancel()
        await asyncio.gather(*self._background, return_exceptions=True)
        if self.server is not None:
            try:
                await asyncio.wait_for(self.server.wait_closed(), timeout=2.0)
            except asyncio.TimeoutError:
                pass
        await asyncio.to_thread(self.app.close)
        try:
            self.socket_path.unlink()
        except FileNotFoundError:
            pass
        self.app.audit.append("service", event="stop", uptimeSec=round(time.monotonic() - self.started, 1))

    # ------------------------------------------------------------------ connections
    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        client = Client(new_id("c"), reader, writer, self.app.config.language)
        self.clients[client.id] = client
        writer_task = asyncio.get_running_loop().create_task(client.writer_loop())
        try:
            while not self.stopping:
                try:
                    line = await reader.readline()
                except (asyncio.LimitOverrunError, ValueError):
                    client.send({"type": "error", "message": t("err.bad_message", client.session.lang,
                                                               why="line too long"), "retryable": False})
                    break
                except (ConnectionError, OSError):
                    break
                if not line:
                    break
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                    if not isinstance(msg, dict):
                        raise ValueError("not an object")
                except ValueError as exc:
                    client.send({"type": "error", "message": t("err.bad_message", client.session.lang, why=str(exc)),
                                 "retryable": False})
                    continue
                try:
                    await self._dispatch(client, msg)
                except Exception as exc:  # pragma: no cover - defensive
                    log.exception("dispatch failed")
                    client.send({"type": "error", "id": msg.get("id"), "retryable": False,
                                 "message": t("err.internal", client.session.lang, why=str(exc))})
        finally:
            if client.task is not None and not client.task.done():
                if client.turn is not None:
                    client.turn.cancel.cancel()
                    self.app.engine.deny_all(client.turn)
                client.task.cancel()
                try:
                    await client.task
                except BaseException:
                    pass
            client.queue.put_nowait(None)
            try:
                await asyncio.wait_for(writer_task, timeout=2.0)
            except (asyncio.TimeoutError, Exception):
                writer_task.cancel()
            self.clients.pop(client.id, None)
            try:
                writer.close()
                await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
            except Exception:
                pass

    # ------------------------------------------------------------------ messages
    async def _dispatch(self, client: Client, msg: dict[str, Any]) -> None:
        mtype = msg.get("type")
        lang = client.session.lang
        if mtype == "hello":
            client.name = str(msg.get("client") or "unknown")[:64]
            client.version = str(msg.get("version") or "")[:32]
            if msg.get("lang"):
                client.session.lang = norm_lang(str(msg["lang"]))
            client.send(await self._welcome(client))
        elif mtype == "ask":
            await self._ask(client, msg)
        elif mtype == "approve":
            call_id = str(msg.get("callId") or "")
            decision = str(msg.get("decision") or "")
            if decision not in DECISIONS:
                client.send({"type": "error", "id": msg.get("id"), "retryable": False,
                             "message": t("err.bad_message", lang, why=f"decision must be one of {DECISIONS}")})
            elif not self.app.engine.resolve_approval(call_id, decision):
                client.send({"type": "error", "id": msg.get("id"), "retryable": False,
                             "message": t("err.bad_message", lang, why=f"no pending approval {call_id!r}")})
        elif mtype == "cancel":
            self._cancel(str(msg.get("id") or ""), client)
        elif mtype == "status":
            client.send(await self._status(client, msg))
            client.send({"type": "state", "state": self.aggregate_state(), "persona": self.app.config.persona,
                         "avatar": self.app.config.avatar, "mood": "calm"})
        elif mtype == "undo":
            await self._undo(client, msg)
        elif mtype == "ping":
            client.send({"type": "pong", "id": msg.get("id")})
        else:
            client.send({"type": "error", "id": msg.get("id"), "retryable": False,
                         "message": t("err.bad_message", lang, why=f"unknown type {mtype!r}")})

    async def _welcome(self, client: Client) -> dict[str, Any]:
        app = self.app
        lang = client.session.lang
        models = await asyncio.to_thread(app.router.model_table)
        route = await asyncio.to_thread(app.route_preview, lang)
        return {"type": "welcome", "version": __version__, "protocol": PROTOCOL_VERSION, "models": models,
                "route": route, "client": client.id, "lang": lang, "persona": app.persona(lang),
                "avatar": app.config.avatar, "name": "Джексон" if lang == "ru" else "Jackson"}

    async def _status(self, client: Client, msg: dict[str, Any]) -> dict[str, Any]:
        info = self.app.engine.status()
        turns = [{"id": c.turn.id, "client": c.id, "clientName": c.name, "state": c.turn.state}
                 for c in self.clients.values() if c.turn is not None and not c.turn.finished]
        return {**info, "type": "status", "id": msg.get("id"), "version": __version__,
                "protocol": PROTOCOL_VERSION, "state": self.aggregate_state(), "clients": len(self.clients),
                "turns": turns, "uptimeSec": round(time.monotonic() - self.started, 1),
                "models": await asyncio.to_thread(self.app.router.model_table),
                "persona": self.app.persona(client.session.lang), "avatar": self.app.config.avatar}

    def aggregate_state(self) -> str:
        order = ["speaking", "working", "thinking", "listening"]
        states = {c.turn.state for c in self.clients.values() if c.turn is not None and not c.turn.finished}
        for s in order:
            if s in states:
                return s
        return "idle"

    def _emitter(self, client: Client) -> Any:
        async def emit(event: dict[str, Any]) -> None:
            if event.get("type") == "state":
                event = dict(event, client=client.id)
                for other in list(self.clients.values()):
                    other.send(event)
            else:
                client.send(event)
        return emit

    async def _ask(self, client: Client, msg: dict[str, Any]) -> None:
        lang = client.session.lang
        turn_id = str(msg.get("id") or "").strip()
        text = msg.get("text")
        if not turn_id or not isinstance(text, str) or not text.strip():
            client.send({"type": "error", "id": turn_id or None, "retryable": False,
                         "message": t("err.bad_message", lang, why="ask needs non-empty `id` and `text`")})
            return
        if client.turn is not None and not client.turn.finished:
            client.send({"type": "error", "id": turn_id, "message": t("err.busy", lang), "retryable": True})
            return
        context = msg.get("context") if isinstance(msg.get("context"), dict) else {}
        route = msg.get("route") if isinstance(msg.get("route"), str) else None
        if msg.get("new"):
            client.session.reset()
        turn = Turn(id=turn_id, session=client.session, text=text.strip(), emit=self._emitter(client),
                    context=dict(context), route=route)
        client.turn = turn
        self.app.audit.append("ask", turn=turn_id, client=client.id, clientName=client.name,
                              chars=len(text), route=route, context=sorted(context))
        client.task = asyncio.get_running_loop().create_task(self.app.engine.run_turn(turn))

    def _cancel(self, turn_id: str, requester: Client) -> None:
        for client in self.clients.values():
            turn = client.turn
            if turn is not None and not turn.finished and (turn.id == turn_id or (not turn_id and client is requester)):
                turn.cancel.cancel()
                self.app.engine.deny_all(turn)
                if client.task is not None:
                    client.task.cancel()
                self.app.audit.append("cancel", turn=turn.id, by=requester.id)
                return

    async def _undo(self, client: Client, msg: dict[str, Any]) -> None:
        lang = client.session.lang
        uid = str(msg.get("id") or new_id("undo"))
        action_id = msg.get("actionId") if isinstance(msg.get("actionId"), str) else None
        t0 = time.monotonic()
        emit = self._emitter(client)
        persona, avatar = self.app.config.persona, self.app.config.avatar
        await emit({"type": "state", "id": uid, "state": "working", "persona": persona, "avatar": avatar,
                    "mood": "busy"})
        call_id = new_id("call")
        await emit({"type": "tool", "id": uid, "callId": call_id, "name": "undo", "args": {"actionId": action_id},
                    "tier": 1, "state": "running", "summary": ""})
        outcome = await asyncio.to_thread(self.app.undo.undo, action_id, lang)
        await emit({"type": "tool", "id": uid, "callId": call_id, "name": "undo", "args": {"actionId": action_id},
                    "tier": 1, "state": "done" if outcome.ok else "failed", "summary": outcome.message})
        if outcome.ok:
            await emit({"type": "token", "id": uid, "text": outcome.message})
            await emit({"type": "done", "id": uid, "usage": {"inTokens": 0, "outTokens": 0}, "costEur": 0,
                        "latencyMs": int((time.monotonic() - t0) * 1000), "leftMachine": False, "actions": [],
                        "undone": [outcome.action.id] if outcome.action else []})
        else:
            await emit({"type": "error", "id": uid, "message": outcome.message, "retryable": False})
        await emit({"type": "state", "id": uid, "state": "idle", "persona": persona, "avatar": avatar,
                    "mood": "calm" if outcome.ok else "sorry"})


# ---------------------------------------------------------------------------

async def run_service(app: Jackson, socket_path: Path | None = None) -> None:
    service = JacksonService(app, socket_path)
    await service.start()
    await service.serve_forever()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="jacksond", description="Jackson background service (Unix socket).")
    parser.add_argument("--socket", help="socket path (default: $XDG_RUNTIME_DIR/svoya/jackson.sock)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    app = Jackson()
    for w in app.config.warnings:
        log.warning("config: %s", w)
    try:
        asyncio.run(run_service(app, Path(args.socket) if args.socket else None))
    except RuntimeError as exc:
        log.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
