"""`sos morse` (and `sos sos`) and the hidden teapot."""
import argparse
import contextlib
import io
import os
import wave

from svoya_cli import commands, fun
from svoya_cli.main import main as sos_main

from .helpers import FakeRunner, SandboxTest, capture


def morse_args(*text, **kw):
    base = {"text": list(text), "wpm": 20, "quiet": False, "no_sound": False, "json": False}
    base.update(kw)
    return argparse.Namespace(**base)


class MorseTest(SandboxTest):
    def test_code(self):
        self.assertEqual(fun.pretty(fun.encode("SOS")), "··· ——— ···")
        self.assertEqual(fun.pretty(fun.encode("сос")), "··· ——— ···")
        self.assertEqual(fun.pretty(fun.encode("Привет, мир!")), "·——· ·—· ·· ·—— · — ——··—— / —— ·· ·—· —·—·——")
        self.assertEqual(fun.encode("😀 ☕"), [])

    def test_timing_and_sound(self):
        words = fun.encode("sos")
        pieces = fun.timeline(words, 20)                 # a unit is 60 ms at 20 wpm
        self.assertAlmostEqual(sum(s for _, s in pieces), 27 * 0.06)        # 5 + 3 + 11 + 3 + 5 units
        self.assertAlmostEqual(sum(s for tone, s in pieces if tone), 15 * 0.06)
        self.assertAlmostEqual(sum(s for _, s in fun.timeline(fun.encode("e e"), 20)), 9 * 0.06)
        with wave.open(io.BytesIO(fun.wav_bytes(pieces))) as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, fun.RATE))
            self.assertAlmostEqual(w.getnframes() / fun.RATE, 27 * 0.06 + 0.05, places=2)

    def test_plays_with_pipewire_and_cleans_up(self):
        runner = FakeRunner(responses={"pw-play": ""}, available={"pw-play", "aplay"})
        rc = fun.main_morse(morse_args("sos"), self.sb.ctx(runner))
        self.assertEqual(rc, 0)
        (call,) = runner.calls
        self.assertEqual(call[0], "pw-play")
        self.assertTrue(call[1].endswith(".wav"))
        self.assertFalse(os.path.exists(call[1]))        # the temporary WAV is gone
        self.assertIn("··· ——— ···", self.output())
        self.assertNotIn("no sound", self.output())

    def test_without_a_player_prints_only(self):
        rc = fun.main_morse(morse_args(), self.sb.ctx(FakeRunner()))
        self.assertEqual(rc, 0)
        self.assertIn("··· ——— ···  SOS", self.output())      # the default call sign
        self.assertIn("no sound", self.output())
        self.buf.truncate(0)
        self.buf.seek(0)
        runner = FakeRunner(available={"pw-play"})
        fun.main_morse(morse_args("sos", no_sound=True), self.sb.ctx(runner))
        self.assertEqual(runner.calls, [])
        self.assertNotIn("no sound", self.output())

    def test_json_and_nothing_to_send(self):
        rv, out = capture(fun.main_morse, morse_args("a", json=True, no_sound=True), self.sb.ctx(FakeRunner()))
        self.assertIn('"morse": "·—"', out)
        self.assertEqual(fun.main_morse(morse_args("😀"), self.sb.ctx(FakeRunner())), 2)

    def test_words(self):
        n = commands.normalize
        self.assertEqual(n(["морзе", "привет"]), ["morse", "привет"])
        self.assertEqual(n(["морзянка"]), ["morse"])
        self.assertEqual(n(["sos"]), ["morse"])                     # `sos sos` sends SOS
        self.assertEqual(n(["чай"]), ["tea"])
        self.assertEqual(n(["coffee"]), ["tea"])


class TeapotTest(SandboxTest):
    def test_hidden_but_works(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()) as buf:
            sos_main(["--help"])
        out = buf.getvalue()
        self.assertIn("morse", out)
        self.assertNotIn("tea", out.replace("steam", ""))
        self.assertNotIn("tea", commands.known_words())
        self.assertNotIn("чай", commands.complete(["ч"]))
        self.assertEqual(fun.main_tea(None, self.sb.ctx()), 0)
        self.assertIn("418 I'm a teapot", self.output())
