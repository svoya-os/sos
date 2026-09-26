# SPDX-License-Identifier: Apache-2.0
"""The voice service with a scripted microphone, a fake recognizer and a tone for a voice."""

import asyncio
import unittest

try:
    import numpy as np
except ImportError:  # the voice service runs in the voice module's venv, which has numpy
    np = None

from jackson.voice.vad import FRAME, EndpointConfig, Endpointer

LOUD, QUIET = 0.9, 0.02


class EndpointerTest(unittest.TestCase):
    def feed(self, ep, probs):
        return [(i, e) for i, p in enumerate(probs) if (e := ep.push(p))]

    def test_a_phrase_starts_after_some_speech_and_ends_after_a_pause(self):
        cfg = EndpointConfig(start_ms=96, end_ms=320, wait_ms=3000)
        ep = Endpointer(cfg, "tap")
        events = self.feed(ep, [QUIET] * 5 + [LOUD] * 20 + [QUIET] * 20)
        self.assertEqual([e for _, e in events], ["start", "end"])
        self.assertEqual(events[0][0], 7)            # the third loud frame (3 × 32 ms)
        self.assertEqual(events[1][0], 24 + 10)      # ten quiet frames later

    def test_a_click_is_not_speech_and_silence_gives_up(self):
        ep = Endpointer(EndpointConfig(wait_ms=640), "tap")
        self.assertEqual([e for _, e in self.feed(ep, [LOUD, QUIET] * 15)], ["timeout"])

    def test_hold_ends_only_when_released(self):
        ep = Endpointer(EndpointConfig(end_ms=320, wait_ms=640), "hold")
        self.assertEqual([e for _, e in self.feed(ep, [QUIET] * 30 + [LOUD] * 5 + [QUIET] * 40)], ["start"])

    def test_follow_waits_less(self):
        ep = Endpointer(EndpointConfig(wait_ms=8000, follow_ms=320), "follow")
        self.assertEqual(self.feed(ep, [QUIET] * 20)[0], (9, "timeout"))


class FakeRecorder:
    def __init__(self, frames):
        self.script = frames
        self.closed = False

    async def start(self):
        pass

    async def frames(self):
        for amp in self.script:
            await asyncio.sleep(0.0005)
            yield (np.full(FRAME, amp * 20000, dtype=np.int16)).tobytes()

    async def close(self):
        self.closed = True
        return ""


class FakeVAD:
    def reset(self):
        pass

    def __call__(self, frame):
        return LOUD if np.abs(frame).mean() > 5000 else QUIET


class FakeSTT:
    name = "fake-stt"

    def __init__(self, text="какой сегодня день"):
        self.text = text
        self.heard = []

    def recognize(self, samples):
        self.heard.append(len(samples))
        return self.text


class FakePlayer:
    def __init__(self, rate, on_level):
        self.rate = rate
        self.on_level = on_level
        self.played = []
        self.hushed = False
        self.finished = False

    async def play(self, samples):
        for i in range(0, len(samples), 320):
            if self.hushed:
                return False
            await asyncio.sleep(0.001)
            self.on_level(0.5)
        self.played.append(len(samples))
        return True

    async def finish(self):
        self.finished = True

    async def hush(self):
        self.hushed = True


class Conn:
    def __init__(self):
        self.got = []
        self.closed = False

    async def send(self, msg):
        self.got.append(msg)

    def send_nowait(self, msg):
        self.got.append(msg)

    def last(self, skip=("level",)):
        return [m for m in self.got if m["type"] not in skip][-1]

    def kinds(self, skip=("level",)):
        return [m["type"] for m in self.got if m["type"] not in skip]


@unittest.skipUnless(np is not None, "numpy is in the voice module's venv")
class ServiceTest(unittest.TestCase):
    def make(self, script, stt=None):
        from jackson.voice.service import VoiceService
        from jackson.voice.tts import ToneTTS
        self.stt = stt or FakeSTT()
        self.tts = ToneTTS()
        self.players = []

        def player(rate, on_level):
            p = FakePlayer(rate, on_level)
            self.players.append(p)
            return p

        return VoiceService(load_stt=lambda: self.stt, load_tts=lambda: self.tts, load_vad=FakeVAD,
                            recorder=lambda: FakeRecorder(script), player=player,
                            endpoint=EndpointConfig(end_ms=320, wait_ms=960, follow_ms=320))

    async def drive(self, svc, *steps, settle=0.3):
        await svc.start()
        await asyncio.wait_for(svc.ready.wait(), 5)      # (a listen during loading gets `loading` first)
        conn = Conn()
        for step in steps:
            if isinstance(step, (int, float)):
                await asyncio.sleep(step)
            else:
                await svc.dispatch(conn, step)
        await asyncio.sleep(settle)
        for t in svc._tasks:
            t.cancel()
        return conn

    def test_a_phrase_becomes_text(self):
        svc = self.make([0] * 12 + [1] * 25 + [0] * 30)
        conn = asyncio.run(self.drive(svc, {"type": "listen", "id": "t1", "mode": "tap"}))
        self.assertEqual(conn.kinds(), ["speech", "speech", "transcript"])
        transcript = conn.got[-1]
        self.assertEqual((transcript["id"], transcript["text"]), ("t1", "какой сегодня день"))
        # the phrase with what came just before it (the first syllable is quiet), up to the pause
        self.assertGreaterEqual(self.stt.heard[0], (25 + 10) * FRAME)
        levels = [m for m in conn.got if m["type"] == "level"]
        self.assertTrue(levels and all(m["source"] == "mic" for m in levels))
        self.assertEqual(levels[-1]["level"], 0.0)

    def test_silence_is_nothing_and_nothing_is_recognized(self):
        svc = self.make([0] * 100)
        conn = asyncio.run(self.drive(svc, {"type": "listen", "id": "t1"}))
        self.assertEqual(conn.kinds(), ["nothing"])
        self.assertEqual(self.stt.heard, [])

    def test_no_microphone_says_so(self):
        svc = self.make([])
        conn = asyncio.run(self.drive(svc, {"type": "listen", "id": "t1"}))
        self.assertEqual(conn.kinds(), ["error"])
        self.assertIn("no microphone", conn.got[-1]["message"])

    def test_hold_is_heard_until_released(self):
        svc = self.make([1] * 400)
        conn = asyncio.run(self.drive(svc, {"type": "listen", "id": "t1", "mode": "hold"}, 0.05,
                                    {"type": "stop", "id": "t1"}))
        self.assertEqual(conn.kinds()[-1], "transcript")

    def test_it_speaks_sentence_by_sentence_and_says_when_it_is_done(self):
        svc = self.make([])
        conn = asyncio.run(self.drive(
            svc, {"type": "say", "id": "t1", "text": "Готово.", "lang": "ru", "voice": "kent"},
            {"type": "say", "id": "t1", "text": "Громкость семьдесят процентов.", "lang": "ru"},
            {"type": "say", "id": "t1", "text": "", "final": True}))
        self.assertEqual([t for t, _, _ in self.tts.said], ["Готово.", "Громкость семьдесят процентов."])
        self.assertEqual(conn.kinds(), ["spoken"])
        self.assertEqual(conn.last(), {"type": "spoken", "id": "t1", "hushed": False})
        self.assertEqual(conn.got[-1]["type"], "spoken")          # no level after the end
        self.assertEqual(len(self.players), 1)          # one stream for the whole answer
        self.assertTrue(self.players[0].finished)
        self.assertTrue(any(m["type"] == "level" and m["source"] == "voice" for m in conn.got))

    def test_hush_stops_the_answer_and_what_is_left_of_it(self):
        svc = self.make([])
        long = " ".join(["слово"] * 400)
        conn = asyncio.run(self.drive(svc, {"type": "say", "id": "t1", "text": long, "lang": "ru"}, 0.05,
                                    {"type": "hush"},
                                    {"type": "say", "id": "t1", "text": "ещё", "lang": "ru", "final": True}))
        self.assertEqual(conn.kinds(), ["spoken"])
        self.assertTrue(conn.last()["hushed"])
        self.assertTrue(self.players[0].hushed)
        self.assertNotIn("ещё", [t for t, _, _ in self.tts.said])

    def test_an_answer_hushed_before_it_starts_is_never_said(self):
        svc = self.make([])
        conn = asyncio.run(self.drive(svc, {"type": "hush", "id": "t1"},
                                      {"type": "say", "id": "t1", "text": "поздно", "lang": "ru"},
                                      {"type": "say", "id": "t1", "text": "", "final": True},
                                      {"type": "say", "id": "t2", "text": "другое", "lang": "ru", "final": True}))
        self.assertEqual([t for t, _, _ in self.tts.said], ["другое"])
        self.assertEqual([(m["id"], m["hushed"]) for m in conn.got if m["type"] == "spoken"],
                         [("t1", True), ("t2", False)])

    def test_listening_silences_the_voice_first(self):
        svc = self.make([0] * 60)
        long = " ".join(["слово"] * 400)
        conn = asyncio.run(self.drive(svc, {"type": "say", "id": "t1", "text": long, "lang": "ru"}, 0.05,
                                    {"type": "listen", "id": "t2"}))
        self.assertEqual(conn.kinds(), ["spoken", "nothing"])
        self.assertEqual(conn.got[[m["type"] for m in conn.got].index("spoken")]["id"], "t1")

    def test_status(self):
        svc = self.make([])
        conn = asyncio.run(self.drive(svc, 0.05, {"type": "status"}))
        status = conn.got[-1]
        self.assertTrue(status["ready"])
        self.assertEqual((status["stt"], status["tts"], status["voices"]), ("fake-stt", "tone", ["tone"]))

    def test_models_that_do_not_load_are_an_answer_not_a_crash(self):
        from jackson.voice.service import VoiceService

        def broken():
            raise FileNotFoundError("/srv/ai/voice/parakeet-tdt-0.6b-v3")

        svc = VoiceService(load_stt=broken, load_tts=lambda: None, load_vad=FakeVAD,
                           recorder=lambda: FakeRecorder([]))
        conn = asyncio.run(self.drive(svc, {"type": "listen", "id": "t1"}, {"type": "status"}))
        self.assertEqual(conn.kinds(), ["error", "status"])
        self.assertIn("parakeet", conn.got[0]["message"])
        self.assertFalse(conn.got[-1]["ready"])


if __name__ == "__main__":
    unittest.main()
