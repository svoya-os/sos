# SPDX-License-Identifier: Apache-2.0
"""Speech to text, on the CPU through onnx-asr (MIT):

* Parakeet TDT 0.6B v3 (NVIDIA, CC-BY-4.0): Russian, English and 23 more European languages, the
  language found by itself — it decides what language was spoken;
* GigaAM v3 (Sber, MIT), end-to-end RNN-T with punctuation: Russian only, and better at it
  (in the first Voice workflow run Parakeet heard nothing in a synthetic Russian phrase).

:class:`BilingualSTT` asks Parakeet first. When Parakeet surely heard English, that is the answer;
otherwise GigaAM hears the phrase too. For Russian GigaAM has the last word. For English that
Parakeet was unsure of, the surer model wins: robotic Russian «открой браузер» once came out of
Parakeet as "But Carolina." How sure a model is: the geometric mean of the probabilities of the
tokens it chose (onnx-asr gives their log-probabilities).
A short command takes a fraction of a second on an ordinary laptop.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .vad import RATE

PARAKEET = "nemo-parakeet-tdt-0.6b-v3"
GIGAAM = "gigaam-v3-e2e-rnnt"

SURE = 0.85             # Parakeet's English at least this sure is taken without asking GigaAM


@dataclass
class Heard:
    text: str
    sure: float | None = None       # 0…1, None when the model does not say
    model: str = ""


class SpeechToText(Protocol):
    name: str

    def recognize(self, samples: Any) -> str:
        """Float32 mono samples at 16 kHz → text."""
        ...


def sureness(logprobs: Any) -> float | None:
    values = [float(x) for x in (logprobs or [])]
    if not values:
        return None
    return math.exp(sum(values) / len(values))


class OnnxAsrSTT:
    def __init__(self, model: str, model_dir: str | Path, name: str, quantization: str | None = "int8") -> None:
        import onnx_asr
        self.name = name
        self.model = onnx_asr.load_model(model, str(model_dir), quantization=quantization)
        with_timestamps = getattr(self.model, "with_timestamps", None)
        self.timed = with_timestamps() if with_timestamps else None

    def hear(self, samples: Any) -> Heard:
        import numpy as np
        audio = np.asarray(samples, dtype=np.float32).reshape(-1)
        result = (self.timed or self.model).recognize(audio, sample_rate=RATE)
        text = result if isinstance(result, str) else str(getattr(result, "text", result))
        return Heard(" ".join(text.split()), sureness(getattr(result, "logprobs", None)), self.name)

    def recognize(self, samples: Any) -> str:
        return self.hear(samples).text


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


def hear(model: Any, samples: Any) -> Heard:
    if hasattr(model, "hear"):
        return model.hear(samples)
    return Heard(model.recognize(samples), None, getattr(model, "name", ""))


class BilingualSTT:
    """Parakeet for what is not Russian, GigaAM for Russian."""

    def __init__(self, multilingual: Any, russian: Any = None, sure: float = SURE) -> None:
        self.multilingual = multilingual
        self.russian = russian
        self.sure = sure
        self.name = multilingual.name + (f" + {russian.name}" if russian else "")
        self.last = ""          # which model gave the last text (logs, tests)
        self.heard: list[Heard] = []    # what each model heard last time

    def recognize(self, samples: Any) -> str:
        first = hear(self.multilingual, samples)
        self.heard = [first]
        chosen = first
        english = is_english(first.text)
        if self.russian is not None and not (english and (first.sure is None or first.sure >= self.sure)):
            second = hear(self.russian, samples)
            self.heard.append(second)
            if second.text.strip() and not (english and (second.sure or 0.0) <= (first.sure or 0.0)):
                chosen = second
        self.last = chosen.model or (self.russian.name if chosen is not first else self.multilingual.name)
        return chosen.text

    def describe(self) -> str:
        """For the system log: which model gave the text and how sure each one was — never the words."""
        sure = ", ".join(f"{h.model} {h.sure:.2f}" for h in self.heard if h.sure is not None)
        return self.last + (f"; sure: {sure}" if sure else "")

    def sureness(self) -> float | None:
        """How sure the model that gave the last text was."""
        return next((h.sure for h in self.heard if h.model == self.last), None)
