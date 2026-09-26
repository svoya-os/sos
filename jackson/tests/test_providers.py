# SPDX-License-Identifier: Apache-2.0
import io
import json
import threading
import time
import unittest

from jackson.config import ProviderConfig, build_config, DEFAULTS
from jackson.providers import (AnthropicProvider, CancelToken, Cancelled, ChatRequest, End, GeminiProvider,
                               OpenAIProvider, Progress, ProviderError, TextDelta, ToolCall, ToolSpec, Usage,
                               cost_eur)
from jackson.providers.base import ThinkFilter
from jackson.providers.gemini import sanitize_schema
from tests.fakes import FakeAnthropic, FakeGemini, FakeOpenAI

TOOLS = [ToolSpec("fs__read", "Read a file", {"type": "object", "properties": {"path": {"type": "string"}},
                                              "required": ["path"], "additionalProperties": False})]


def collect(provider, req, cancel=None):
    events = list(provider.stream(req, cancel or CancelToken()))
    text = "".join(e.text for e in events if isinstance(e, TextDelta))
    calls = [e for e in events if isinstance(e, ToolCall)]
    usage = next(e for e in events if isinstance(e, Usage))
    end = events[-1]
    assert isinstance(end, End)
    return text, calls, usage, end


class OpenAICompatibleTest(unittest.TestCase):
    def test_text_tools_and_usage(self) -> None:
        script = [{"text": "Сейчас посмотрю.", "tool_calls": [{"name": "fs__read", "args": {"path": "~/a.md"}}],
                   "in": 321, "out": 17}]
        with FakeOpenAI(script) as srv:
            prov = OpenAIProvider(ProviderConfig("local", base_url=f"http://127.0.0.1:{srv.port}/v1", local=True))
            text, calls, usage, end = collect(prov, ChatRequest("qwen3.5-4b", "system!", [
                {"role": "user", "content": "прочитай a.md"}], TOOLS))
            body = srv.requests[0]
        self.assertEqual(text, "Сейчас посмотрю.")
        self.assertEqual([(c.name, c.args) for c in calls], [("fs__read", {"path": "~/a.md"})])
        self.assertEqual((usage.input_tokens, usage.output_tokens, usage.estimated), (321, 17, False))
        self.assertEqual(end.stop_reason, "tool_calls")
        self.assertEqual(body["messages"][0], {"role": "system", "content": "system!"})
        self.assertTrue(body["stream"])
        self.assertEqual(body["tools"][0]["function"]["name"], "fs__read")
        self.assertEqual(body["stream_options"], {"include_usage": True})
        self.assertNotIn("chat_template_kwargs", body)           # thinking is the server's default

    def test_local_models_answer_without_thinking_first(self) -> None:
        # ISO #13: llama.cpp's Qwen3.5 template thinks by default ("thinking = 1"); on a CPU that is
        # minutes of text nobody sees. The shipped local providers ask it not to.
        from jackson.config import DEFAULTS, build_config
        cfg = build_config(DEFAULTS)
        self.assertFalse(cfg.providers["local"].thinking)
        self.assertFalse(cfg.providers["ollama"].thinking)
        self.assertTrue(cfg.providers["anthropic"].thinking)
        with FakeOpenAI([{"text": "ok"}]) as srv:
            prov = OpenAIProvider(ProviderConfig("local", base_url=f"http://127.0.0.1:{srv.port}/v1", local=True,
                                                 thinking=False))
            collect(prov, ChatRequest("m", "", [{"role": "user", "content": "q"}], TOOLS))
            self.assertEqual(srv.requests[0]["chat_template_kwargs"], {"enable_thinking": False})

    def _refusing(self, srv, key: str, message: str) -> None:
        """Make *srv* answer 400 to a request that carries *key*, as a server that does not know it."""
        original = srv._handler()

        class Refusing(original):  # type: ignore[misc, valid-type]
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length)
                body = json.loads(raw or b"{}")
                if key in body:
                    srv.requests.append(body)
                    self._json(400, {"error": {"message": message, "type": "invalid_request_error"}})
                    return
                self.rfile = io.BytesIO(raw)
                self.headers.replace_header("Content-Length", str(len(raw)))
                super().do_POST()

        srv.httpd.RequestHandlerClass = Refusing

    def test_a_server_without_template_options_is_asked_again_without_them(self) -> None:
        with FakeOpenAI([{"text": "ok"}]) as srv:
            self._refusing(srv, "chat_template_kwargs", "unknown field chat_template_kwargs")
            prov = OpenAIProvider(ProviderConfig("local", base_url=f"http://127.0.0.1:{srv.port}/v1", local=True,
                                                 thinking=False))
            text, _calls, _usage, _end = collect(prov, ChatRequest("m", "", [{"role": "user", "content": "q"}], TOOLS))
        self.assertEqual(text, "ok")
        self.assertEqual(["chat_template_kwargs" in r for r in srv.requests], [True, False])

    def test_a_local_server_says_how_far_it_has_read_the_prompt(self) -> None:
        # ISO #15: the runner's CPU read Jackson's 2,949-token prompt for six and a half minutes with
        # nothing on the wire. llama.cpp reports every batch it has read when asked (return_progress).
        script = [{"text": "ok", "progress": [(2000, 3000, 2000), (2512, 3000, 2000), (3000, 3000, 2000)]}]
        with FakeOpenAI(script) as srv:
            prov = OpenAIProvider(ProviderConfig("local", base_url=f"http://127.0.0.1:{srv.port}/v1", local=True))
            events = list(prov.stream(ChatRequest("m", "", [{"role": "user", "content": "q"}], TOOLS),
                                      CancelToken()))
            body = srv.requests[0]
        self.assertTrue(body["return_progress"])
        progress = [e for e in events if isinstance(e, Progress)]
        # the 2,000 tokens reused from the cache are not read again: 0 → 512 → 1,000 of 1,000
        self.assertEqual([(p.done, p.todo) for p in progress], [(0, 1000), (512, 1000), (1000, 1000)])
        self.assertEqual(progress[1].ms, 40 * 512)
        first_text = next(i for i, e in enumerate(events) if isinstance(e, TextDelta))
        self.assertLess(events.index(progress[-1]), first_text)
        self.assertEqual("".join(e.text for e in events if isinstance(e, TextDelta)), "ok")

    def test_cloud_providers_are_not_asked_for_progress(self) -> None:
        with FakeOpenAI([{"text": "ok"}]) as srv:
            prov = OpenAIProvider(ProviderConfig("deepseek", base_url=f"http://127.0.0.1:{srv.port}/v1"))
            collect(prov, ChatRequest("m", "", [{"role": "user", "content": "q"}], TOOLS))
        self.assertNotIn("return_progress", srv.requests[0])

    def test_a_server_that_does_not_know_progress_is_asked_again_without_it(self) -> None:
        with FakeOpenAI([{"text": "ok"}]) as srv:
            self._refusing(srv, "return_progress", "Unrecognized request argument supplied: return_progress")
            prov = OpenAIProvider(ProviderConfig("local", base_url=f"http://127.0.0.1:{srv.port}/v1", local=True))
            text, _calls, _usage, _end = collect(prov, ChatRequest("m", "", [{"role": "user", "content": "q"}], TOOLS))
        self.assertEqual(text, "ok")
        self.assertEqual(["return_progress" in r for r in srv.requests], [True, False])

    def test_progress_keeps_a_slow_prompt_from_timing_out(self) -> None:
        # the read timeout is per read: a server that reads for longer than it, batch by batch, is fine
        script = [{"text": "ok", "progress": [(0, 2048, 0), (512, 2048, 0), (1024, 2048, 0), (1536, 2048, 0),
                                               (2048, 2048, 0)]}]
        with FakeOpenAI(script, delay=0.15) as srv:
            prov = OpenAIProvider(ProviderConfig("local", base_url=f"http://127.0.0.1:{srv.port}/v1", local=True,
                                                 timeout=0.5))
            t0 = time.monotonic()
            text, _calls, _usage, _end = collect(prov, ChatRequest("m", "", [{"role": "user", "content": "q"}], TOOLS))
        self.assertEqual(text, "ok")
        self.assertGreater(time.monotonic() - t0, 0.5)

    def test_replays_tool_calls_and_results(self) -> None:
        with FakeOpenAI([{"text": "ok"}]) as srv:
            prov = OpenAIProvider(ProviderConfig("local", base_url=f"http://127.0.0.1:{srv.port}/v1", local=True))
            msgs = [{"role": "user", "content": "q"},
                    {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "name": "fs__read",
                                                                          "args": {"path": "x"}}]},
                    {"role": "tool", "tool_call_id": "c1", "name": "fs__read", "content": "data"}]
            collect(prov, ChatRequest("m", "", msgs, TOOLS))
            sent = srv.requests[0]["messages"]
        self.assertEqual(sent[1]["tool_calls"][0]["function"], {"name": "fs__read", "arguments": '{"path": "x"}'})
        self.assertEqual(sent[2], {"role": "tool", "tool_call_id": "c1", "content": "data"})

    def test_http_errors_are_classified(self) -> None:
        with FakeOpenAI(status=401) as srv:
            prov = OpenAIProvider(ProviderConfig("x", base_url=f"http://127.0.0.1:{srv.port}/v1"))
            with self.assertRaises(ProviderError) as ctx:
                collect(prov, ChatRequest("m", "", [{"role": "user", "content": "q"}]))
        self.assertEqual(ctx.exception.kind, "auth")
        self.assertFalse(ctx.exception.retryable)
        with FakeOpenAI(status=503) as srv:
            prov = OpenAIProvider(ProviderConfig("x", base_url=f"http://127.0.0.1:{srv.port}/v1"))
            with self.assertRaises(ProviderError) as ctx:
                collect(prov, ChatRequest("m", "", [{"role": "user", "content": "q"}]))
        self.assertTrue(ctx.exception.retryable)

    def test_connection_refused_is_network_error(self) -> None:
        prov = OpenAIProvider(ProviderConfig("local", base_url="http://127.0.0.1:9/v1", local=True, connect_timeout=1))
        with self.assertRaises(ProviderError) as ctx:
            collect(prov, ChatRequest("m", "", [{"role": "user", "content": "q"}]))
        self.assertEqual(ctx.exception.kind, "network")
        self.assertFalse(prov.health(timeout=0.5).ok)

    def test_health_lists_models(self) -> None:
        with FakeOpenAI(models=["qwen3.5-4b", "qwen3.5-14b"]) as srv:
            h = OpenAIProvider(ProviderConfig("local", base_url=f"http://127.0.0.1:{srv.port}/v1", local=True)).health()
        self.assertTrue(h.ok)
        self.assertEqual(h.models, ["qwen3.5-4b", "qwen3.5-14b"])

    def test_cancel_stops_stream(self) -> None:
        def slow(body):
            time.sleep(0.05)
            return {"text": "x" * 400}
        with FakeOpenAI(slow, chunk=1, delay=0.002) as srv:
            prov = OpenAIProvider(ProviderConfig("local", base_url=f"http://127.0.0.1:{srv.port}/v1", local=True))
            cancel = CancelToken()
            seen = []
            with self.assertRaises((Cancelled, ProviderError)):
                for ev in prov.stream(ChatRequest("m", "", [{"role": "user", "content": "q"}]), cancel):
                    seen.append(ev)
                    if len(seen) == 3:
                        threading.Timer(0.01, cancel.cancel).start()
                        time.sleep(0.05)
        self.assertLess(len(seen), 400)

    def test_think_filter(self) -> None:
        f = ThinkFilter()
        out = "".join(f.feed(p) for p in ["Ok <thi", "nk>secret reasoning</th", "ink>\nAnswer", " done"]) + f.flush()
        self.assertEqual(out, "Ok Answer done")


class AnthropicTest(unittest.TestCase):
    def test_stream_with_thinking_and_tool(self) -> None:
        script = [{"thinking": "let me think", "text": "Читаю.",
                   "tool_calls": [{"name": "fs__read", "args": {"path": "~/b.md"}, "id": "toolu_9"}],
                   "in": 50, "cache_read": 1000, "out": 22}]
        with FakeAnthropic(script) as srv:
            prov = AnthropicProvider(ProviderConfig("anthropic", kind="anthropic",
                                                    base_url=f"http://127.0.0.1:{srv.port}"), api_key="sk-test")
            text, calls, usage, end = collect(prov, ChatRequest("claude-sonnet-5", "sys", [
                {"role": "user", "content": "прочитай b"}], TOOLS))
            hdr = srv.headers[0]
            body = srv.requests[0]
        self.assertEqual(text, "Читаю.")
        self.assertEqual((calls[0].id, calls[0].name, calls[0].args), ("toolu_9", "fs__read", {"path": "~/b.md"}))
        self.assertEqual((usage.input_tokens, usage.output_tokens), (1050, 22))
        self.assertAlmostEqual(usage.billable_input, 50 + 100.0)
        self.assertEqual(hdr.get("x-api-key"), "sk-test")
        self.assertEqual(hdr.get("anthropic-version"), "2023-06-01")
        self.assertEqual(body["tools"][0]["input_schema"]["required"], ["path"])
        self.assertEqual(body["system"][0]["cache_control"], {"type": "ephemeral"})
        native = end.native["content"]
        self.assertEqual([b["type"] for b in native], ["thinking", "text", "tool_use"])
        self.assertEqual(native[0]["signature"], "sig-abc")

        # The native blocks (with the thinking signature) are replayed verbatim to the same provider.
        with FakeAnthropic([{"text": "Готово."}]) as srv2:
            prov.cfg.base_url = f"http://127.0.0.1:{srv2.port}"
            history = [{"role": "user", "content": "прочитай b"},
                       {"role": "assistant", "content": text, "native": end.native,
                        "tool_calls": [{"id": "toolu_9", "name": "fs__read", "args": {"path": "~/b.md"}}]},
                       {"role": "tool", "tool_call_id": "toolu_9", "name": "fs__read", "content": "file!"},
                       {"role": "user", "content": "и что?"}]
            collect(prov, ChatRequest("claude-sonnet-5", "sys", history, TOOLS))
            sent = srv2.requests[0]["messages"]
        self.assertEqual(sent[1]["content"][0]["signature"], "sig-abc")
        self.assertEqual(sent[2]["role"], "user")
        self.assertEqual(sent[2]["content"][0]["type"], "tool_result")
        self.assertEqual(sent[2]["content"][1], {"type": "text", "text": "и что?"})

    def test_stream_error_event(self) -> None:
        with FakeAnthropic([{"text": "part", "error": True}]) as srv:
            prov = AnthropicProvider(ProviderConfig("anthropic", kind="anthropic",
                                                    base_url=f"http://127.0.0.1:{srv.port}"), api_key="k")
            with self.assertRaises(ProviderError) as ctx:
                collect(prov, ChatRequest("m", "", [{"role": "user", "content": "q"}]))
        self.assertTrue(ctx.exception.retryable)
        self.assertIn("overloaded", str(ctx.exception))


class GeminiTest(unittest.TestCase):
    def test_stream_function_call_and_signature_replay(self) -> None:
        script = [{"text": "Смотрю", "tool_calls": [{"name": "fs__read", "args": {"path": "c.md"}}]}]
        with FakeGemini(script) as srv:
            prov = GeminiProvider(ProviderConfig("gemini", kind="gemini", base_url=f"http://127.0.0.1:{srv.port}"),
                                  api_key="g-key")
            text, calls, usage, end = collect(prov, ChatRequest("gemini-3.8-flash", "sys", [
                {"role": "user", "content": "q"}], TOOLS))
            hdr = srv.headers[0]
            body = srv.requests[0]
        self.assertEqual(text, "Смотрю")
        self.assertEqual((calls[0].name, calls[0].args), ("fs__read", {"path": "c.md"}))
        self.assertTrue(calls[0].id.startswith("gemini-local-"))
        self.assertEqual((usage.input_tokens, usage.output_tokens), (90, 12))
        self.assertEqual(hdr.get("x-goog-api-key"), "g-key")
        self.assertNotIn("additionalProperties", body["tools"][0]["functionDeclarations"][0]["parameters"])
        self.assertEqual(body["systemInstruction"], {"parts": [{"text": "sys"}]})
        with FakeGemini([{"text": "ok"}]) as srv2:
            prov.cfg.base_url = f"http://127.0.0.1:{srv2.port}"
            history = [{"role": "user", "content": "q"},
                       {"role": "assistant", "content": text, "native": end.native,
                        "tool_calls": [{"id": calls[0].id, "name": "fs__read", "args": {"path": "c.md"}}]},
                       {"role": "tool", "tool_call_id": calls[0].id, "name": "fs__read", "content": "data"}]
            collect(prov, ChatRequest("gemini-3.8-flash", "", history, TOOLS))
            sent = srv2.requests[0]["contents"]
        model_parts = sent[1]["parts"]
        self.assertTrue(any(p.get("thoughtSignature") == "sig-fs__read" for p in model_parts))
        fr = sent[2]["parts"][0]["functionResponse"]
        self.assertEqual(fr, {"name": "fs__read", "response": {"result": "data"}})

    def test_schema_sanitizer(self) -> None:
        s = sanitize_schema({"type": "object", "additionalProperties": False, "$schema": "x",
                             "properties": {"a": {"type": ["string", "null"], "default": "q"}}})
        self.assertEqual(s, {"type": "object", "properties": {"a": {"type": "string", "nullable": True}}})


class PricingTest(unittest.TestCase):
    def test_cost(self) -> None:
        cfg = build_config(dict(DEFAULTS))
        cost, est = cost_eur(cfg, "anthropic", "claude-sonnet-5", False, Usage(1_000_000, 100_000))
        self.assertAlmostEqual(cost, 1.72 + 0.86, places=4)
        self.assertFalse(est)
        self.assertEqual(cost_eur(cfg, "local", "qwen", True, Usage(10 ** 6, 10 ** 6)), (0.0, False))
        cost, est = cost_eur(cfg, "anthropic", "claude-unknown", False, Usage(1000, 1000))
        self.assertTrue(est)
        self.assertGreater(cost, 0)


if __name__ == "__main__":
    unittest.main()
