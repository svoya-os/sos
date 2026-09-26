# SPDX-License-Identifier: Apache-2.0
"""The turn engine: router + provider + tool loop, approvals, taint, fallbacks, cancel."""

import asyncio
import json
import os
import time
import unittest

from jackson.config import ProviderConfig
from jackson.engine import Session, Turn
from jackson.providers import AnthropicProvider, OpenAIProvider
from tests.fakes import FakeAnthropic, FakeOpenAI, asked, make_app, rmtree, short_tmpdir


async def run_turn(app, text, session=None, approve=None, context=None, route=None, turn_id="t-1",
                   cancel_after_tokens=None):
    events = []
    session = session or Session("test", "ru")
    turn_box = {}

    async def emit(ev):
        events.append(ev)
        if ev["type"] == "approval" and approve is not None:
            decision = approve(ev) if callable(approve) else approve
            asyncio.get_running_loop().call_soon(app.engine.resolve_approval, ev["callId"], decision)
        if cancel_after_tokens and ev["type"] == "token" and \
                sum(e["type"] == "token" for e in events) == cancel_after_tokens:
            turn_box["task"].cancel()

    turn = Turn(id=turn_id, session=session, text=text, emit=emit, context=context or {}, route=route)
    task = asyncio.get_running_loop().create_task(app.engine.run_turn(turn))
    turn_box["task"] = task
    await task
    return events


def kinds(events):
    return [e["type"] for e in events if e["type"] != "state"]


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.servers = []

    def tearDown(self):
        for s in self.servers:
            s.close()
        rmtree(self.root)

    def server(self, script, cls=FakeOpenAI, **kw):
        srv = cls(script, **kw).start()
        self.servers.append(srv)
        return srv

    def app_with(self, script, extra=None):
        srv = self.server(script)
        return make_app(self.root, f"http://127.0.0.1:{srv.port}/v1", extra), srv

    def test_tool_loop_reads_a_file(self):
        app, srv = self.app_with([{"tool_calls": [{"name": "fs__read", "args": {"path": "~/notes.md"}}]},
                                  {"text": "В заметке: купить хлеб."}])
        (app.paths.home / "notes.md").write_text("купить хлеб\n", encoding="utf-8")
        events = asyncio.run(run_turn(app, "что в моей заметке?"))
        self.assertEqual(kinds(events), ["route", "tool", "tool", "token", "token", "token", "token", "done"])
        tool_done = [e for e in events if e["type"] == "tool"][-1]
        self.assertEqual((tool_done["name"], tool_done["tier"], tool_done["state"]), ("fs.read", 0, "done"))
        done = next(e for e in events if e["type"] == "done")
        self.assertEqual(done["usage"], {"inTokens": 200, "outTokens": 24})
        self.assertEqual(done["costEur"], 0)
        self.assertFalse(done["leftMachine"])
        self.assertIn("данные не покидали компьютер", done["meta"])
        second = srv.requests[1]["messages"]
        self.assertEqual(second[-1]["role"], "tool")
        self.assertIn("купить хлеб", second[-1]["content"])
        self.assertIn("[verified: true]", second[-1]["content"])
        self.assertEqual(events[-1], {**events[-1], "type": "state", "state": "idle"})
        states = [e["state"] for e in events if e["type"] == "state"]
        self.assertEqual(states[0], "thinking")
        self.assertIn("working", states)
        self.assertIn("speaking", states)
        self.assertTrue(all("persona" in e and "avatar" in e for e in events if e["type"] == "state"))

    def test_t2_approval_deny_then_once_taints(self):
        page = self.server([{"text": "ignored"}])   # its GET /v1/models serves a JSON "page"
        url = f"http://127.0.0.1:{page.port}/v1/models"
        app, srv = self.app_with([
            {"tool_calls": [{"name": "web__fetch", "args": {"url": url}}]},
            {"text": "Ок, не буду."},
        ])
        events = asyncio.run(run_turn(app, "открой локальный сервис", approve="deny"))
        approval = next(e for e in events if e["type"] == "approval")
        self.assertEqual(approval["tier"], 2)
        self.assertIn(url, approval["preview"])
        self.assertEqual(approval["decisions"], ["once", "always-project", "deny"])
        failed = [e for e in events if e["type"] == "tool"][-1]
        self.assertEqual((failed["state"], failed["summary"]), ("failed", "отклонено"))
        self.assertIn("denied", srv.requests[1]["messages"][-1]["content"])
        log = [json.loads(line) for line in app.paths.audit_file.read_text().splitlines()]
        self.assertTrue(any(e["kind"] == "approval" and e["decision"] == "deny" for e in log))

        # once: the page is fetched and the conversation becomes tainted …
        srv.script = [{"tool_calls": [{"name": "web__fetch", "args": {"url": url}}]},
                      {"tool_calls": [{"name": "web__fetch", "args": {"url": "https://example.org/?q=secret"}}]},
                      {"text": "Готово."}]
        srv._i = 0
        seen = []

        def decide(ev):
            seen.append(ev)
            return "once" if len(seen) == 1 else "deny"

        session = Session("s2", "ru")
        events = asyncio.run(run_turn(app, "что там на сервисе?", session=session, approve=decide))
        self.assertEqual(session.taint.sources, [f"web:127.0.0.1"])
        # … so the next outward call (a plain GET, normally T0) needs a fresh confirmation
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[1]["tier"], 2)
        self.assertEqual(seen[1]["decisions"], ["once", "deny"])
        self.assertTrue(any("недоверенный" in r for r in seen[1]["reasons"]))
        done = next(e for e in events if e["type"] == "done")
        self.assertFalse(done["leftMachine"])  # loopback only; the example.org call was denied
        # the warning comes with the request (the system prompt stays the same), within this very turn
        self.assertNotIn("недоверенный", srv.requests[-1]["messages"][0]["content"])
        request = [m for m in srv.requests[-1]["messages"] if m["role"] == "user"][-1]["content"]
        self.assertIn("недоверенный контент", request)
        self.assertTrue(request.endswith("что там на сервисе?"))
        self.assertNotIn("недоверенный", session.history[-1][0]["content"])   # not kept in the history

    def test_always_project_grant(self):
        page = self.server([{"text": "x"}])
        url = f"http://127.0.0.1:{page.port}/v1/models"
        app, srv = self.app_with([{"tool_calls": [{"name": "web__fetch", "args": {"url": url}}]}, {"text": "ок"}])
        events = asyncio.run(run_turn(app, "проверь сервис", approve="always-project",
                                      context={"cwd": str(app.paths.home)}))
        self.assertEqual(sum(e["type"] == "approval" for e in events), 1)
        srv._i = 0
        events = asyncio.run(run_turn(app, "ещё раз", session=Session("fresh", "ru"), approve="deny"))
        self.assertEqual(sum(e["type"] == "approval" for e in events), 0)
        self.assertEqual(app.grants.list()[0]["tool"], "web.fetch")

    def test_secret_read_is_t4_once_only(self):
        app, srv = self.app_with([{"tool_calls": [{"name": "fs__read", "args": {"path": "~/.ssh/id_ed25519"}}]},
                                  {"tool_calls": [{"name": "fs__read", "args": {"path": "~/.ssh/id_ed25519"}}]},
                                  {"text": "ок"}])
        (app.paths.home / ".ssh").mkdir(parents=True)
        (app.paths.home / ".ssh" / "id_ed25519").write_text("KEY")
        asked = []
        events = asyncio.run(run_turn(app, "покажи ключ", approve=lambda ev: asked.append(ev) or "always-project"))
        self.assertEqual(len(asked), 1)          # granted for this task only…
        self.assertEqual(asked[0]["tier"], 4)
        self.assertEqual(asked[0]["decisions"], ["once", "deny"])
        self.assertEqual(app.grants.list(), [])  # …never as a standing grant
        self.assertEqual([e["state"] for e in events if e["type"] == "tool" and e["state"] != "running"],
                         ["done", "done"])

    def test_writes_snapshot_undo_and_journal(self):
        app, srv = self.app_with([{"tool_calls": [{"name": "fs__write", "args": {"path": "~/todo.md",
                                                                                "content": "- хлеб\n"}}]},
                                  {"text": "Записал."}])
        events = asyncio.run(run_turn(app, "запиши хлеб в todo"))
        done = next(e for e in events if e["type"] == "done")
        self.assertEqual(len(done["actions"]), 2)  # snapshot + file
        self.assertEqual(app.runner.snapshots, 1)
        self.assertTrue((app.paths.home / "todo.md").exists())
        journal = [e for e in events if e["type"] == "tool" and e["name"] == "memory.journal"]
        self.assertEqual(len(journal), 1)
        self.assertIn("хлеб", "".join(p.read_text() for p in (app.memory.dir / "journal").glob("*.md")))
        outcome = app.undo.undo(None, "ru")   # the file, not the snapshot or the journal
        self.assertTrue(outcome.ok, outcome.message)
        self.assertFalse((app.paths.home / "todo.md").exists())

    def test_max_steps(self):
        app, _ = self.app_with([{"tool_calls": [{"name": "fs__list", "args": {"path": "~"}}]}],
                               extra={"max_steps": 2})
        events = asyncio.run(run_turn(app, "бесконечный цикл"))
        tokens = "".join(e["text"] for e in events if e["type"] == "token")
        self.assertIn("слишком много шагов", tokens)
        self.assertEqual(kinds(events)[-1], "done")

    def test_unknown_tool_and_bad_arguments(self):
        app, srv = self.app_with([{"tool_calls": [{"name": "rm_rf", "args": {}},
                                                  {"name": "fs__read", "args": {"nope": 1}}]},
                                  {"text": "ок"}])
        events = asyncio.run(run_turn(app, "сделай что-нибудь"))
        failed = [e for e in events if e["type"] == "tool" and e["state"] == "failed"]
        self.assertEqual(len(failed), 2)
        tool_msgs = [m for m in srv.requests[1]["messages"] if m["role"] == "tool"]
        self.assertIn("Unknown tool", tool_msgs[0]["content"])
        self.assertIn("missing required argument", tool_msgs[1]["content"])

    def test_route_error_is_an_error_event(self):
        app = make_app(self.root, "http://127.0.0.1:9/v1")
        events = asyncio.run(run_turn(app, "расскажи о себе"))
        self.assertEqual(kinds(events), ["error"])
        error = next(e for e in events if e["type"] == "error")
        self.assertIn("Нет доступной модели", error["message"])
        self.assertTrue(error["retryable"])
        self.assertEqual(events[-1]["state"], "idle")

    def test_local_model_that_never_answers_says_what_to_do(self):
        # ISO #11: «The model failed: local: no answer from 127.0.0.1:8080 (timeout)» — true, and no help
        def hang(body):
            time.sleep(1.5)
            return {"text": "поздно"}
        srv = self.server(hang)
        url = f"http://127.0.0.1:{srv.port}/v1"
        app = make_app(self.root, url, providers={"local": OpenAIProvider(ProviderConfig(
            "local", base_url=url, local=True, region="local", label="llama.cpp", timeout=0.3))})
        events = asyncio.run(run_turn(app, "расскажи о себе"))
        error = next(e for e in events if e["type"] == "error")
        self.assertIn("Локальная модель так и не ответила", error["message"])
        self.assertIn("sos models serve --status", error["message"])
        self.assertNotIn("127.0.0.1", error["message"])
        self.assertTrue(error["retryable"])

    def test_a_slow_local_server_is_not_asked_again_with_another_model(self):
        # ISO #12: after a timeout the turn went on to the next local model — the same weights under
        # another name — and the server loaded a second copy on the same CPU
        def hang(body):
            time.sleep(1.0)
            return {"text": "поздно"}
        srv = self.server(hang, models=["qwen3.5-4b", "qwen3.5-9b"])
        url = f"http://127.0.0.1:{srv.port}/v1"
        app = make_app(self.root, url, providers={"local": OpenAIProvider(ProviderConfig(
            "local", base_url=url, local=True, region="local", label="llama.cpp", timeout=0.3))})
        events = asyncio.run(run_turn(app, "расскажи о себе"))
        routes = [e for e in events if e["type"] == "route"]
        self.assertEqual(len(routes), 1)
        self.assertEqual(len([r for r in srv.requests if r.get("stream")]), 1)
        self.assertEqual(kinds(events)[-1], "error")

    def test_a_local_model_reading_the_request_says_how_far_it_got(self):
        # ISO #15: minutes of «думаю…» on a CPU; the panel and `j` now show «читаю запрос… 45%»
        app, _srv = self.app_with([{"text": "Готово.",
                                    "progress": [(900, 1900, 900), (1412, 1900, 900), (1900, 1900, 900)]}])
        events = asyncio.run(run_turn(app, "расскажи о себе"))
        progress = [e for e in events if e["type"] == "progress"]
        self.assertEqual([(e["stage"], e["done"], e["total"]) for e in progress],
                         [("prompt", 0, 1000), ("prompt", 512, 1000), ("prompt", 1000, 1000)])
        self.assertTrue(all(e["id"] == "t-1" for e in progress))
        order = kinds(events)
        self.assertLess(order.index("progress"), order.index("token"))
        self.assertEqual(order[-1], "done")

    def test_local_model_that_is_not_running_says_how_to_start_it(self):
        from jackson.providers import ProviderError
        app = make_app(self.root, "http://127.0.0.1:9/v1")
        err = ProviderError("cannot connect to 127.0.0.1:9 (Connection refused)", kind="network", retryable=True,
                            provider="local")

        async def fail(turn):
            raise err
        app.engine._model_turn = fail
        events = asyncio.run(run_turn(app, "расскажи о себе"))
        error = next(e for e in events if e["type"] == "error")
        self.assertEqual(error["message"], "Локальная модель не запущена. Запустить: `sos models serve`.")

    def test_fallback_to_cloud_when_local_stream_fails(self):
        bad = self.server([{"text": "x"}], status=500)
        cloud = self.server([{"text": "Ответ из облака.", "in": 1000, "out": 100}], cls=FakeAnthropic)
        app = make_app(self.root, f"http://127.0.0.1:{bad.port}/v1", extra={"route": {"policy": "any"}},
                       providers={
                           "local": OpenAIProvider(ProviderConfig("local", base_url=f"http://127.0.0.1:{bad.port}/v1",
                                                                  local=True, region="local", label="llama.cpp")),
                           "anthropic": AnthropicProvider(ProviderConfig(
                               "anthropic", kind="anthropic", base_url=f"http://127.0.0.1:{cloud.port}",
                               needs_key=True, region="us", label="Anthropic", models=["claude-haiku-4-5"]),
                               api_key="sk-test")})
        events = asyncio.run(run_turn(app, "расскажи о себе"))
        routes = [e for e in events if e["type"] == "route"]
        self.assertEqual([r["provider"] for r in routes], ["local", "anthropic"])
        self.assertIn("переключаюсь", routes[1]["reason"])
        done = next(e for e in events if e["type"] == "done")
        self.assertTrue(done["leftMachine"])
        self.assertEqual(done["leftTo"], ["Anthropic"])
        self.assertAlmostEqual(done["costEur"], (1000 * 0.86 + 100 * 4.30) / 1e6, places=6)
        self.assertIn("данные отправлены: Anthropic", done["meta"])
        self.assertGreater(app.spend.today()["eur"], 0)
        # sos status reads this: back to local once the cloud turn is over
        self.assertEqual(json.loads((app.paths.runtime_dir / "ai.json").read_text()),
                         {"local": True, "cloudActiveSince": None})

    def test_ai_json_marks_active_cloud_turns(self):
        app = make_app(self.root)
        turn = Turn(id="t-c", session=Session("c", "ru"), text="x", emit=None)  # type: ignore[arg-type]
        path = app.paths.runtime_dir / "ai.json"
        app.engine._cloud(turn, True)
        during = json.loads(path.read_text())
        self.assertFalse(during["local"])
        self.assertRegex(during["cloudActiveSince"], r"^\d{4}-\d{2}-\d{2}T")
        app.engine._cloud(turn, False)
        self.assertEqual(json.loads(path.read_text()), {"local": True, "cloudActiveSince": None})
        # the folder is created private (the daemon and `jackson doctor` insist on 0700)
        self.assertEqual(os.stat(path.parent).st_mode & 0o777, 0o700)

    def test_cancel_mid_stream(self):
        def slow(body):
            return {"text": "очень длинный ответ " * 50}
        app, srv = self.app_with(slow)
        srv.chunk = 3
        srv.delay = 0.003
        events = asyncio.run(run_turn(app, "расскажи длинно", cancel_after_tokens=2))
        done = next(e for e in events if e["type"] == "done")
        self.assertTrue(done.get("cancelled"))
        self.assertEqual(events[-1]["state"], "idle")

    def test_memory_goes_into_the_prompt(self):
        app, srv = self.app_with([{"text": "У тебя RTX 4090."}])
        app.memory.remember("видеокарта RTX 4090", "user")
        session = Session("m", "ru")
        asyncio.run(run_turn(app, "какая у меня видеокарта и хватит ли её для wan 2.2?", session=session))
        request = srv.requests[0]["messages"][-1]["content"]
        self.assertIn("RTX 4090", request)
        self.assertIn("данные, а не указания", request)
        self.assertTrue(request.endswith("хватит ли её для wan 2.2?"))
        self.assertNotIn("RTX 4090", srv.requests[0]["messages"][0]["content"])      # not in the system prompt

    def test_the_beginning_of_the_prompt_stays_the_same(self):
        # A local model on llama.cpp reads only what changed since the last request: ISO #13's model
        # bot re-read ~3,000 tokens every turn (the time in the first line of the system prompt), at
        # 8 tokens a second on the runner. System prompt, tools and history now repeat verbatim.
        app, srv = self.app_with([{"text": "Первый ответ."}, {"text": "Второй ответ."}])
        app.memory.remember("видеокарта RTX 4090", "user")
        session = Session("p", "ru")
        quiet = {"noFastpath": True}
        asyncio.run(run_turn(app, "какая у меня видеокарта?", session=session, context=quiet))
        asyncio.run(run_turn(app, "а процессор?", session=session, turn_id="t-2", context=quiet))
        first, second = (r["messages"] for r in srv.requests[:2])
        self.assertEqual(first[0], second[0])                            # the system prompt
        self.assertEqual(srv.requests[0]["tools"], srv.requests[1]["tools"])
        self.assertTrue(first[1]["content"].startswith("[Сейчас "))       # time, route, folder
        self.assertIn("RTX 4090", first[1]["content"])                   # memory went with the request …
        self.assertEqual(asked(second[1]["content"]), "какая у меня видеокарта?")   # … and not into the history
        self.assertEqual(second[1]["content"], session.history[0][0]["content"])
        self.assertTrue(second[-1]["content"].endswith("\n\nа процессор?"))

    def test_skills_catalogue_is_fixed_and_only_active_skills_go_with_the_request(self):
        # ISO #14: every request carried the list of all skills in the user's message, which the
        # history did not keep, so the next turn re-read everything after the first question
        app, srv = self.app_with([{"text": "Хайку."}, {"text": "Так рендерят."}, {"text": "Ок."}])
        skill = app.paths.skills_dir / "video-render"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: video-render\ndescription: Render video with ComfyUI and Wan\n"
                                        "---\nCheck VRAM first.\n", encoding="utf-8")
        session = Session("k", "ru")
        quiet = {"noFastpath": True}
        asyncio.run(run_turn(app, "напиши хайку про море", session=session, context=quiet))
        asyncio.run(run_turn(app, "render video with comfyui", session=session, turn_id="t-2", context=quiet))
        asyncio.run(run_turn(app, "спасибо", session=session, turn_id="t-3", context=quiet))
        first, second, third = (r["messages"] for r in srv.requests[:3])
        self.assertIn("- video-render: Render video with ComfyUI and Wan", first[0]["content"])   # the catalogue
        self.assertEqual(first[0], third[0])
        self.assertEqual(first[1], second[1])                     # sent as it is kept: nothing to re-read
        self.assertNotIn("Check VRAM", first[1]["content"])
        self.assertIn("Check VRAM first.", second[-1]["content"])  # the active skill goes with its request …
        self.assertNotIn("Check VRAM", third[3]["content"])        # … and not into the history
        self.assertEqual(first[1:], third[1:2])

    def test_fastpath_turn(self):
        app, srv = self.app_with([{"text": "never"}])
        t0 = time.monotonic()
        events = asyncio.run(run_turn(app, "тише"))
        self.assertLess(time.monotonic() - t0, 0.7)
        self.assertEqual(kinds(events), ["route", "tool", "tool", "token", "done"])
        self.assertEqual(srv.requests, [])
        done = next(e for e in events if e["type"] == "done")
        self.assertEqual(done["model"], "fastpath")
        self.assertEqual(len(done["actions"]), 1)


if __name__ == "__main__":
    unittest.main()
