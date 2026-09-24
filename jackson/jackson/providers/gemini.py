# SPDX-License-Identifier: Apache-2.0
"""Google Gemini API: ``models/{model}:streamGenerateContent?alt=sse``.

The model's parts (including ``thoughtSignature`` fields that Gemini 3 function calling
requires on the next request) are kept and replayed verbatim.
"""

from __future__ import annotations

import json
import time
import urllib.parse
from typing import Any, Iterator

from .base import (ChatRequest, CancelToken, End, Event, Health, Provider, ProviderError, TextDelta,
                   ToolCall, Usage)
from .http import get_json, iter_sse, post_sse

LOCAL_ID_PREFIX = "gemini-local-"
_SCHEMA_KEYS = {"type", "format", "description", "nullable", "enum", "properties", "required", "items",
                "minItems", "maxItems", "minimum", "maximum", "anyOf", "minLength", "maxLength", "pattern",
                "title", "propertyOrdering"}


def sanitize_schema(schema: Any) -> Any:
    """Reduce a JSON Schema to the OpenAPI subset accepted by ``functionDeclarations.parameters``."""
    if isinstance(schema, list):
        return [sanitize_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key not in _SCHEMA_KEYS:
            continue
        if key == "type" and isinstance(value, list):
            types = [t for t in value if t != "null"]
            out["type"] = types[0] if types else "string"
            if "null" in value:
                out["nullable"] = True
        elif key == "properties" and isinstance(value, dict):
            out["properties"] = {k: sanitize_schema(v) for k, v in value.items()}
        elif key in ("items", "anyOf"):
            out[key] = sanitize_schema(value)
        else:
            out[key] = value
    return out


class GeminiProvider(Provider):
    kind = "gemini"

    def _headers(self) -> dict[str, str]:
        headers = dict(self.cfg.headers)
        if self.api_key:
            headers["x-goog-api-key"] = self.api_key
        return headers

    def build_contents(self, req: ChatRequest) -> list[dict[str, Any]]:
        contents: list[dict[str, Any]] = []

        def push(role: str, parts: list[dict[str, Any]]) -> None:
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"].extend(parts)
            else:
                contents.append({"role": role, "parts": list(parts)})

        for m in req.messages:
            role = m.get("role")
            if role == "user":
                parts: list[dict[str, Any]] = []
                if m.get("content"):
                    parts.append({"text": m["content"]})
                parts += [{"inlineData": {"mimeType": img["mime"], "data": img["data"]}}
                          for img in m.get("images") or []]
                push("user", parts or [{"text": "…"}])
            elif role == "assistant":
                native = self.replayable(m)
                if native:
                    parts = native
                else:
                    parts = [{"text": m["content"]}] if m.get("content") else []
                    for c in m.get("tool_calls") or []:
                        fc: dict[str, Any] = {"name": c["name"], "args": c.get("args") or {}}
                        if c.get("id") and not str(c["id"]).startswith(LOCAL_ID_PREFIX):
                            fc["id"] = c["id"]
                        parts.append({"functionCall": fc})
                push("model", parts or [{"text": "…"}])
            elif role == "tool":
                key = "error" if m.get("is_error") else "result"
                fr: dict[str, Any] = {"name": m.get("name", ""), "response": {key: m.get("content") or ""}}
                call_id = str(m.get("tool_call_id") or "")
                if call_id and not call_id.startswith(LOCAL_ID_PREFIX):
                    fr["id"] = call_id
                push("user", [{"functionResponse": fr}])
        return contents

    def build_payload(self, req: ChatRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contents": self.build_contents(req),
            "generationConfig": {"maxOutputTokens": req.max_tokens or self.cfg.max_tokens},
        }
        if req.system:
            payload["systemInstruction"] = {"parts": [{"text": req.system}]}
        if req.tools:
            payload["tools"] = [{"functionDeclarations": [
                {"name": t.name, "description": t.description, "parameters": sanitize_schema(t.parameters)}
                for t in req.tools]}]
        if req.temperature is not None:
            payload["generationConfig"]["temperature"] = req.temperature
        return payload

    def stream(self, req: ChatRequest, cancel: CancelToken) -> Iterator[Event]:
        model = urllib.parse.quote(req.model, safe="-._")
        url = f"{self.cfg.base_url}/v1beta/models/{model}:streamGenerateContent?alt=sse"
        conn, resp = post_sse(url, self.build_payload(req), self._headers(),
                              connect_timeout=self.cfg.connect_timeout, read_timeout=self.cfg.timeout,
                              use_proxy=not self.cfg.local, cancel=cancel, provider=self.name)
        try:
            yield from self._parse(resp, cancel)
        finally:
            conn.close()

    def _parse(self, resp: Any, cancel: CancelToken) -> Iterator[Event]:
        raw_parts: list[dict[str, Any]] = []
        in_tokens = out_tokens = 0
        stop = "STOP"
        n_calls = 0
        for _event, data in iter_sse(resp, cancel, self.name):
            try:
                chunk = json.loads(data)
            except ValueError:
                continue
            if isinstance(chunk, list):  # tolerate a JSON array framing
                chunk = chunk[0] if chunk else {}
            if not isinstance(chunk, dict):
                continue
            if chunk.get("error"):
                err = chunk["error"]
                raise ProviderError(f"stream error: {err.get('message', err)}", kind="server", retryable=True,
                                    provider=self.name)
            feedback = chunk.get("promptFeedback") or {}
            if feedback.get("blockReason"):
                raise ProviderError(f"the request was blocked by the provider ({feedback['blockReason']})",
                                    kind="bad_request", provider=self.name)
            for cand in (chunk.get("candidates") or [])[:1]:
                for part in (cand.get("content") or {}).get("parts") or []:
                    if not isinstance(part, dict):
                        continue
                    raw_parts.append(part)
                    if part.get("thought"):
                        continue
                    if part.get("text"):
                        yield TextDelta(part["text"])
                    fc = part.get("functionCall")
                    if isinstance(fc, dict):
                        n_calls += 1
                        call_id = fc.get("id") or f"{LOCAL_ID_PREFIX}{n_calls}"
                        args = fc.get("args") if isinstance(fc.get("args"), dict) else {}
                        yield ToolCall(str(call_id), str(fc.get("name", "")), args)
                if cand.get("finishReason"):
                    stop = cand["finishReason"]
            um = chunk.get("usageMetadata") or {}
            if um:
                in_tokens = int(um.get("promptTokenCount") or in_tokens)
                out_tokens = int(um.get("candidatesTokenCount") or 0) + int(um.get("thoughtsTokenCount") or 0) \
                    or out_tokens
        if stop in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII") and not raw_parts:
            raise ProviderError(f"the answer was blocked by the provider ({stop})", kind="bad_request",
                                provider=self.name)
        yield Usage(in_tokens, out_tokens)
        yield End("tool_calls" if n_calls else stop.lower(), {"provider": self.name, "content": raw_parts})

    def health(self, timeout: float = 2.0) -> Health:
        if not self.api_key:
            return Health(False, "no API key")
        t0 = time.monotonic()
        try:
            status, data = get_json(self.cfg.base_url + "/v1beta/models", self._headers(), timeout=timeout,
                                    use_proxy=not self.cfg.local, provider=self.name)
        except ProviderError as exc:
            return Health(False, exc.message)
        ms = (time.monotonic() - t0) * 1000
        if status == 200:
            ids = [str(m.get("name", "")).removeprefix("models/") for m in (data or {}).get("models", [])
                   if isinstance(m, dict)]
            return Health(True, "ok", ids, latency_ms=ms)
        return Health(False, f"HTTP {status}", latency_ms=ms)
