# SPDX-License-Identifier: Apache-2.0
"""Speech to text: Parakeet TDT 0.6B v3 (NVIDIA, CC-BY-4.0; Russian, English and 23 more European
languages, language found by itself) through onnx-asr (MIT) on the CPU. A short command takes a
fraction of a second on an ordinary laptop."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .vad import RATE

PARAKEET = "nemo-parakeet-tdt-0.6b-v3"


class SpeechToText(Protocol):
    name: str

    def recognize(self, samples: Any) -> str:
        """Float32 mono samples at 16 kHz → text."""
        ...


class ParakeetSTT:
    name = "parakeet-tdt-0.6b-v3"

    def __init__(self, model_dir: str | Path, quantization: str | None = "int8") -> None:
        import onnx_asr
        self.model = onnx_asr.load_model(PARAKEET, str(model_dir), quantization=quantization)

    def recognize(self, samples: Any) -> str:
        import numpy as np
        audio = np.asarray(samples, dtype=np.float32).reshape(-1)
        result = self.model.recognize(audio, sample_rate=RATE)
        text = result if isinstance(result, str) else str(getattr(result, "text", result))
        return " ".join(text.split())
