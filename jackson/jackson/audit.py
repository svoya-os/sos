# SPDX-License-Identifier: Apache-2.0
"""Tamper-evident audit log: hash-chained JSON Lines.

Each line is a JSON object whose ``prev`` field is the SHA-256 (hex) of the previous line's
exact bytes (``"0"*64`` for the first line). ``audit.head`` stores the sequence number and
hash of the last line, so truncation is detected too. Appends are serialized across processes
with ``flock`` and fsync'ed.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

GENESIS = "0" * 64
MAX_STR = 300
_SECRET_KEY = re.compile(r"(api[_-]?key|token|password|passwd|secret|authorization|cookie)", re.IGNORECASE)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compact(value: Any, depth: int = 0) -> Any:
    """Keep the log small and free of secrets: long strings become digests."""
    if depth > 6:
        return "…"
    if isinstance(value, str):
        if len(value) > MAX_STR:
            return {"sha256": sha256_hex(value.encode("utf-8", "replace")), "len": len(value),
                    "head": value[:80]}
        return value
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if _SECRET_KEY.search(str(k)) and isinstance(v, str):
                out[str(k)] = "***"
            else:
                out[str(k)] = compact(v, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        items = [compact(v, depth + 1) for v in list(value)[:50]]
        if len(value) > 50:
            items.append(f"… +{len(value) - 50}")
        return items
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)


@dataclass
class VerifyResult:
    ok: bool
    count: int
    bad_line: int | None = None
    reason: str = ""
    last_hash: str = GENESIS


class AuditLog:
    def __init__(self, path: Path, head_path: Path | None = None) -> None:
        self.path = path
        self.head_path = head_path or path.with_suffix(".head")
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def _read_tail(self, fd: int) -> tuple[str, int]:
        """Hash and seq of the last line (under the flock)."""
        size = os.fstat(fd).st_size
        if size == 0:
            return GENESIS, 0
        chunk = 4096
        pos = size
        buf = b""
        while pos > 0:
            step = min(chunk, pos)
            pos -= step
            buf = os.pread(fd, step, pos) + buf
            stripped = buf.rstrip(b"\n")
            if b"\n" in stripped:
                break
        last = buf.rstrip(b"\n").rsplit(b"\n", 1)[-1]
        try:
            seq = int(json.loads(last).get("seq", 0))
        except (ValueError, AttributeError):
            seq = 0
        return sha256_hex(last), seq

    def append(self, kind: str, **fields: Any) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            fd = os.open(self.path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                prev, seq = self._read_tail(fd)
                entry: dict[str, Any] = {
                    "seq": seq + 1,
                    "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds"),
                    "kind": kind,
                }
                for key, value in fields.items():
                    if key not in entry and key != "prev":
                        entry[key] = compact(value)
                entry["prev"] = prev
                line = json.dumps(entry, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                os.write(fd, line + b"\n")
                os.fsync(fd)
                self._write_head(seq + 1, sha256_hex(line))
            finally:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)
        return entry

    def _write_head(self, seq: int, digest: str) -> None:
        tmp = self.head_path.with_name(self.head_path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"seq": seq, "hash": digest}, fh)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.head_path)

    # ------------------------------------------------------------------
    def lines(self) -> Iterator[bytes]:
        try:
            with open(self.path, "rb") as fh:
                for raw in fh:
                    yield raw.rstrip(b"\n")
        except FileNotFoundError:
            return

    def verify(self) -> VerifyResult:
        prev = GENESIS
        count = 0
        for i, raw in enumerate(self.lines(), start=1):
            try:
                entry = json.loads(raw)
                if not isinstance(entry, dict):
                    raise ValueError
            except ValueError:
                return VerifyResult(False, count, i, "line is not a JSON object", prev)
            if entry.get("prev") != prev:
                reason = ("prev hash does not match line {} — it was altered, inserted or removed"
                          .format(i - 1) if i > 1 else "first line does not start the chain")
                return VerifyResult(False, count, i, reason, prev)
            if entry.get("seq") != i:
                return VerifyResult(False, count, i, f"sequence number {entry.get('seq')} != {i}", prev)
            prev = sha256_hex(raw)
            count = i
        try:
            with open(self.head_path, encoding="utf-8") as fh:
                head = json.load(fh)
        except FileNotFoundError:
            head = None
        except (OSError, ValueError):
            return VerifyResult(False, count, None, "audit.head is unreadable", prev)
        if head is not None:
            if head.get("seq") != count or head.get("hash") != prev:
                return VerifyResult(False, count, count + 1 if head.get("seq", 0) > count else None,
                                    f"log ends at line {count} but the head says {head.get('seq')} — "
                                    f"lines were removed or the head was altered", prev)
        elif count:
            return VerifyResult(False, count, None, "audit.head is missing", prev)
        return VerifyResult(True, count, None, "", prev)

    def tail(self, n: int = 20) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for raw in self.lines():
            try:
                out.append(json.loads(raw))
            except ValueError:
                out.append({"kind": "corrupt", "raw": raw[:200].decode("utf-8", "replace")})
            if len(out) > n:
                out.pop(0)
        return out
