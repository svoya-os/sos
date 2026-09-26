# SPDX-License-Identifier: Apache-2.0
"""Talking to Jackson through jacksond, with a scripted voice service in place of svoya-voice."""

import asyncio
import json
import unittest

from jackson.client import connect
from jackson.daemon import JacksonService
from tests.fakes import FakeOpenAI, make_app, rmtree, short_tmpdir
from tests.test_daemon import until


class FakeVoice:
    """Speaks the voice service protocol: hears `heard` for a tap, nothing when following."""

    def __init__(self, path, heard="расскажи о себе", ready=True):
        self.path = path
        self.heard = heard
        self.follow_heard = ""
        self.hold_spoken = False
        self.ready = ready
        self.got = []
        self.writers = []
        self.server = None

    async def start(self):
        self.server = await asyncio.start_unix_server(self.handle, path=str(self.path))

    async def close(self):
        for w in self.writers:
            w.close()
        self.server.close()
        await self.server.wait_closed()

    def said(self):
        return [m for m in self.got if m["type"] == "say"]

    async def handle(self, reader, writer):
        self.writers.append(writer)

        async def send(msg):
            writer.write(json.dumps(msg, ensure_ascii=False).encode() + b"\n")
            await writer.drain()

        while True:
            raw = await reader.readline()
            if not raw:
                return
            msg = json.loads(raw)
            self.got.append(msg)
            kind, tid = msg["type"], msg.get("id")
            if kind == "status":
                await send({"type": "status", "ready": self.ready, "stt": "fake", "tts": "fake", "voices": ["kent"],
                            "readsNumbers": False})
            elif kind == "listen" and msg["mode"] == "follow" and self.follow_heard:
                await send({"type": "transcript", "id": tid, "text": self.follow_heard, "ms": 90})
            elif kind == "listen" and msg["mode"] == "follow":
                await send({"type": "level", "id": tid, "source": "mic", "level": 0.1})
                await send({"type": "nothing", "id": tid})
            elif kind == "listen" and not self.heard:
                await send({"type": "nothing", "id": tid})
            elif kind == "listen":
                await send({"type": "level", "id": tid, "source": "mic", "level": 0.6})
                await send({"type": "speech", "id": tid, "state": "start"})
                await send({"type": "speech", "id": tid, "state": "end"})
                await send({"type": "transcript", "id": tid, "text": self.heard, "ms": 120})
            elif kind == "say" and msg.get("final") and not self.hold_spoken:
                await send({"type": "level", "id": tid, "source": "voice", "level": 0.4})
                await send({"type": "spoken", "id": tid, "hushed": False})
            elif kind == "hush" and tid:
                await send({"type": "spoken", "id": tid, "hushed": True})


class VoiceProtocolTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.srv = FakeOpenAI([{"text": "Привет! Я Джексон, громкость 70%."}]).start()
        self.app = make_app(self.root, f"http://127.0.0.1:{self.srv.port}/v1")

    def tearDown(self):
        self.srv.close()
        rmtree(self.root)

    def run_async(self, scenario, voice=True, **kw):
        async def main():
            svc = JacksonService(self.app, health_interval=60)
            svc.voice.link.retry_s = 0.05
            fake = FakeVoice(self.app.paths.socket.parent / "voice.sock", **kw) if voice else None
            await svc.start()
            if fake:
                await fake.start()
            task = asyncio.get_running_loop().create_task(svc.serve_forever(handle_signals=False))
            try:
                return await scenario(svc, fake)
            finally:
                if fake:
                    await fake.close()
                svc.request_stop()
                await asyncio.wait_for(task, 10)
        return asyncio.run(main())

    async def ready_client(self, svc):
        for _ in range(100):
            if svc.voice.available:
                break
            await asyncio.sleep(0.02)
        conn = await connect(self.app.paths.socket)
        welcome = await conn.hello("shell", "ru")
        return conn, welcome

    def test_a_spoken_question_is_answered_out_loud_and_the_mic_opens_again(self):
        async def scenario(svc, fake):
            conn, welcome = await self.ready_client(svc)
            self.assertIn("voice", welcome["capabilities"])
            await conn.send({"type": "listen", "id": "t1", "action": "start", "mode": "tap"})
            events = await until(conn, ("done",), "t1")
            listen = [e for e in events if e["type"] == "listen"]
            self.assertEqual(listen[0]["state"], "listening")
            transcript = next(e for e in events if e["type"] == "transcript")
            self.assertEqual((transcript["id"], transcript["text"], transcript["lang"]), ("t1", "расскажи о себе", "ru"))
            self.assertIn("level", [e["type"] for e in events])
            rest = await until(conn, ("listen",), timeout=5)
            spoken = next(e for e in rest if e["type"] == "spoken")
            self.assertEqual(spoken, {"type": "spoken", "id": "t1", "hushed": False})
            follow = rest[-1]
            self.assertEqual((follow["state"], follow["mode"], follow["follow"]), ("listening", "follow", "t1"))
            nothing = await until(conn, ("listen",), follow["id"], timeout=5)
            self.assertEqual(nothing[-1]["state"], "nothing")
            idle = await until(conn, ("state",), follow["id"], timeout=5)
            self.assertEqual(idle[-1]["state"], "idle")
            # the answer went to the voice sentence by sentence, numbers spelled out, in the persona's voice
            said = fake.said()
            self.assertEqual([m["text"] for m in said], ["Привет!", "Я Джексон, громкость семьдесят процентов.", ""])
            self.assertTrue(said[-1]["final"])
            self.assertTrue(all(m["voice"] == "kent" and m["lang"] == "ru" for m in said))
            # the model knew the answer would be heard, not read
            self.assertIn("сказано голосом", self.srv.requests[-1]["messages"][-1]["content"])
            self.assertEqual([m["mode"] for m in fake.got if m["type"] == "listen"], ["tap", "follow"])
            # while the voice was still talking the scope said so
            states = [e["state"] for e in events + rest if e["type"] == "state" and e.get("id") == "t1"]
            self.assertEqual(states[-1], "speaking")
            await conn.close()
        self.run_async(scenario)

    def test_saying_thanks_after_an_answer_ends_the_conversation(self):
        async def scenario(svc, fake):
            conn, _ = await self.ready_client(svc)
            fake.follow_heard = "Спасибо, всё!"
            await conn.send({"type": "listen", "id": "t1", "action": "start", "mode": "tap"})
            await until(conn, ("done",), "t1")
            rest = await until(conn, ("listen",), timeout=5)
            follow_id = rest[-1]["id"]
            events = await until(conn, ("spoken",), follow_id, timeout=5)
            self.assertEqual(next(e for e in events if e["type"] == "token")["text"], "Ок, я тут, если что.")
            self.assertEqual(len(self.srv.requests), 1)            # no second question for the model
            self.assertEqual(fake.said()[-2]["text"], "Ок, я тут, если что.")
            idle = await until(conn, ("state",), follow_id, timeout=5)
            self.assertEqual(idle[-1]["state"], "idle")
            await asyncio.sleep(0.1)
            self.assertEqual([m["mode"] for m in fake.got if m["type"] == "listen"], ["tap", "follow"])
            await conn.close()
        self.run_async(scenario)

    def test_a_held_key_is_one_question_without_a_follow_up(self):
        async def scenario(svc, fake):
            conn, _ = await self.ready_client(svc)
            await conn.send({"type": "listen", "id": "t1", "action": "start", "mode": "hold"})
            await conn.send({"type": "listen", "id": "t1", "action": "stop"})
            events = await until(conn, ("spoken",), "t1")
            self.assertIn("done", [e["type"] for e in events])
            idle = await until(conn, ("state",), "t1", timeout=5)
            self.assertEqual(idle[-1]["state"], "idle")
            self.assertEqual([m["type"] for m in fake.got if m["type"] in ("listen", "stop")], ["listen", "stop"])
            await conn.close()
        self.run_async(scenario)

    def test_a_typed_question_silences_jackson_and_is_not_read_out(self):
        async def scenario(svc, fake):
            fake.hold_spoken = True                   # the answer is still being said…
            conn, _ = await self.ready_client(svc)
            await conn.send({"type": "listen", "id": "t1", "action": "start", "mode": "tap"})
            await until(conn, ("done",), "t1")
            await conn.send({"type": "ask", "id": "t2", "text": "расскажи о себе"})   # …and the user types
            events = await until(conn, ("done",), "t2")
            spoken = next(e for e in events if e["type"] == "spoken")
            self.assertEqual((spoken["id"], spoken["hushed"]), ("t1", True))
            self.assertIn({"type": "hush", "id": "t1"}, fake.got)
            self.assertFalse(any(m.get("id") == "t2" for m in fake.said()))      # typed answers stay silent
            self.assertEqual([m["mode"] for m in fake.got if m["type"] == "listen"], ["tap"])   # no follow-up
            await conn.close()
        self.run_async(scenario)

    def test_the_button_while_jackson_talks_interrupts_him(self):
        async def scenario(svc, fake):
            fake.hold_spoken = True
            conn, _ = await self.ready_client(svc)
            await conn.send({"type": "listen", "id": "t1", "action": "start", "mode": "tap"})
            await until(conn, ("done",), "t1")
            fake.heard = ""                            # the second press hears nothing
            await conn.send({"type": "listen", "id": "t2", "action": "start", "mode": "tap"})
            events = await until(conn, ("spoken",), "t1", timeout=5)
            self.assertTrue(events[-1]["hushed"])
            self.assertIn({"type": "hush", "id": "t1"}, fake.got)
            await conn.close()
        self.run_async(scenario)

    def test_without_the_voice_service_listening_is_unavailable(self):
        async def scenario(svc, _fake):
            conn = await connect(self.app.paths.socket)
            welcome = await conn.hello("shell", "ru")
            self.assertNotIn("voice", welcome["capabilities"])
            await conn.send({"type": "listen", "id": "t1", "action": "start"})
            events = await until(conn, ("listen",), "t1", timeout=5)
            self.assertEqual(events[-1]["state"], "unavailable")
            await conn.close()
        self.run_async(scenario, voice=False)

    def test_the_first_press_starts_the_voice_service(self):
        async def scenario(svc, fake):
            await fake.close()
            started = []

            async def start():
                started.append(True)
                await fake.start()

            svc.voice.installed = lambda: True        # the voice module is installed, its service is not running
            svc.voice.start_service = start
            conn = await connect(self.app.paths.socket)
            welcome = await conn.hello("shell", "ru")
            self.assertIn("voice", welcome["capabilities"])   # the microphone can be offered already
            await conn.send({"type": "listen", "id": "t1", "action": "start", "mode": "tap"})
            events = await until(conn, ("transcript",), "t1", timeout=10)
            self.assertEqual([e["state"] for e in events if e["type"] == "listen"][:2], ["loading", "listening"])
            self.assertEqual(started, [True])
            await until(conn, ("done",), "t1")
            await conn.close()
        self.run_async(scenario)

    def test_clients_learn_when_the_voice_comes(self):
        async def scenario(svc, fake):
            await fake.close()
            conn = await connect(self.app.paths.socket)
            welcome = await conn.hello("shell", "ru")
            self.assertNotIn("voice", welcome["capabilities"])
            await fake.start()
            events = await until(conn, ("state",), timeout=5)
            self.assertEqual(events[-1]["detail"], "voice")
            self.assertIn("voice", events[-1]["capabilities"])
            await conn.close()
        self.run_async(scenario)


if __name__ == "__main__":
    unittest.main()
