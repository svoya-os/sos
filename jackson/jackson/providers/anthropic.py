# SPDX-License-Identifier: Apache-2.0
"""Anthropic Messages API (streaming SSE, tools, thinking blocks replayed verbatim)."""

from __future__ import annotations

import json
import time
from typing import Any, Iterator

from .base import (ChatRequest, CancelToken, End, Event, Health, Provider, ProviderError, TextDelta,
                   ToolCall, Usage)
from .http import get_json, iter_sse, post_sse

API_VERSION = "2023-06-01"
_RETRYABLE = {"overloaded_error", "api_error", "rate_limit_error", "timeout_error"}


class AnthropicProvider(Provider):
    kind = "anthropic"

    def _headers(self) -> dict[str, str]:
        headers = {"anthropic-version": API_VERSION, **self.cfg.headers}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def build_messages(self, req: ChatRequest) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []

        def push(role: str, blocks: list[dict[str, Any]]) -> None:
            if out and out[-1]["role"] == role:
                out[-1]["content"].extend(blocks)
            else:
                out.append({"role": role, "content": list(blocks)})

        for m in req.messages:
            role = m.get("role")
            if role == "user":
                blocks: list[dict[str, Any]] = [
                    {"type": "image", "source": {"type": "base64", "media_type": img["mime"], "data": img["data"]}}
                    for img in m.get("images") or []]
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                push("user", blocks or [{"type": "text", "text": "…"}])
            elif role == "assistant":
                native = self.replayable(m)
                if native:
                    blocks = native
                else:
                    blocks = [{"type": "text", "text": m["content"]}] if m.get("content") else []
                    blocks += [{"type": "tool_use", "id": c["id"], "name": c["name"], "input": c.get("args") or {}}
                               for c in m.get("tool_calls") or []]
                push("assistant", blocks or [{"type": "text", "text": "…"}])
            elif role == "tool":
                push("user", [{"type": "tool_result", "tool_use_id": m.get("tool_call_id", ""),
                               "content": m.get("content") or "(empty)",
                               "is_error": bool(m.get("is_error"))}])
        if out and out[0]["role"] != "user":
            out.insert(0, {"role": "user", "content": [{"type": "text", "text": "…"}]})
        return out

    def build_payload(self, req: ChatRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": req.model,
            "max_tokens": req.max_tokens or self.cfg.max_tokens,
            "messages": self.build_messages(req),
            "stream": True,
        }
        if req.system:
            # Cache the (large, stable) system prompt across the steps of a tool loop.
            payload["system"] = [{"type": "text", "text": req.system, "cache_control": {"type": "ephemeral"}}]
        if req.tools:
            payload["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.parameters}
                                for t in req.tools]
        if req.temperature is not None:
            payload["temperature"] = req.temperature
        return payload

    def stream(self, req: ChatRequest, cancel: CancelToken) -> Iterator[Event]:
        conn, resp = post_sse(self.cfg.base_url + "/v1/messages", self.build_payload(req), self._headers(),
                              connect_timeout=self.cfg.connect_timeout, read_timeout=self.cfg.timeout,
                              use_proxy=not self.cfg.local, cancel=cancel, provider=self.name)
        try:
            yield from self._parse(resp, cancel)
        finally:
            conn.close()

    def _parse(self, resp: Any, cancel: CancelToken) -> Iterator[Event]:
        blocks: dict[int, dict[str, Any]] = {}
        json_bufs: dict[int, str] = {}
        in_tokens = out_tokens = cache_write = cache_read = 0
        stop = "end_turn"
        finished = False
        for event, data in iter_sse(resp, cancel, self.name):
            try:
                msg = json.loads(data)
            except ValueError:
                continue
            etype = msg.get("type") or event
            if etype == "message_start":
                u = (msg.get("message") or {}).get("usage") or {}
                in_tokens = int(u.get("input_tokens") or 0)
                cache_write = int(u.get("cache_creation_input_tokens") or 0)
                cache_read = int(u.get("cache_read_input_tokens") or 0)
                out_tokens = int(u.get("output_tokens") or 0)
            elif etype == "content_block_start":
                idx = int(msg.get("index", 0))
                block = dict(msg.get("content_block") or {})
                blocks[idx] = block
                if block.get("type") in ("tool_use", "server_tool_use"):
                    json_bufs[idx] = ""
            elif etype == "content_block_delta":
                idx = int(msg.get("index", 0))
                delta = msg.get("delta") or {}
                block = blocks.setdefault(idx, {"type": "text", "text": ""})
                dtype = delta.get("type")
                if dtype == "text_delta":
                    text = delta.get("text") or ""
                    block["text"] = block.get("text", "") + text
                    if text:
                        yield TextDelta(text)
                elif dtype == "input_json_delta":
                    json_bufs[idx] = json_bufs.get(idx, "") + (delta.get("partial_json") or "")
                elif dtype == "thinking_delta":
                    block["thinking"] = block.get("thinking", "") + (delta.get("thinking") or "")
                elif dtype == "signature_delta":
                    block["signature"] = block.get("signature", "") + (delta.get("signature") or "")
            elif etype == "content_block_stop":
                idx = int(msg.get("index", 0))
                block = blocks.get(idx) or {}
                if idx in json_bufs:
                    raw = json_bufs.pop(idx).strip() or "{}"
                    try:
                        block["input"] = json.loads(raw)
                        error = None
                    except ValueError:
                        block["input"], error = {}, f"arguments are not valid JSON: {raw[:200]}"
                    if block.get("type") == "tool_use":
                        args = block["input"] if isinstance(block["input"], dict) else {}
                        yield ToolCall(block.get("id", ""), block.get("name", ""), args, error=error)
            elif etype == "message_delta":
                delta = msg.get("delta") or {}
                if delta.get("stop_reason"):
                    stop = delta["stop_reason"]
                u = msg.get("usage") or {}
                out_tokens = max(out_tokens, int(u.get("output_tokens") or 0))
                in_tokens = max(in_tokens, int(u.get("input_tokens") or 0))
            elif etype == "message_stop":
                finished = True
                break
            elif etype == "error":
                err = msg.get("error") or {}
                etype_ = err.get("type", "error")
                raise ProviderError(f"{etype_}: {err.get('message', '')}".strip(), kind="server",
                                    retryable=etype_ in _RETRYABLE, provider=self.name)
        if not finished and not blocks:
            raise ProviderError("the stream ended before the answer", kind="protocol", retryable=True,
                                provider=self.name)
        ordered = [blocks[i] for i in sorted(blocks)]
        for b in ordered:  # an empty citations list is not accepted back
            if b.get("type") == "text" and not b.get("citations"):
                b.pop("citations", None)
        # Cache writes cost 1.25×, cache reads 0.1× the input price.
        yield Usage(in_tokens + cache_write + cache_read, out_tokens,
                    billable_input=in_tokens + cache_write * 1.25 + cache_read * 0.1)
        yield End(stop, {"provider": self.name, "content": ordered})

    def health(self, timeout: float = 2.0) -> Health:
        if not self.api_key:
            return Health(False, "no API key")
        t0 = time.monotonic()
        try:
            status, data = get_json(self.cfg.base_url + "/v1/models", self._headers(), timeout=timeout,
                                    use_proxy=not self.cfg.local, provider=self.name)
        except ProviderError as exc:
            return Health(False, exc.message)
        ms = (time.monotonic() - t0) * 1000
        if status == 200:
            ids = [str(m.get("id")) for m in (data or {}).get("data", []) if isinstance(m, dict)]
            return Health(True, "ok", ids, latency_ms=ms)
        return Health(False, f"HTTP {status}", latency_ms=ms)
