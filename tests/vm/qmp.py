# SPDX-License-Identifier: Apache-2.0
"""Minimal QEMU Machine Protocol (QMP) client, stdlib only.

    with QMPClient.connect_unix("/tmp/qmp.sock") as qmp:
        qmp.negotiate()
        qmp.execute("screendump", {"filename": "/tmp/s.ppm"})
        qmp.send_key(["meta_l", "spc"])

Every command carries an "id"; replies are matched by id, asynchronous events that arrive in
between are buffered in ``events``.
"""
from __future__ import annotations

import itertools
import json
import socket
import time
from typing import Any, Iterable


class QMPError(RuntimeError):
    """QEMU answered a command with an error object."""

    def __init__(self, command: str, error: dict[str, Any]):
        self.command = command
        self.error = error
        super().__init__(f"{command}: {error.get('class', 'Error')}: {error.get('desc', error)}")


class QMPTimeout(TimeoutError):
    pass


def encode_command(command: str, arguments: dict[str, Any] | None = None, cmd_id: Any = None) -> bytes:
    msg: dict[str, Any] = {"execute": command}
    if arguments:
        msg["arguments"] = arguments
    if cmd_id is not None:
        msg["id"] = cmd_id
    return (json.dumps(msg, separators=(",", ":")) + "\r\n").encode("utf-8")


def key_events(keys: Iterable[str]) -> list[dict[str, str]]:
    """["meta_l", "spc"] -> QMP KeyValue list (qcode names, see QEMU's qapi/ui.json)."""
    return [{"type": "qcode", "data": k} for k in keys]


class QMPClient:
    def __init__(self, sock: socket.socket, timeout: float = 30.0):
        self.sock = sock
        self.sock.settimeout(timeout)
        self.timeout = timeout
        self._buf = b""
        self._ids = itertools.count(1)
        self.greeting: dict[str, Any] | None = None
        self.events: list[dict[str, Any]] = []

    # -- connection -------------------------------------------------------------------------------
    @classmethod
    def connect_unix(cls, path: str, timeout: float = 30.0, wait: float = 30.0) -> "QMPClient":
        deadline = time.monotonic() + wait
        last: OSError | None = None
        while time.monotonic() < deadline:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                s.connect(path)
                return cls(s, timeout)
            except OSError as exc:  # socket not there yet / QEMU still starting
                last = exc
                s.close()
                time.sleep(0.2)
        raise QMPTimeout(f"cannot connect to {path}: {last}")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self) -> "QMPClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- wire -------------------------------------------------------------------------------------
    def _read_message(self, deadline: float) -> dict[str, Any]:
        while b"\n" not in self._buf:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise QMPTimeout("timed out waiting for QMP data")
            self.sock.settimeout(remaining)
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout as exc:
                raise QMPTimeout("timed out waiting for QMP data") from exc
            if not chunk:
                raise ConnectionError("QMP connection closed by QEMU")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        line = line.strip()
        if not line:
            return self._read_message(deadline)
        return json.loads(line.decode("utf-8"))

    def negotiate(self) -> dict[str, Any]:
        """Read the greeting and enter command mode (qmp_capabilities)."""
        deadline = time.monotonic() + self.timeout
        msg = self._read_message(deadline)
        if "QMP" not in msg:
            raise QMPError("greeting", {"desc": f"unexpected greeting {msg!r}"})
        self.greeting = msg["QMP"]
        self.execute("qmp_capabilities")
        return self.greeting

    def execute(self, command: str, arguments: dict[str, Any] | None = None,
                timeout: float | None = None) -> Any:
        cmd_id = f"sos-{next(self._ids)}"
        self.sock.sendall(encode_command(command, arguments, cmd_id))
        deadline = time.monotonic() + (timeout or self.timeout)
        while True:
            msg = self._read_message(deadline)
            if "event" in msg:
                self.events.append(msg)
                continue
            if msg.get("id") != cmd_id:
                continue  # stale reply of an abandoned command
            if "error" in msg:
                raise QMPError(command, msg["error"])
            return msg.get("return")

    # -- helpers ----------------------------------------------------------------------------------
    def screendump(self, filename: str, fmt: str | None = None) -> None:
        args: dict[str, Any] = {"filename": filename}
        if fmt:
            args["format"] = fmt
        self.execute("screendump", args)

    def send_key(self, keys: Iterable[str], hold_ms: int = 100) -> None:
        self.execute("send-key", {"keys": key_events(keys), "hold-time": int(hold_ms)})

    def pointer(self, x: float, y: float, width: int, height: int, button: str | None = "left") -> None:
        """Move the absolute pointer (the usb-tablet) to pixel (x, y) of a width×height screen, then
        press and release *button* (None: only move)."""
        ax = round(min(max(x, 0), width - 1) * 32767 / max(1, width - 1))
        ay = round(min(max(y, 0), height - 1) * 32767 / max(1, height - 1))
        self.execute("input-send-event", {"events": [{"type": "abs", "data": {"axis": "x", "value": ax}},
                                                     {"type": "abs", "data": {"axis": "y", "value": ay}}]})
        if button:
            for down in (True, False):
                time.sleep(0.05)
                self.execute("input-send-event", {"events": [{"type": "btn", "data": {"down": down, "button": button}}]})

    def eject(self, device_id: str) -> None:
        """Open the tray of a removable drive (the ISO), also while the guest holds it."""
        self.execute("eject", {"id": device_id, "force": True})

    def reset(self) -> None:
        """Hard reset, like the machine's reset button."""
        self.execute("system_reset")

    def status(self) -> str:
        return str((self.execute("query-status") or {}).get("status", "unknown"))

    def quit(self) -> None:
        try:
            self.execute("quit", timeout=5)
        except (ConnectionError, QMPTimeout, OSError):
            pass
