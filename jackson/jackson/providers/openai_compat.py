# SPDX-License-Identifier: Apache-2.0
"""OpenAI-compatible Chat Completions (streaming).

Covers llama.cpp ``llama-server`` (also in router mode), Ollama, vLLM, LM Studio, DeepSeek,
Mistral and Gemini's OpenAI-compatible endpoint.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Iterator

from .base import (ChatRequest, CancelToken, End, Event, Health, Progress, Provider, ProviderError, TextDelta,
                   ThinkFilter, ToolCall, Usage, chars_to_tokens)

# what a server may not know: the request goes again without these when it answers 400 naming one
OPTIONAL = ("stream_options", "chat_template_kwargs", "return_progress")
from .http import get_json, iter_sse, post_sse


class OpenAIProvider(Provider):
    kind = "openai"

    def _headers(self) -> dict[str, str]:
        headers = dict(self.cfg.headers)
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # ------------------------------------------------------------------
    def build_messages(self, req: ChatRequest) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if req.system:
            out.append({"role": "system", "content": req.system})
        for m in req.messages:
            role = m.get("role")
            if role == "user":
                images = m.get("images") or []
                if images:
                    content: Any = [{"type": "text", "text": m.get("content") or ""}] + [
                        {"type": "image_url", "image_url": {"url": f"data:{img['mime']};base64,{img['data']}"}}
                        for img in images]
                else:
                    content = m.get("content") or ""
                out.append({"role": "user", "content": content})
            elif role == "assistant":
                msg: dict[str, Any] = {"role": "assistant", "content": m.get("content") or ""}
                native = self.replayable(m)
                if native:
                    msg["tool_calls"] = native
                elif m.get("tool_calls"):
                    msg["tool_calls"] = [
                        {"id": c["id"], "type": "function",
                         "function": {"name": c["name"], "arguments": json.dumps(c.get("args") or {},
                                                                                  ensure_ascii=False)}}
                        for c in m["tool_calls"]]
                out.append(msg)
            elif role == "tool":
                out.append({"role": "tool", "tool_call_id": m.get("tool_call_id", ""),
                            "content": m.get("content") or ""})
        return out

    def build_payload(self, req: ChatRequest, stream_usage: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": req.model, "messages": self.build_messages(req), "stream": True}
        if stream_usage:
            payload["stream_options"] = {"include_usage": True}
        if req.tools:
            payload["tools"] = [{"type": "function", "function": {
                "name": t.name, "description": t.description, "parameters": t.parameters}} for t in req.tools]
        max_tokens = req.max_tokens or self.cfg.max_tokens
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if req.temperature is not None:
            payload["temperature"] = req.temperature
        if not self.cfg.thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        if self.cfg.local:
            # llama.cpp says how far it has read the prompt (minutes on a CPU); others ignore it
            payload["return_progress"] = True
        return payload

    # ------------------------------------------------------------------
    def stream(self, req: ChatRequest, cancel: CancelToken) -> Iterator[Event]:
        url = self.cfg.base_url + "/chat/completions"
        stream_usage = self.cfg.stream_usage
        payload = self.build_payload(req, stream_usage)
        try:
            conn, resp = post_sse(url, payload, self._headers(),
                                  connect_timeout=self.cfg.connect_timeout, read_timeout=self.cfg.timeout,
                                  use_proxy=not self.cfg.local, cancel=cancel, provider=self.name)
        except ProviderError as exc:
            # a server that knows neither usage in the stream nor template options nor progress: without them
            if exc.kind != "bad_request" or not any(k in exc.message and k in payload for k in OPTIONAL):
                raise
            for key in OPTIONAL:
                payload.pop(key, None)
            conn, resp = post_sse(url, payload, self._headers(),
                                  connect_timeout=self.cfg.connect_timeout, read_timeout=self.cfg.timeout,
                                  use_proxy=not self.cfg.local, cancel=cancel, provider=self.name)
        try:
            yield from self._parse(resp, cancel, req)
        finally:
            conn.close()

    def _parse(self, resp: Any, cancel: CancelToken, req: ChatRequest) -> Iterator[Event]:
        calls: dict[int, dict[str, Any]] = {}
        usage: Usage | None = None
        stop = "stop"
        text_len = 0
        think = ThinkFilter()
        for _event, data in iter_sse(resp, cancel, self.name):
            if data.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except ValueError:
                continue
            if not isinstance(chunk, dict):
                continue
            if chunk.get("error"):
                err = chunk["error"]
                msg = err.get("message") if isinstance(err, dict) else str(err)
                raise ProviderError(f"stream error: {msg}", kind="server", retryable=True, provider=self.name)
            u = chunk.get("usage")
            if isinstance(u, dict) and (u.get("prompt_tokens") or u.get("completion_tokens")):
                usage = Usage(int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0))
            timings = chunk.get("timings")
            if usage is None and isinstance(timings, dict) and timings.get("predicted_n"):
                usage = Usage(int(timings.get("prompt_n") or 0), int(timings.get("predicted_n") or 0))
            progress = chunk.get("prompt_progress")
            if isinstance(progress, dict):
                try:
                    yield Progress(int(progress.get("processed") or 0), int(progress.get("total") or 0),
                                   int(progress.get("cache") or 0), float(progress.get("time_ms") or 0))
                except (TypeError, ValueError):
                    pass
            for choice in chunk.get("choices") or []:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta") or {}
                content = delta.get("content")
                if isinstance(content, str) and content:
                    visible = think.feed(content)
                    if visible:
                        text_len += len(visible)
                        yield TextDelta(visible)
                for tc in delta.get("tool_calls") or []:
                    if not isinstance(tc, dict):
                        continue
                    idx = int(tc.get("index", len(calls)) or 0)
                    acc = calls.setdefault(idx, {"id": "", "name": "", "args": "", "extra": {}})
                    if tc.get("id"):
                        acc["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    name = fn.get("name")
                    if name:
                        acc["name"] = name if not acc["name"] or acc["name"] == name else acc["name"] + name
                    if fn.get("arguments"):
                        acc["args"] += fn["arguments"]
                    for key, value in tc.items():
                        if key not in ("index", "id", "type", "function"):
                            acc["extra"][key] = value
                if choice.get("finish_reason"):
                    stop = choice["finish_reason"]
        rest = think.flush()
        if rest:
            text_len += len(rest)
            yield TextDelta(rest)
        native_calls = []
        for idx in sorted(calls):
            acc = calls[idx]
            call_id = acc["id"] or f"call_{uuid.uuid4().hex[:12]}"
            raw_args = acc["args"].strip() or "{}"
            error = None
            try:
                args = json.loads(raw_args)
                if not isinstance(args, dict):
                    args, error = {}, "arguments must be a JSON object"
            except ValueError:
                args, error = {}, f"arguments are not valid JSON: {raw_args[:200]}"
            native_calls.append({"id": call_id, "type": "function",
                                 "function": {"name": acc["name"], "arguments": raw_args}, **acc["extra"]})
            yield ToolCall(call_id, acc["name"], args, error=error, raw=acc["extra"])
        if usage is None:
            prompt_chars = len(req.system) + sum(len(str(m.get("content") or "")) for m in req.messages)
            usage = Usage(chars_to_tokens(prompt_chars), chars_to_tokens(text_len), estimated=True)
        yield usage
        yield End("tool_calls" if calls else stop,
                  {"provider": self.name, "content": native_calls} if native_calls else None)

    # ------------------------------------------------------------------
    def health(self, timeout: float = 1.0) -> Health:
        t0 = time.monotonic()
        base = self.cfg.base_url
        urls = [base + "/models"]
        if base.endswith("/v1"):
            urls.append(base[:-3] + "/models")  # llama-server router mode lists models at the root
        last = "unreachable"
        for url in urls:
            try:
                status, data = get_json(url, self._headers(), timeout=timeout, use_proxy=not self.cfg.local,
                                        provider=self.name)
            except ProviderError as exc:
                return Health(False, exc.message, latency_ms=(time.monotonic() - t0) * 1000)
            ms = (time.monotonic() - t0) * 1000
            if status == 200:
                return Health(True, "ok", _model_ids(data), latency_ms=ms)
            if status == 503:
                return Health(True, "loading", loading=True, latency_ms=ms)
            if status in (401, 403):
                return Health(False, f"HTTP {status}: check the API key", latency_ms=ms)
            last = f"HTTP {status}"
        return Health(False, last, latency_ms=(time.monotonic() - t0) * 1000)


def _model_ids(data: Any) -> list[str]:
    items: list[Any] = []
    if isinstance(data, dict):
        items = data.get("data") or data.get("models") or []
    elif isinstance(data, list):
        items = data
    ids = []
    for item in items:
        if isinstance(item, dict):
            mid = item.get("id") or item.get("name") or item.get("model")
            if mid:
                ids.append(str(mid))
        elif isinstance(item, str):
            ids.append(item)
    return ids
