# SPDX-License-Identifier: Apache-2.0
"""Speech engines for the voice service (registered in :data:`jackson.voice.tts.ENGINES`).

Each one imports its runtime when constructed, so the service loads only the engine it speaks
with, and has a ``fetch(models, fetch_dir)`` that ``python -m jackson.voice.setup`` uses to put its
files into the model store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

# Jackson's own voices: a short reference clip per voice (reference.wav + reference.txt), designed
# from a description with Qwen3-TTS VoiceDesign (tests/voice-samples) and cloned at run time.
VOICES_DIR = Path(__file__).resolve().parent / "voices"


class QwenTTS:
    """Qwen3-TTS (Apache-2.0): the Base model speaks in Jackson's designed voices, Russian and English
    in the same voice. 0.6B runs on a graphics card, or slowly on a fast processor."""

    name = "qwen3-tts"
    reads_numbers = True        # a language model reads «70%» and «15:30» by itself
    rate = 24000
    LANG = {"ru": "Russian", "en": "English"}

    def __init__(self, models: Any, size: str = "0.6B", device: str = "", voices: Any = None) -> None:
        import torch
        from qwen_tts import Qwen3TTSModel
        if not device:
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if device != "cpu" else torch.float32
        self.model = Qwen3TTSModel.from_pretrained(str(Path(models) / "qwen3-tts" / f"Qwen3-TTS-12Hz-{size}-Base"),
                                                   device_map=device, dtype=dtype)
        self.size = size
        self.voices_dir = Path(voices) if voices else VOICES_DIR
        self.prompts: dict[str, Any] = {}

    def voices(self) -> list[str]:
        if not self.voices_dir.is_dir():
            return []
        return sorted(d.name for d in self.voices_dir.iterdir() if (d / "reference.wav").is_file())

    def _prompt(self, voice: str) -> Any:
        if voice not in self.prompts:
            ref = self.voices_dir / voice
            self.prompts[voice] = self.model.create_voice_clone_prompt(
                ref_audio=str(ref / "reference.wav"), ref_text=(ref / "reference.txt").read_text(encoding="utf-8").strip())
        return self.prompts[voice]

    def synth(self, text: str, lang: str, voice: str) -> Any:
        known = self.voices()
        if not known:
            raise RuntimeError(f"no voices in {self.voices_dir}")
        voice = voice if voice in known else known[0]
        wavs, sr = self.model.generate_voice_clone(text=text, language=self.LANG.get(lang, "English"),
                                                   voice_clone_prompt=self._prompt(voice))
        self.rate = int(sr)
        return wavs[0]

    @staticmethod
    def fetch(models: Path, fetch_dir: Callable[..., None], size: str = "0.6B") -> None:
        from huggingface_hub import snapshot_download
        repo = f"Qwen/Qwen3-TTS-12Hz-{size}-Base"
        fetch_dir(Path(models) / "qwen3-tts" / f"Qwen3-TTS-12Hz-{size}-Base",
                  lambda d: snapshot_download(repo, local_dir=str(d)), f"Qwen3-TTS {size} Base")


class SupertonicTTS:
    """Supertonic 3 (Supertone: code MIT, model OpenRAIL-M): 31 languages in one ONNX model (Russian,
    English, Estonian, Ukrainian…), many times faster than speech on any processor. Ten ready-made
    voices; each of Jackson's characters speaks with one of them (:data:`PERSONA`), or any of them
    by name (``[voice] voice = "M3"``)."""

    name = "supertonic-3"
    reads_numbers = False       # «семьдесят процентов» comes from jacksond (speech.py), not «70%»
    speeds = True               # synth(…, speed=0.94): calmer in the evening
    rate = 44100
    REPO = "supertone-oss-archive/supertonic-3"     # the archived release, as Supertone left it
    REVISION = "aafc6e32416a594460b32413efc49d7fe4ce6d46"
    # a character → the voice closest to how he was described (tests/voice-samples/lines.json)
    PERSONA = {"kent": "M1", "sysop": "M2", "dispatcher": "M3", "pirate": "M5"}
    DEFAULT = "M1"

    def __init__(self, models: Any, steps: int = 8, speed: float = 1.05) -> None:
        from supertonic import TTS
        self.tts = TTS(model="supertonic-3", model_dir=str(Path(models) / "supertonic-3"), auto_download=False)
        self.rate = int(self.tts.sample_rate)
        self.steps = steps
        self.speed = speed
        self.styles: dict[str, Any] = {}
        try:
            from supertonic.config import SUPPORTED_LANGUAGES
            self.languages = set(SUPPORTED_LANGUAGES)
        except ImportError:
            self.languages = {"ru", "en"}

    def voices(self) -> list[str]:
        return sorted(self.tts.voice_style_names)

    def voice(self, name: str) -> str:
        known = self.voices()
        for candidate in (name, self.PERSONA.get(name, ""), self.DEFAULT):
            if candidate in known:
                return candidate
        return known[0]

    def speakable(self, text: str) -> str:
        """Supertonic refuses a whole sentence for one character it does not know (a «№», an emoji
        left over): such characters become spaces instead."""
        processor = getattr(getattr(self.tts, "model", None), "text_processor", None)
        if processor is not None:
            ok, unknown = processor.validate_text(text)
            if not ok:
                drop = set(unknown)
                text = "".join(" " if c in drop else c for c in text)
        return " ".join(text.split())

    def synth(self, text: str, lang: str, voice: str, speed: float = 1.0) -> Any:
        import numpy as np
        text = self.speakable(text)
        if not any(c.isalnum() for c in text):
            return np.zeros(0, dtype=np.float32)
        name = self.voice(voice)
        if name not in self.styles:
            self.styles[name] = self.tts.get_voice_style(voice_name=name)
        # one chunk (jacksond sends a sentence at a time): the sound is cut where the speech ends,
        # which for several chunks joined with pauses would cut the last one short
        wav, duration = self.tts.synthesize(text, voice_style=self.styles[name], total_steps=self.steps,
                                            speed=min(2.0, max(0.7, self.speed * speed)),
                                            lang=lang if lang in self.languages else "na",
                                            max_chunk_length=max(1000, len(text) + 1))
        samples = np.asarray(wav, dtype=np.float32).reshape(-1)
        return samples[: int(self.rate * float(np.asarray(duration).reshape(-1)[0]))]

    @classmethod
    def fetch(cls, models: Path, fetch_dir: Callable[..., None]) -> None:
        from huggingface_hub import snapshot_download
        fetch_dir(Path(models) / "supertonic-3",
                  lambda d: snapshot_download(cls.REPO, revision=cls.REVISION, local_dir=str(d),
                                              allow_patterns=["onnx/*", "voice_styles/*", "LICENSE*", "README.md"]),
                  "Supertonic 3")
