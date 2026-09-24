# SPDX-License-Identifier: Apache-2.0
"""Common provider interface.

Canonical (provider-neutral) conversation messages::

    {"role": "user", "content": "text", "images": [{"mime": "image/png", "data": "<base64>"}]}
    {"role": "assistant", "content": "text", "tool_calls": [{"id", "name", "args"}],
     "native": {"provider": "anthropic", "content": [...]}}      # replayed verbatim to the same provider
    {"role": "tool", "tool_call_id": "...", "name": "fs__read", "content": "text", "is_error": False}

``stream()`` yields :class:`TextDelta`, :class:`ToolCall`, :class:`Usage` and exactly one final
:class:`End`. It runs in a worker thread; cancellation goes through :class:`CancelToken`.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from ..config import ProviderConfig


# ---------------------------------------------------------------------------
# events

@dataclass
class TextDelta:
    text: str


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]
    error: str | None = None       # arguments were not valid JSON
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    estimated: bool = False
    billable_input: float | None = None   # input tokens weighted by cache pricing, if it differs


@dataclass
class End:
    stop_reason: str = "stop"
    native: dict[str, Any] | None = None


Event = TextDelta | ToolCall | Usage | End


# ---------------------------------------------------------------------------

@dataclass
class ToolSpec:
    name: str                 # wire name ([A-Za-z0-9_-], ≤ 64)
    description: str
    parameters: dict[str, Any]


@dataclass
class ChatRequest:
    model: str
    system: str
    messages: list[dict[str, Any]]
    tools: list[ToolSpec] = field(default_factory=list)
    max_tokens: int | None = None
    temperature: float | None = None


@dataclass
class Health:
    ok: bool
    detail: str = ""
    models: list[str] = field(default_factory=list)
    loading: bool = False
    latency_ms: float = 0.0


class ProviderError(Exception):
    """A provider failure with a human-readable message and a retry hint."""

    def __init__(self, message: str, *, kind: str = "error", retryable: bool = False,
                 status: int | None = None, provider: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.kind = kind          # network | timeout | auth | rate | server | bad_request | protocol | cancelled
        self.retryable = retryable
        self.status = status
        self.provider = provider
        self.output_started = False  # set by the engine when text was already streamed

    def __str__(self) -> str:
        prefix = f"{self.provider}: " if self.provider else ""
        return prefix + self.message


class Cancelled(Exception):
    pass


class CancelToken:
    """Thread-safe cancellation flag with abort callbacks (e.g. closing a socket)."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._callbacks: list[Callable[[], None]] = []

    def cancel(self) -> None:
        with self._lock:
            if self._event.is_set():
                return
            self._event.set()
            callbacks, self._callbacks = self._callbacks, []
        for cb in callbacks:
            try:
                cb()
            except Exception:
                pass

    def is_set(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float | None = None) -> bool:
        return self._event.wait(timeout)

    def on_cancel(self, cb: Callable[[], None]) -> Callable[[], None]:
        with self._lock:
            if not self._event.is_set():
                self._callbacks.append(cb)

                def remove() -> None:
                    with self._lock:
                        if cb in self._callbacks:
                            self._callbacks.remove(cb)
                return remove
        cb()
        return lambda: None

    def check(self) -> None:
        if self._event.is_set():
            raise Cancelled()


class Provider(ABC):
    def __init__(self, cfg: ProviderConfig, api_key: str | None = None) -> None:
        self.cfg = cfg
        self.api_key = api_key

    @property
    def name(self) -> str:
        return self.cfg.name

    @property
    def local(self) -> bool:
        return self.cfg.local

    @abstractmethod
    def stream(self, req: ChatRequest, cancel: CancelToken) -> Iterator[Event]:
        ...

    @abstractmethod
    def health(self, timeout: float = 1.0) -> Health:
        ...

    def replayable(self, msg: dict[str, Any]) -> list[Any] | None:
        """Native assistant content from this very provider, if any."""
        native = msg.get("native")
        if isinstance(native, dict) and native.get("provider") == self.name:
            content = native.get("content")
            return content if isinstance(content, list) else None
        return None


def chars_to_tokens(chars: int) -> int:
    """Rough token estimate (≈3.5 chars per token for mixed RU/EN text)."""
    return max(1, int(chars / 3.5)) if chars > 0 else 0


def estimate_tokens(text: str) -> int:
    return chars_to_tokens(len(text or ""))


class ThinkFilter:
    """Hides ``<think>…</think>`` blocks that some local models stream inline."""

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self.inside = False
        self.buf = ""

    def feed(self, text: str) -> str:
        self.buf += text
        out = []
        while self.buf:
            if self.inside:
                idx = self.buf.find(self.CLOSE)
                if idx < 0:
                    keep = _partial_suffix(self.buf, self.CLOSE)
                    self.buf = self.buf[len(self.buf) - keep:] if keep else ""
                    break
                self.buf = self.buf[idx + len(self.CLOSE):].lstrip("\n")
                self.inside = False
            else:
                idx = self.buf.find(self.OPEN)
                if idx < 0:
                    keep = _partial_suffix(self.buf, self.OPEN)
                    out.append(self.buf[:len(self.buf) - keep])
                    self.buf = self.buf[len(self.buf) - keep:]
                    break
                out.append(self.buf[:idx])
                self.buf = self.buf[idx + len(self.OPEN):]
                self.inside = True
        return "".join(out)

    def flush(self) -> str:
        rest, self.buf = ("" if self.inside else self.buf), ""
        return rest


def _partial_suffix(text: str, token: str) -> int:
    """Length of the longest suffix of *text* that is a proper prefix of *token*."""
    for n in range(min(len(token) - 1, len(text)), 0, -1):
        if text.endswith(token[:n]):
            return n
    return 0
