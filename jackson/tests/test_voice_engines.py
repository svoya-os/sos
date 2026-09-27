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

from jackson.voice.tts import ENGINE_DIRS, PREFERENCE, engine_class, installed_engines, pick_engine


class FakeSupertonic:
    """What the engine uses of `supertonic.TTS`."""

    made: list = []

    def __init__(self, model, model_dir, auto_download):
        assert (model, auto_download) == ("supertonic-3", False)
        self.model = types.SimpleNamespace(text_processor=self)
        self.model_dir = Path(model_dir)
        self.sample_rate = 44100
        self.voice_style_names = ["F1", "M1", "M2", "M3", "M5"]
        self.styles = []
        self.calls = []
        FakeSupertonic.made.append(self)

    def validate_text(self, text):
        unknown = sorted({c for c in text if c in "№☺"})
        return not unknown, unknown

    def get_voice_style(self, voice_name):
        self.styles.append(voice_name)
        return ("style", voice_name)

    def synthesize(self, text, voice_style, total_steps, speed, lang, max_chunk_length):
        assert max_chunk_length > len(text)                         # one chunk: cut where speech ends
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


    def test_a_sentence_can_be_said_slower(self):
        self.assertTrue(self.tts.speeds)
        self.tts.synth("Спокойной ночи.", "ru", "kent", speed=0.9)
        self.assertAlmostEqual(self.fake.calls[-1][3], 1.05 * 0.9)

    def test_a_character_it_does_not_know_does_not_silence_the_sentence(self):
        self.tts.synth("Дом №5 ☺ готов.", "ru", "kent")
        self.assertEqual(self.fake.calls[-1][0], "Дом 5 готов.")
        self.assertEqual(len(self.tts.synth("☺", "ru", "kent")), 0)      # nothing left to say
        self.assertEqual(len(self.fake.calls), 1)


class PickTest(unittest.TestCase):
    def test_the_best_installed_engine_is_picked(self):
        with tempfile.TemporaryDirectory() as models:
            self.assertEqual(pick_engine(models, gpu=True), "none")
            (Path(models) / ENGINE_DIRS["supertonic"]).mkdir()
            self.assertEqual(pick_engine(models, gpu=True), "supertonic")
            (Path(models) / ENGINE_DIRS["qwen3"]).mkdir()
            self.assertEqual(pick_engine(models, gpu=True), "qwen3")
            # Jackson's own voice is slower than speech on a processor: without the NVIDIA driver
            # (the card taken out, a driver that failed) he speaks with Supertonic
            self.assertEqual(pick_engine(models, gpu=False), "supertonic")
            self.assertEqual(installed_engines(models, gpu=True), ["qwen3", "supertonic"])
        self.assertEqual(PREFERENCE[0], "qwen3")


class FakeQwen:
    """What the engine uses of `qwen_tts.Qwen3TTSModel`."""

    made: list = []

    def __init__(self, path, device_map, dtype):
        self.path, self.device_map, self.dtype = path, device_map, dtype
        self.prompts = []
        self.said = []

    @classmethod
    def from_pretrained(cls, path, device_map, dtype):
        m = cls(path, device_map, dtype)
        cls.made.append(m)
        return m

    def create_voice_clone_prompt(self, ref_audio, ref_text):
        self.prompts.append((Path(ref_audio).parent.name, Path(ref_audio).name, ref_text))
        return ("prompt", Path(ref_audio).parent.name, Path(ref_audio).name)

    def generate_voice_clone(self, text, language, voice_clone_prompt):
        self.said.append((text, language, voice_clone_prompt))
        return [np.zeros(2400, dtype=np.float32)], 24000


@unittest.skipIf(np is None, "numpy")
class QwenTest(unittest.TestCase):
    def setUp(self):
        self.saved = {k: sys.modules.get(k) for k in ("torch", "qwen_tts")}
        cuda = types.SimpleNamespace(is_available=lambda: True)
        sys.modules["torch"] = types.SimpleNamespace(cuda=cuda, bfloat16="bf16", float32="f32")
        sys.modules["qwen_tts"] = types.SimpleNamespace(Qwen3TTSModel=FakeQwen)
        self.tts = engine_class("qwen3")(models="/srv/ai/voice")
        self.fake = FakeQwen.made[-1]

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    def test_the_characters_voices_ship_with_jackson(self):
        self.assertEqual(self.tts.voices(), ["dispatcher", "kent", "pirate", "sysop"])
        self.assertEqual((self.fake.device_map, self.fake.dtype), ("cuda:0", "bf16"))
        self.assertTrue(self.fake.path.endswith("qwen3-tts/Qwen3-TTS-12Hz-0.6B-Base"))
        for voice in self.tts.voices():
            for lang in ("ru", "en"):
                wav, text = self.tts.reference(voice, lang)
                self.assertEqual(wav.name, f"reference-{lang}.wav")
                self.assertIn("Джексон" if lang == "ru" else "Jackson", text)

    def test_each_language_is_cloned_from_its_own_clip_once(self):
        self.tts.synth("Привет.", "ru", "kent")
        self.tts.synth("Ещё раз.", "ru", "kent")
        self.tts.synth("Hello.", "en", "kent")
        self.assertEqual([p[:2] for p in self.fake.prompts], [("kent", "reference-ru.wav"), ("kent", "reference-en.wav")])
        self.assertEqual([s[1] for s in self.fake.said], ["Russian", "Russian", "English"])

    def test_a_supertonic_voice_from_the_settings_means_its_character(self):
        self.assertEqual(self.tts.voice("M2"), "sysop")
        self.assertEqual(self.tts.voice("M1"), "kent")
        self.assertEqual(self.tts.voice("F3"), "kent")           # no such character: Кентафурик
        self.assertEqual(self.tts.voice("pirate"), "pirate")


if __name__ == "__main__":
    unittest.main()
