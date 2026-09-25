# SPDX-License-Identifier: Apache-2.0
"""Socket protocol round-trips (ARCHITECTURE §4.3) against the real service and a fake model."""

import asyncio
import json
import os
import stat
import unittest

from jackson.client import connect
from jackson.daemon import JacksonService
from tests.fakes import FakeOpenAI, make_app, rmtree, short_tmpdir


async def until(conn, kinds_, turn_id=None, timeout=10.0, sink=None):
    """Read events until one of *kinds_* for *turn_id* arrives; returns all events read."""
    events = []
    while True:
        ev = await conn.recv(timeout=timeout)
        if ev is None:
            raise AssertionError(f"connection closed; got {events}")
        events.append(ev)
        if sink is not None:
            sink.append(ev)
        if ev.get("type") in kinds_ and (turn_id is None or ev.get("id") == turn_id):
            return events


class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.srv = FakeOpenAI([{"text": "Привет! Я Джексон."}]).start()
        self.app = make_app(self.root, f"http://127.0.0.1:{self.srv.port}/v1")

    def tearDown(self):
        self.srv.close()
        rmtree(self.root)

    def run_async(self, coro_fn):
        async def main():
            svc = JacksonService(self.app, health_interval=60)
            await svc.start()
            task = asyncio.get_running_loop().create_task(svc.serve_forever(handle_signals=False))
            try:
                return await coro_fn(svc)
            finally:
                svc.request_stop()
                await asyncio.wait_for(task, 10)
        return asyncio.run(main())

    def test_hello_ask_done_and_state_broadcast(self):
        async def scenario(svc):
            sock = self.app.paths.socket
            self.assertEqual(stat.S_IMODE(os.stat(sock).st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(os.stat(sock.parent).st_mode), 0o700)
            a, b = await connect(sock), await connect(sock)
            welcome = await a.hello("shell", "ru")
            for key in ("version", "models", "route", "persona", "avatar", "protocol"):
                self.assertIn(key, welcome)
            self.assertEqual(welcome["route"]["model"], "qwen3.5-4b")
            self.assertEqual(welcome["persona"]["id"], "kent")
            await b.hello("bar", "ru")
            await a.send({"type": "ask", "id": "t1", "text": "привет", "context": {"cwd": str(self.app.paths.home)}})
            events = await until(a, ("done",), "t1")
            types = [e["type"] for e in events if e["type"] != "state"]
            self.assertEqual(types[0], "route")
            self.assertEqual("".join(e["text"] for e in events if e["type"] == "token"), "Привет! Я Джексон.")
            done = events[-1]
            for key in ("usage", "costEur", "latencyMs", "leftMachine", "actions"):
                self.assertIn(key, done)
            # the other client sees the scope states of this turn, nothing else
            seen_b = await until(b, ("state",), timeout=5)
            self.assertEqual(seen_b[0]["id"], "t1")
            await a.close()
            await b.close()
        self.run_async(scenario)

    def test_cross_client_approval_and_status(self):
        page_url = f"http://127.0.0.1:{self.srv.port}/v1/models"
        self.srv.script = [{"tool_calls": [{"name": "web__fetch", "args": {"url": page_url}}]},
                           {"text": "Сервис жив."}]

        async def scenario(svc):
            sock = self.app.paths.socket
            a, b = await connect(sock), await connect(sock)
            await a.hello("cli", "ru")
            await b.hello("shell", "ru")
            await a.send({"type": "ask", "id": "t2", "text": "проверь сервис"})
            events = await until(a, ("approval",), "t2")
            approval = events[-1]
            self.assertEqual(approval["tier"], 2)
            for key in ("callId", "name", "preview", "tier"):
                self.assertIn(key, approval)
            await b.send({"type": "status"})
            st = await until(b, ("status",))
            self.assertEqual(st[-1]["pendingApprovals"][0]["callId"], approval["callId"])
            self.assertEqual(st[-1]["persona"]["id"], "kent")
            self.assertEqual(st[-1]["state"], "working")
            self.assertEqual(st[-1]["turns"][0]["id"], "t2")
            state_after = await until(b, ("state",))
            self.assertIn(state_after[-1]["state"], ("working", "thinking", "speaking"))
            await b.send({"type": "approve", "id": "t2", "callId": approval["callId"], "decision": "once"})
            events = await until(a, ("done",), "t2")
            tools = [e for e in events if e["type"] == "tool"]
            self.assertEqual(tools[-1]["state"], "done")
            # approving something unknown is an error, not a crash
            await b.send({"type": "approve", "callId": "nope", "decision": "once"})
            err = await until(b, ("error",))
            self.assertFalse(err[-1]["retryable"])
            await a.close()
            await b.close()
        self.run_async(scenario)

    def test_busy_cancel_and_bad_messages(self):
        self.srv.script = lambda body: {"text": "длинный ответ " * 300}
        self.srv.chunk = 2
        self.srv.delay = 0.003

        async def scenario(svc):
            a = await connect(self.app.paths.socket)
            await a.hello("cli", "ru")
            await a.send({"type": "ask", "id": "t3", "text": "расскажи длинную историю"})
            await until(a, ("token",), "t3")
            await a.send({"type": "ask", "id": "t4", "text": "ещё"})
            busy = await until(a, ("error",), "t4")
            self.assertTrue(busy[-1]["retryable"])
            await a.send({"type": "cancel", "id": "t3"})
            done = await until(a, ("done", "error"), "t3")
            self.assertTrue(done[-1].get("cancelled"))
            a.writer.write(b"{not json\n")
            await a.writer.drain()
            self.assertEqual((await until(a, ("error",)))[-1]["retryable"], False)
            await a.send({"type": "teleport", "id": "x"})     # unknown types are ignored (ARCHITECTURE §8)
            await a.send({"type": "ping", "id": "after-teleport"})
            self.assertEqual((await until(a, ("pong", "error")))[-1],
                             {"type": "pong", "id": "after-teleport"})
            await a.send({"type": "ask", "text": "без id"})
            self.assertIn("id", (await until(a, ("error",)))[-1]["message"])
            await a.send({"type": "ping", "id": "p"})
            self.assertEqual((await until(a, ("pong",)))[-1]["id"], "p")
            await a.close()
        self.run_async(scenario)

    def test_undo_over_the_socket(self):
        async def scenario(svc):
            a = await connect(self.app.paths.socket)
            await a.hello("cli", "ru")
            await a.send({"type": "ask", "id": "t5", "text": "громче"})
            done = (await until(a, ("done",), "t5"))[-1]
            self.assertEqual(len(done["actions"]), 1)
            self.assertAlmostEqual(self.app.runner.volume, 0.5)
            await a.send({"type": "undo", "id": "u1", "actionId": done["actions"][0]})
            events = await until(a, ("done", "error"), "u1")
            self.assertEqual(events[-1]["type"], "done")
            self.assertEqual(events[-1]["undone"], done["actions"])
            self.assertAlmostEqual(self.app.runner.volume, 0.4)
            await a.send({"type": "undo", "id": "u2", "actionId": done["actions"][0]})
            self.assertEqual((await until(a, ("done", "error"), "u2"))[-1]["type"], "error")
            await a.close()
        self.run_async(scenario)

    def test_disconnect_cancels_turn_and_shutdown_cleans_up(self):
        self.srv.script = lambda body: {"text": "медленно " * 400}
        self.srv.chunk = 1
        self.srv.delay = 0.003

        async def scenario(svc):
            a = await connect(self.app.paths.socket)
            await a.hello("cli", "ru")
            await a.send({"type": "ask", "id": "t6", "text": "говори долго"})
            await until(a, ("token",), "t6")
            await a.close()
            for _ in range(100):
                if not svc.clients:
                    break
                await asyncio.sleep(0.02)
            self.assertEqual(svc.clients, {})
            b = await connect(self.app.paths.socket)
            await b.hello("cli", "ru")
            await b.send({"type": "ask", "id": "t7", "text": "говори долго"})
            await until(b, ("token",), "t7")
            await svc.shutdown()
            events = await until(b, ("error",), "t7")
            self.assertTrue(events[-1]["retryable"])
            self.assertFalse(self.app.paths.socket.exists())
            await b.close()
        self.run_async(scenario)

    def test_refines_capabilities_and_ai_json(self):
        cloud_like = {"text": "Второй ответ."}
        self.srv.script = [{"text": "Первый ответ."}, cloud_like, cloud_like]

        async def scenario(svc):
            ai_json = self.app.paths.runtime_dir / "ai.json"
            self.assertEqual(json.loads(ai_json.read_text()), {"local": True, "cloudActiveSince": None})
            a = await connect(self.app.paths.socket)
            welcome = await a.hello("shell", "ru")
            self.assertIn("refines", welcome["capabilities"])
            self.assertNotIn("voice", welcome["capabilities"])
            await a.send({"type": "ask", "id": "r1", "text": "первый вопрос"})
            await until(a, ("done",), "r1")
            await a.close()
            b = await connect(self.app.paths.socket)   # a new connection (the panel was reopened)
            await b.hello("shell", "ru")
            await b.send({"type": "ask", "id": "r2", "text": "уточни", "refines": "r1"})
            await until(b, ("done",), "r2")
            sent = self.srv.requests[-1]["messages"]
            self.assertIn("первый вопрос", [m.get("content") for m in sent])   # context kept
            await b.send({"type": "ask", "id": "r3", "text": "с нуля", "new": True})
            await until(b, ("done",), "r3")
            self.assertNotIn("первый вопрос", [m.get("content") for m in self.srv.requests[-1]["messages"]])
            await b.close()
        self.run_async(scenario)

    def test_second_service_refuses_to_start(self):
        async def scenario(svc):
            other = JacksonService(self.app)
            with self.assertRaises(RuntimeError):
                await other.start()
        self.run_async(scenario)

    def test_audit_records_the_session(self):
        async def scenario(svc):
            a = await connect(self.app.paths.socket)
            await a.hello("cli", "ru")
            await a.send({"type": "ask", "id": "t8", "text": "привет"})
            await until(a, ("done",), "t8")
            await a.close()
        self.run_async(scenario)
        kinds = [json.loads(line)["kind"] for line in self.app.paths.audit_file.read_text().splitlines()]
        for k in ("service", "ask", "route"):
            self.assertIn(k, kinds)
        self.assertTrue(self.app.audit.verify().ok)


if __name__ == "__main__":
    unittest.main()
