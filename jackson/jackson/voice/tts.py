# SPDX-License-Identifier: Apache-2.0
"""Text to speech: one sentence in, float32 samples out.

Engines are imported only when used, so that the voice service loads just the one it speaks with.
``reads_numbers`` says whether the engine spells out digits itself; for the others jacksond sends
«семьдесят процентов» instead of «70%» (:mod:`.speech`).
"""

from __future__ import annotations

import math
from typing import Any, Protocol


class TextToSpeech(Protocol):
    name: str
    rate: int
    reads_numbers: bool

    def voices(self) -> list[str]: ...

    def synth(self, text: str, lang: str, voice: str) -> Any:
        """One sentence → float32 mono samples at ``rate``."""
        ...


class ToneTTS:
    """A stand-in that «speaks» a short tone per word: tests, and a check that the speaker works."""

    name = "tone"
    rate = 16000
    reads_numbers = False

    def __init__(self, word_s: float = 0.02, models: Any = None) -> None:
        self.word_s = word_s
        self.said: list[tuple[str, str, str]] = []

    def voices(self) -> list[str]:
        return ["tone"]

    def synth(self, text: str, lang: str, voice: str) -> Any:
        import numpy as np
        self.said.append((text, lang, voice))
        n = int(self.rate * self.word_s * max(1, len(text.split())))
        t = np.arange(n, dtype=np.float32) / self.rate
        return (0.2 * np.sin(2 * math.pi * 440.0 * t)).astype(np.float32)


class SilentTTS:
    """No voice installed: Jackson listens and answers on screen."""

    name = "none"
    rate = 16000
    reads_numbers = True

    def __init__(self, models: Any = None) -> None:
        pass

    def voices(self) -> list[str]:
        return ["none"]

    def synth(self, text: str, lang: str, voice: str) -> Any:
        return []


ENGINES: dict[str, str] = {
    "tone": "jackson.voice.tts:ToneTTS",
    "none": "jackson.voice.tts:SilentTTS",
    "qwen3": "jackson.voice.engines:QwenTTS",
}


def engine_class(name: str) -> Any:
    import importlib
    target = ENGINES.get(name)
    if not target:
        raise ValueError(f"unknown speech engine {name!r} (known: {', '.join(sorted(ENGINES))})")
    module, _, cls = target.partition(":")
    return getattr(importlib.import_module(module), cls)


def load_engine(name: str, **options: Any) -> TextToSpeech:
    return engine_class(name)(**options)


def pick_engine(models: Any) -> str:
    """The best engine installed under *models* for this machine (``sos install voice`` puts one there)."""
    from pathlib import Path
    root = Path(models)
    for name in PREFERENCE:
        marker = ENGINE_DIRS.get(name)
        if marker and (root / marker).exists():
            return name
    return "none"


# engine → the folder under /srv/ai/voice that says it is installed; best first
ENGINE_DIRS: dict[str, str] = {"qwen3": "qwen3-tts"}
PREFERENCE: list[str] = ["qwen3"]
