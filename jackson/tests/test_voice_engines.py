# SPDX-License-Identifier: Apache-2.0
"""Speech engines around their runtimes, with a stand-in for the runtime (the real models are
checked by the Voice workflow): which voice a character speaks with, how much of the sound is kept."""

import sys
import tempfile
import types
import unittest
from pathlib import Path

try:
    import numpy as np
except ImportError:  # the voice service runs in the voice module's venv, which has numpy
    np = None

from jackson.voice.tts import ENGINE_DIRS, PREFERENCE, engine_class, pick_engine


class FakeSupertonic:
    """What the engine uses of `supertonic.TTS`."""

    made: list = []

    def __init__(self, model, model_dir, auto_download):
        assert (model, auto_download) == ("supertonic-3", False)
        self.model_dir = Path(model_dir)
        self.sample_rate = 44100
        self.voice_style_names = ["F1", "M1", "M2", "M3", "M5"]
        self.styles = []
        self.calls = []
        FakeSupertonic.made.append(self)

    def get_voice_style(self, voice_name):
        self.styles.append(voice_name)
        return ("style", voice_name)

    def synthesize(self, text, voice_style, total_steps, speed, lang):
        self.calls.append((text, voice_style[1], total_steps, speed, lang))
        wav = np.ones((1, 44100 + 4410), dtype=np.float32)     # a bit of padding past the duration
        return wav, np.array([1.0], dtype=np.float32)


@unittest.skipIf(np is None, "numpy")
class SupertonicTest(unittest.TestCase):
    def setUp(self):
        self.saved = sys.modules.get("supertonic")
        sys.modules["supertonic"] = types.SimpleNamespace(TTS=FakeSupertonic)
        self.models = tempfile.mkdtemp()
        self.tts = engine_class("supertonic")(models=self.models)
        self.fake = FakeSupertonic.made[-1]

    def tearDown(self):
        if self.saved is None:
            sys.modules.pop("supertonic", None)
        else:
            sys.modules["supertonic"] = self.saved

    def test_it_loads_the_model_from_the_store_and_says_its_rate(self):
        self.assertEqual(self.fake.model_dir, Path(self.models) / "supertonic-3")
        self.assertEqual(self.tts.rate, 44100)
        self.assertFalse(self.tts.reads_numbers)

    def test_each_character_speaks_with_his_voice_and_a_voice_can_be_named(self):
        self.assertEqual(self.tts.voice("sysop"), "M2")
        self.assertEqual(self.tts.voice("pirate"), "M5")
        self.assertEqual(self.tts.voice("F1"), "F1")
        self.assertEqual(self.tts.voice("nobody"), "M1")

    def test_sound_ends_where_the_speech_does_and_styles_load_once(self):
        audio = self.tts.synth("Проверка связи.", "ru", "kent")
        self.tts.synth("Ещё раз.", "ru", "kent")
        self.tts.synth("Hello.", "en", "dispatcher")
        self.tts.synth("Hallo.", "xx", "kent")
        self.assertEqual(len(audio), 44100)
        self.assertEqual(self.fake.styles, ["M1", "M3"])
        self.assertEqual([c[4] for c in self.fake.calls], ["ru", "ru", "en", "na"])
        self.assertEqual(self.fake.calls[0][1:4], ("M1", 8, 1.05))


class PickTest(unittest.TestCase):
    def test_the_best_installed_engine_is_picked(self):
        with tempfile.TemporaryDirectory() as models:
            self.assertEqual(pick_engine(models), "none")
            (Path(models) / ENGINE_DIRS["supertonic"]).mkdir()
            self.assertEqual(pick_engine(models), "supertonic")
            (Path(models) / ENGINE_DIRS["qwen3"]).mkdir()
            self.assertEqual(pick_engine(models), "qwen3")
        self.assertEqual(PREFERENCE[0], "qwen3")


if __name__ == "__main__":
    unittest.main()
