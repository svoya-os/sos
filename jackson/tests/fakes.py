# SPDX-License-Identifier: Apache-2.0
"""Test doubles: streaming model servers (http.server in a thread) and a fake OS."""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from jackson.config import build_config, deep_merge, DEFAULTS
from jackson.paths import Paths
from jackson.runner import RunResult, Runner


def short_tmpdir() -> Path:
    """A temp dir with a short path (Unix socket paths are limited to ~108 bytes)."""
    base = tempfile.gettempdir()
    if len(base) > 40:
        base = "/tmp"
    return Path(tempfile.mkdtemp(prefix="jk", dir=base))


# ---------------------------------------------------------------------------
# streaming model servers

Reply = dict[str, Any]   # {"text": "..."} and/or {"tool_calls": [{"name", "args", "id"?}]}


class _Server:
    def __init__(self, script: list[Reply] | Callable[[dict[str, Any]], Reply] | None = None,
                 models: list[str] | None = None, status: int = 200, chunk: int = 7, delay: float = 0.0,
                 decide: Callable[[dict[str, Any]], dict[str, float]] | None = None) -> None:
        self.script = script if script is not None else [{"text": "Привет!"}]
        # decisions (non-streaming requests with logprobs): {first token: probability}
        self.decide = decide
        self.models = models or ["qwen3.5-4b"]
        self.status = status
        self.chunk = chunk
        self.delay = delay   # seconds between SSE events (for cancel/disconnect tests)
        self.requests: list[dict[str, Any]] = []
        self.headers: list[dict[str, str]] = []
        self._i = 0
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02},
                                       daemon=True)

    def __enter__(self) -> "_Server":
        self.thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def start(self) -> "_Server":
        return self.__enter__()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    @property
    def port(self) -> int:
        return self.httpd.server_address[1]

    def next_reply(self, body: dict[str, Any]) -> Reply:
        if callable(self.script):
            return self.script(body)
        reply = self.script[min(self._i, len(self.script) - 1)]
        self._i += 1
        return reply

    def pieces(self, text: str) -> list[str]:
        return [text[i:i + self.chunk] for i in range(0, len(text), self.chunk)] or [""]

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a: Any) -> None:  # silence
                pass

            def _json(self, code: int, obj: Any) -> None:
                raw = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:  # noqa: N802
                server.headers.append(dict(self.headers))
                server.handle_get(self)

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                server.requests.append(body)
                server.headers.append(dict(self.headers))
                if server.status != 200:
                    self._json(server.status, {"error": {"message": "boom", "type": "server_error"}})
                    return
                if body.get("logprobs") and not body.get("stream"):
                    probs = server.decide(body) if server.decide else {"A": 1.0}
                    ranked = sorted(probs.items(), key=lambda kv: -kv[1])
                    top = [{"token": tok, "logprob": math.log(pr)} for tok, pr in ranked]
                    self._json(200, {"choices": [{"index": 0, "finish_reason": "length",
                                                  "message": {"role": "assistant", "content": ranked[0][0]},
                                                  "logprobs": {"content": [{"token": ranked[0][0],
                                                                            "logprob": top[0]["logprob"],
                                                                            "top_logprobs": top}]}}]})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    for event in server.stream(self.path, body):
                        self.wfile.write(event.encode())
                        self.wfile.flush()
                        if server.delay:
                            time.sleep(server.delay)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # the client went away (cancel) — that's fine
                self.close_connection = True

        return H

    def handle_get(self, h: Any) -> None:
        h._json(200, {"object": "list", "data": [{"id": m, "object": "model"} for m in self.models]})

    def stream(self, path: str, body: dict[str, Any]) -> list[str]:  # pragma: no cover - abstract
        raise NotImplementedError


class FakeOpenAI(_Server):
    """OpenAI-compatible /v1/chat/completions (llama-server, Ollama, vLLM …)."""

    def stream(self, path: str, body: dict[str, Any]) -> list[str]:
        reply = self.next_reply(body)
        events = []

        def data(obj: Any) -> None:
            events.append(f"data: {json.dumps(obj, ensure_ascii=False)}\n\n")

        base = {"id": "chatcmpl-1", "object": "chat.completion.chunk", "model": body.get("model")}
        data({**base, "choices": [{"index": 0, "delta": {"role": "assistant"}}]})
        for piece in self.pieces(reply.get("text", "")) if reply.get("text") else []:
            data({**base, "choices": [{"index": 0, "delta": {"content": piece}}]})
        for i, call in enumerate(reply.get("tool_calls") or []):
            args = json.dumps(call.get("args", {}), ensure_ascii=False)
            data({**base, "choices": [{"index": 0, "delta": {"tool_calls": [
                {"index": i, "id": call.get("id", f"call_{i}"), "type": "function",
                 "function": {"name": call["name"], "arguments": ""}}]}}]})
            for piece in [args[j:j + 5] for j in range(0, len(args), 5)]:
                data({**base, "choices": [{"index": 0, "delta": {"tool_calls": [
                    {"index": i, "function": {"arguments": piece}}]}}]})
        finish = "tool_calls" if reply.get("tool_calls") else "stop"
        data({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]})
        if body.get("stream_options", {}).get("include_usage"):
            data({**base, "choices": [], "usage": {"prompt_tokens": reply.get("in", 100),
                                                   "completion_tokens": reply.get("out", 12)}})
        events.append("data: [DONE]\n\n")
        return events


class FakeAnthropic(_Server):
    """Anthropic Messages API with streaming SSE."""

    def handle_get(self, h: Any) -> None:
        h._json(200, {"data": [{"id": m, "type": "model"} for m in self.models]})

    def stream(self, path: str, body: dict[str, Any]) -> list[str]:
        reply = self.next_reply(body)
        events = []

        def ev(name: str, obj: Any) -> None:
            events.append(f"event: {name}\ndata: {json.dumps(obj, ensure_ascii=False)}\n\n")

        ev("message_start", {"type": "message_start", "message": {
            "id": "msg_1", "type": "message", "role": "assistant", "content": [], "model": body.get("model"),
            "usage": {"input_tokens": reply.get("in", 120), "output_tokens": 1,
                      "cache_read_input_tokens": reply.get("cache_read", 0)}}})
        ev("ping", {"type": "ping"})
        idx = 0
        if reply.get("thinking"):
            ev("content_block_start", {"type": "content_block_start", "index": idx,
                                       "content_block": {"type": "thinking", "thinking": ""}})
            ev("content_block_delta", {"type": "content_block_delta", "index": idx,
                                       "delta": {"type": "thinking_delta", "thinking": reply["thinking"]}})
            ev("content_block_delta", {"type": "content_block_delta", "index": idx,
                                       "delta": {"type": "signature_delta", "signature": "sig-abc"}})
            ev("content_block_stop", {"type": "content_block_stop", "index": idx})
            idx += 1
        if reply.get("text"):
            ev("content_block_start", {"type": "content_block_start", "index": idx,
                                       "content_block": {"type": "text", "text": ""}})
            for piece in self.pieces(reply["text"]):
                ev("content_block_delta", {"type": "content_block_delta", "index": idx,
                                           "delta": {"type": "text_delta", "text": piece}})
            ev("content_block_stop", {"type": "content_block_stop", "index": idx})
            idx += 1
        for call in reply.get("tool_calls") or []:
            args = json.dumps(call.get("args", {}), ensure_ascii=False)
            ev("content_block_start", {"type": "content_block_start", "index": idx, "content_block": {
                "type": "tool_use", "id": call.get("id", f"toolu_{idx}"), "name": call["name"], "input": {}}})
            for piece in [args[j:j + 4] for j in range(0, len(args), 4)]:
                ev("content_block_delta", {"type": "content_block_delta", "index": idx,
                                           "delta": {"type": "input_json_delta", "partial_json": piece}})
            ev("content_block_stop", {"type": "content_block_stop", "index": idx})
            idx += 1
        if reply.get("error"):
            ev("error", {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}})
            return events
        stop = "tool_use" if reply.get("tool_calls") else "end_turn"
        ev("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                             "usage": {"output_tokens": reply.get("out", 15)}})
        ev("message_stop", {"type": "message_stop"})
        return events


class FakeGemini(_Server):
    """Gemini streamGenerateContent?alt=sse."""

    def handle_get(self, h: Any) -> None:
        h._json(200, {"models": [{"name": f"models/{m}"} for m in self.models]})

    def stream(self, path: str, body: dict[str, Any]) -> list[str]:
        reply = self.next_reply(body)
        events = []
        for piece in self.pieces(reply.get("text", "")) if reply.get("text") else []:
            events.append("data: " + json.dumps({"candidates": [{"content": {"role": "model", "parts": [
                {"text": piece}]}}]}, ensure_ascii=False) + "\r\n\r\n")
        parts = []
        for call in reply.get("tool_calls") or []:
            parts.append({"functionCall": {"name": call["name"], "args": call.get("args", {})},
                          "thoughtSignature": "sig-" + call["name"]})
        final = {"candidates": [{"content": {"role": "model", "parts": parts or [{"text": ""}]},
                                 "finishReason": "STOP"}],
                 "usageMetadata": {"promptTokenCount": reply.get("in", 90), "candidatesTokenCount": reply.get("out", 9),
                                   "thoughtsTokenCount": 3, "totalTokenCount": 102}}
        events.append("data: " + json.dumps(final, ensure_ascii=False) + "\r\n\r\n")
        return events


# ---------------------------------------------------------------------------
# fake OS

class FakeRunner(Runner):
    """Simulates wpctl, brightnessctl, nmcli, bluetoothctl, loginctl, sos, systemd-run, notify-send…"""

    def __init__(self, paths: Paths | None = None, available: set[str] | None = None) -> None:
        self.paths = paths
        self.available = available if available is not None else {
            "wpctl", "brightnessctl", "nmcli", "bluetoothctl", "loginctl", "notify-send", "systemd-run",
            "systemctl", "sos", "grim", "pgrep", "gtk-launch", "ip"}
        self.volume = 0.40
        self.muted = False
        self.brightness = 12000
        self.max_brightness = 24000
        self.wifi = True
        self.bt = False
        self.locked = False
        self.theme = "graphite"
        self.timers: set[str] = set()
        self.calls: list[list[str]] = []
        self.snapshots = 0
        self.broken: set[str] = set()   # commands that "succeed" without an effect
        self.launched: list[str] = []
        self.accent: str | None = None  # None = the theme's default ("signal")
        self.spawned: list[tuple[float, list[str]]] = []   # (time.monotonic(), argv) of detached commands

    def which(self, name: str) -> str | None:
        return f"/usr/bin/{name}" if name in self.available else None

    def spawn(self, argv: Any, env: Any = None, cwd: Any = None) -> int | None:
        self.calls.append(list(argv))
        if argv[0] not in self.available:
            return None
        self.spawned.append((time.monotonic(), list(argv)))
        if argv[0] in ("sos", "svoya"):  # a detached sos command still has its effect
            self.run(argv)
            return 4243
        self.launched.append(" ".join(argv))
        return 4242

    def _write_theme(self) -> None:
        if self.paths is not None:
            self.paths.state_dir.mkdir(parents=True, exist_ok=True)
            self.paths.theme_json.write_text(json.dumps({"id": self.theme, "mode": "dark",
                                                         "accentId": self.accent or "signal"}), encoding="utf-8")

    ACCENT_WORDS = {"фиолетовым": "lilac", "фиолетовый": "lilac", "сирень": "lilac", "lilac": "lilac",
                    "violet": "lilac", "зеленый": "phosphor", "зелёный": "phosphor", "green": "phosphor",
                    "оранжевый": "amber", "amber": "amber", "mono": "mono", "моно": "mono", "синий": "ink",
                    "#ff8800": "custom"}
    ACCENT_NAMES = {"lilac": ("Lilac", "Сирень"), "phosphor": ("Phosphor", "Фосфор"), "amber": ("Amber", "Янтарь"),
                    "mono": ("Mono", "Моно"), "ink": ("Ink", "Чернила"), "signal": ("Signal", "Сигнал"),
                    "custom": ("Custom", "Свой")}

    def _accent(self, words: list[str]) -> RunResult:
        word = " ".join(words).lower()
        if word.startswith(("красн", "red")):
            return RunResult(2, json.dumps({"ok": False, "error": "red is reserved for errors", "hint": "rose"}))
        if word == "default":
            new = None
        elif word in self.ACCENT_WORDS:
            new = self.ACCENT_WORDS[word]
        else:
            return RunResult(2, json.dumps({"ok": False, "error": f"unknown accent: {word}", "hint": None}))
        prev, self.accent = self.accent, new
        if "accent" not in self.broken:
            self._write_theme()
        aid = new or "signal"
        en, ru = self.ACCENT_NAMES[aid]
        return RunResult(0, json.dumps({"ok": True, "accent": {"id": aid, "name": {"en": en, "ru": ru},
                                                               "color": "#bba4ff", "custom": word if aid == "custom" else None,
                                                               "adjusted": aid == "custom"},
                                        "changed": prev != new, "visible": prev != new,
                                        "previous": {"theme": self.theme, "accent": prev}}))

    def run(self, argv: Any, timeout: float = 5.0, env: Any = None, cwd: Any = None, input: Any = None) -> RunResult:
        argv = list(argv)
        self.calls.append(argv)
        cmd = argv[0]
        if cmd not in self.available:
            return RunResult(127, missing=True)
        a = argv[1:]
        if cmd == "wpctl":
            if a[0] == "get-volume":
                return RunResult(0, f"Volume: {self.volume:.2f}" + (" [MUTED]" if self.muted else "") + "\n")
            if a[0] == "set-volume":
                if "wpctl" in self.broken:
                    return RunResult(0)
                val = a[-1]
                if val.endswith("%+") or val.endswith("%-"):
                    delta = int(val[:-2]) / 100 * (1 if val.endswith("+") else -1)
                    self.volume = round(min(1.0, max(0.0, self.volume + delta)), 2)
                else:
                    self.volume = float(val.rstrip("%")) / (100 if val.endswith("%") else 1)
                return RunResult(0)
            if a[0] == "set-mute":
                self.muted = (not self.muted) if a[-1] == "toggle" else a[-1] == "1"
                return RunResult(0)
        if cmd == "brightnessctl":
            if a == ["-m"]:
                pct = round(100 * self.brightness / self.max_brightness)
                return RunResult(0, f"intel_backlight,backlight,{self.brightness},{pct}%,{self.max_brightness}\n")
            if "set" in a:
                val = a[-1]
                step = self.max_brightness * int(val.rstrip("%+-")) // 100
                if val.endswith("%+"):
                    self.brightness = min(self.max_brightness, self.brightness + step)
                elif val.endswith("%-"):
                    self.brightness = max(1, self.brightness - step)
                else:
                    self.brightness = step
                return RunResult(0)
        if cmd == "nmcli" and a[:2] == ["radio", "wifi"]:
            if len(a) == 2:
                return RunResult(0, "enabled\n" if self.wifi else "disabled\n")
            self.wifi = a[2] == "on"
            return RunResult(0)
        if cmd == "bluetoothctl":
            if a == ["show"]:
                return RunResult(0, f"Controller 00:11\n\tPowered: {'yes' if self.bt else 'no'}\n")
            if a[0] == "power":
                self.bt = a[1] == "on"
                return RunResult(0)
        if cmd == "loginctl":
            if a[0] == "show-user":
                return RunResult(0, "7\n")
            if a[0] == "lock-session":
                self.locked = True
                return RunResult(0)
            if a[0] == "show-session":
                return RunResult(0, "yes\n" if self.locked else "no\n")
        if cmd in ("sos", "svoya"):
            if a[:2] == ["theme", "apply"]:
                self.theme = {"auto": "paper"}.get(a[2], a[2])
                self._write_theme()
                return RunResult(0, f"applied {a[2]}\n")
            if a[:2] == ["snapshot", "create"]:
                self.snapshots += 1
                return RunResult(0, json.dumps({"id": f"snap-{self.snapshots}"}))
            if a[:1] == ["undo"]:
                return RunResult(0, "rolled back\n")
            if a[:2] == ["theme", "accent"]:
                return self._accent([x for x in a[2:] if x != "--json"])
            if a[:1] == ["ai"] and self.paths is not None:
                marker = self.paths.ai_off_markers[1]
                if a[1] == "off":
                    marker.parent.mkdir(parents=True, exist_ok=True)
                    marker.write_text("off\n")
                elif a[1] == "on" and marker.exists():
                    marker.unlink()
                return RunResult(0, f"ai {a[1]}\n")
            if a[:3] == ["models", "suggest", "--json"]:
                return RunResult(0, json.dumps({"hardware": {"backend": "cpu"}, "default": {
                    "id": "qwen3.5-4b:Q4_K_M", "name": "Qwen3.5 4B", "quant": "Q4_K_M", "sizeBytes": 3413361504,
                    "tokensPerSecond": 12}, "live": getattr(self, "live", False)}))
            if a[:2] == ["apps", "--json"]:
                return RunResult(0, json.dumps({"apps": [
                    {"key": "telegram", "name": "Telegram", "aliases": ["телеграм"], "installed": False},
                    {"key": "prism", "name": "Prism Launcher", "aliases": ["minecraft", "майнкрафт"], "installed": False},
                    {"key": "gimp", "name": "GIMP", "aliases": ["гимп"], "installed": True}]}))
            if a[:3] == ["modules", "list", "--json"]:
                return RunResult(0, json.dumps({"modules": [
                    {"id": "gaming", "name": {"en": "Gaming", "ru": "Игры"}, "aliases": ["steam", "стим"],
                     "installed": False}]}))
            if a[:2] == ["status", "--json"]:
                return RunResult(0, json.dumps({"gpu": [{"index": 0, "vendor": "nvidia", "name": "RTX 4090",
                                                         "vramUsedMiB": 11468, "vramTotalMiB": 24564, "tempC": 64,
                                                         "util": 93, "driver": "595.58", "ok": True}]}))
        if cmd == "systemd-run":
            unit = next(x.split("=", 1)[1] for x in a if x.startswith("--unit="))
            self.timers.add(unit)
            return RunResult(0)
        if cmd == "systemctl":
            if a[:2] == ["--user", "is-active"]:
                unit = a[2].removesuffix(".timer")
                return RunResult(0 if unit in self.timers else 3, "active\n" if unit in self.timers else "inactive\n")
            if a[:2] == ["--user", "stop"]:
                self.timers.discard(a[2].removesuffix(".timer"))
                return RunResult(0)
        if cmd == "notify-send":
            return RunResult(0)
        if cmd == "grim":
            Path(a[-1]).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 16)
            return RunResult(0)
        if cmd == "gtk-launch":
            self.launched.append(a[0])
            return RunResult(0)
        if cmd == "pgrep":
            name = a[-1]
            return RunResult(0, "4242\n") if any(name in x for x in self.launched) else RunResult(1)
        if cmd == "ip":
            return RunResult(0, json.dumps([{"ifname": "wlp1s0", "addr_info": [
                {"family": "inet", "local": "192.168.1.23"}]}]))
        return RunResult(1, err=f"fake: unsupported {argv}")


# ---------------------------------------------------------------------------

def make_config(base_url: str | None = None, extra: dict[str, Any] | None = None) -> Any:
    """Config with only a fake local provider (others removed) and no git in memory."""
    data = deep_merge(DEFAULTS, {"memory": {"git": False}, "snapshots": {"enabled": True}})
    data["providers"] = {}
    if base_url:
        data["providers"]["local"] = {"kind": "openai", "label": "llama.cpp", "base_url": base_url, "local": True,
                                      "region": "local", "needs_key": False, "models": [], "timeout": 10.0,
                                      "connect_timeout": 1.0}
    if extra:
        data = deep_merge(data, extra)
    return build_config(data)


def make_app(root: Path, base_url: str | None = None, extra: dict[str, Any] | None = None,
             runner: Runner | None = None, providers: Any = None) -> Any:
    from jackson.app import Jackson
    paths = Paths.for_root(root)
    paths.home.mkdir(parents=True, exist_ok=True)
    cfg = make_config(base_url, extra)
    return Jackson(paths=paths, config=cfg, runner=runner or FakeRunner(paths), providers=providers,
                   env={"HOME": str(paths.home)}, use_keyring=False)


def rmtree(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def install_desktop_entry(paths: Paths, app_id: str, name: str, exec_: str, names: str = "") -> None:
    d = paths.data_home / "applications"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{app_id}.desktop").write_text(
        f"[Desktop Entry]\nType=Application\nName={name}\n{names}\nExec={exec_}\n", encoding="utf-8")


def env_for(paths: Paths) -> dict[str, str]:
    return {"HOME": str(paths.home), "XDG_CONFIG_HOME": str(paths.config_home), "XDG_DATA_HOME": str(paths.data_home),
            "XDG_STATE_HOME": str(paths.state_home), "XDG_RUNTIME_DIR": str(paths.runtime_base),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
