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
