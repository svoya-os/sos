# SPDX-License-Identifier: Apache-2.0
"""Socket client for the JSON Lines protocol (ARCHITECTURE §4.3).

If Jackson is not running in the background, :func:`open_connection` starts the same service
in-process on a private socket, so the CLI speaks exactly the same protocol either way.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator

from . import __version__
from .paths import Paths

LINE_LIMIT = 4 * 1024 * 1024


class Connection:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, embedded: Any = None) -> None:
        self.reader = reader
        self.writer = writer
        self.embedded = embedded  # (service, task, socket dir) when running in-process

    @property
    def in_process(self) -> bool:
        return self.embedded is not None

    async def send(self, msg: dict[str, Any]) -> None:
        self.writer.write((json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
        await self.writer.drain()

    async def recv(self, timeout: float | None = None) -> dict[str, Any] | None:
        line = await (asyncio.wait_for(self.reader.readline(), timeout) if timeout else self.reader.readline())
        if not line:
            return None
        try:
            msg = json.loads(line)
        except ValueError:
            return {"type": "error", "message": "malformed line from Jackson", "retryable": False}
        return msg if isinstance(msg, dict) else None

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            msg = await self.recv()
            if msg is None:
                return
            yield msg

    async def hello(self, client: str = "jackson-cli", lang: str | None = None) -> dict[str, Any] | None:
        msg: dict[str, Any] = {"type": "hello", "client": client, "version": __version__}
        if lang:
            msg["lang"] = lang
        await self.send(msg)
        while True:
            ev = await self.recv(timeout=15.0)
            if ev is None or ev.get("type") == "welcome":
                return ev

    async def close(self) -> None:
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass
        if self.embedded is not None:
            service, task, tmpdir = self.embedded
            service.request_stop()
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except (asyncio.TimeoutError, Exception):
                task.cancel()
            try:
                os.rmdir(tmpdir)
            except OSError:
                pass


async def connect(path: Path, timeout: float = 1.0) -> Connection:
    reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(str(path), limit=LINE_LIMIT), timeout)
    return Connection(reader, writer)


async def open_connection(paths: Paths | None = None, allow_embedded: bool = True,
                          socket_path: Path | None = None) -> Connection:
    """Connect to the running service, or start one in this process."""
    paths = paths or Paths.from_env()
    path = socket_path or paths.socket
    try:
        return await connect(path)
    except (OSError, asyncio.TimeoutError):
        if not allow_embedded:
            raise
    from .app import Jackson
    from .daemon import JacksonService

    app = Jackson(paths=paths)
    base = paths.runtime_dir if paths.runtime_dir.is_dir() else Path(tempfile.gettempdir())
    tmpdir = tempfile.mkdtemp(prefix="jk-", dir=str(base))
    private = Path(tmpdir) / "s"
    service = JacksonService(app, private)
    await service.start()
    task = asyncio.get_running_loop().create_task(service.serve_forever(handle_signals=False))
    conn = await connect(private)
    conn.embedded = (service, task, tmpdir)
    return conn


async def service_running(paths: Paths | None = None) -> bool:
    paths = paths or Paths.from_env()
    try:
        conn = await connect(paths.socket, timeout=0.5)
    except (OSError, asyncio.TimeoutError):
        return False
    await conn.close()
    return True
