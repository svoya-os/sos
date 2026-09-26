# SPDX-License-Identifier: Apache-2.0
"""Speech to text, on the CPU through onnx-asr (MIT):

* Parakeet TDT 0.6B v3 (NVIDIA, CC-BY-4.0): Russian, English and 23 more European languages, the
  language found by itself — it decides what language was spoken;
* GigaAM v3 (Sber, MIT), end-to-end RNN-T with punctuation: Russian only, and better at it
  (in the first Voice workflow run Parakeet heard nothing in a synthetic Russian phrase).

:class:`BilingualSTT` asks Parakeet first; when it did not hear English, GigaAM has the last word.
A short command takes a fraction of a second on an ordinary laptop.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Protocol

from .vad import RATE

PARAKEET = "nemo-parakeet-tdt-0.6b-v3"
GIGAAM = "gigaam-v3-e2e-rnnt"


class SpeechToText(Protocol):
    name: str

    def recognize(self, samples: Any) -> str:
        """Float32 mono samples at 16 kHz → text."""
        ...


class OnnxAsrSTT:
    def __init__(self, model: str, model_dir: str | Path, name: str, quantization: str | None = "int8") -> None:
        import onnx_asr
        self.name = name
        self.model = onnx_asr.load_model(model, str(model_dir), quantization=quantization)

    def recognize(self, samples: Any) -> str:
        import numpy as np
        audio = np.asarray(samples, dtype=np.float32).reshape(-1)
        result = self.model.recognize(audio, sample_rate=RATE)
        text = result if isinstance(result, str) else str(getattr(result, "text", result))
        return " ".join(text.split())


class ParakeetSTT(OnnxAsrSTT):
    def __init__(self, model_dir: str | Path, quantization: str | None = "int8") -> None:
        super().__init__(PARAKEET, model_dir, "parakeet-tdt-0.6b-v3", quantization)


class GigaAMSTT(OnnxAsrSTT):
    def __init__(self, model_dir: str | Path, quantization: str | None = "int8") -> None:
        super().__init__(GIGAAM, model_dir, "gigaam-v3-e2e-rnnt", quantization)


_LATIN = re.compile(r"[A-Za-z]")
_CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def is_english(text: str) -> bool:
    latin, cyrillic = len(_LATIN.findall(text)), len(_CYRILLIC.findall(text))
    return latin > 0 and latin >= 3 * cyrillic


class BilingualSTT:
    """Parakeet for what is not Russian, GigaAM for Russian."""

    def __init__(self, multilingual: Any, russian: Any = None) -> None:
        self.multilingual = multilingual
        self.russian = russian
        self.name = multilingual.name + (f" + {russian.name}" if russian else "")
        self.last = ""          # which model gave the last text (logs, tests)

    def recognize(self, samples: Any) -> str:
        text = self.multilingual.recognize(samples)
        self.last = self.multilingual.name
        if self.russian is None or is_english(text):
            return text
        russian = self.russian.recognize(samples)
        if russian.strip():
            self.last = self.russian.name
            return russian
        return text
