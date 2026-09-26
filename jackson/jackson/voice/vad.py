# SPDX-License-Identifier: Apache-2.0
"""Where a phrase starts and ends: Silero VAD (MIT) probabilities → :class:`Endpointer` events.

The endpointer is plain logic over one speech probability per 32 ms frame, so it is tested without
a model; :class:`SileroVAD` needs numpy and onnxruntime (the voice module's venv).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RATE = 16000
FRAME = 512                     # samples per frame at 16 kHz (32 ms): what Silero VAD v5+ takes
FRAME_MS = FRAME * 1000 // RATE


@dataclass
class EndpointConfig:
    start_prob: float = 0.5     # a frame this sure is speech
    end_prob: float = 0.35      # below this it is quiet (in between: still the same state)
    start_ms: int = 96          # this much speech in a row starts a phrase (a click does not)
    end_ms: int = 800           # this much quiet ends it (tap, follow)
    preroll_ms: int = 320       # kept from before the start: the first syllable is quiet
    max_ms: int = 30000         # a phrase ends here whatever happens
    wait_ms: int = 8000         # nobody spoke: give up (tap); `follow` waits `follow_ms`
    follow_ms: int = 6000


class Endpointer:
    """Feed one probability per frame; get "start", "end", "timeout" or "max" when they happen.

    Modes: ``tap`` (the phrase ends after a pause), ``hold`` (it ends when the key is released:
    no pause and no timeout end it), ``follow`` (after an answer: like tap with a shorter wait).
    """

    def __init__(self, cfg: EndpointConfig | None = None, mode: str = "tap") -> None:
        self.cfg = cfg or EndpointConfig()
        self.mode = mode
        self.speaking = False
        self.done = False
        self.elapsed_ms = 0
        self.speech_ms = 0          # since the start of the phrase
        self._run_ms = 0            # speech in a row before the start
        self._quiet_ms = 0          # quiet in a row inside the phrase

    @property
    def preroll_frames(self) -> int:
        return max(1, self.cfg.preroll_ms // FRAME_MS)

    def push(self, prob: float) -> str | None:
        if self.done:
            return None
        cfg = self.cfg
        self.elapsed_ms += FRAME_MS
        if not self.speaking:
            self._run_ms = self._run_ms + FRAME_MS if prob >= cfg.start_prob else 0
            if self._run_ms >= cfg.start_ms:
                self.speaking = True
                self.speech_ms = self._run_ms
                return "start"
            wait = cfg.follow_ms if self.mode == "follow" else cfg.wait_ms
            if self.mode != "hold" and self.elapsed_ms >= wait:
                self.done = True
                return "timeout"
            return None
        self.speech_ms += FRAME_MS
        if prob < cfg.end_prob:
            self._quiet_ms += FRAME_MS
        elif prob >= cfg.start_prob:
            self._quiet_ms = 0
        if self.mode != "hold" and self._quiet_ms >= cfg.end_ms:
            self.done = True
            return "end"
        if self.speech_ms >= cfg.max_ms:
            self.done = True
            return "max"
        return None


def level(frame: Any) -> float:
    """0…1 loudness of int16 or float samples for the scope (−60 dBFS → 0, 0 dBFS → 1)."""
    import numpy as np
    x = np.asarray(frame, dtype=np.float32)
    if x.size and np.abs(x).max() > 1.5:        # int16 samples
        x = x / 32768.0
    rms = float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0
    if rms <= 1e-6:
        return 0.0
    db = 20.0 * np.log10(rms)
    return round(float(min(1.0, max(0.0, (db + 60.0) / 60.0))), 3)


class SileroVAD:
    """Silero VAD v5/v6 (ONNX): the probability that a 512-sample frame at 16 kHz is speech."""

    CONTEXT = 64

    def __init__(self, model_path: str, threads: int = 1) -> None:
        import numpy as np
        import onnxruntime as ort
        self._np = np
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = threads
        self.session = ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])
        self.reset()

    def reset(self) -> None:
        np = self._np
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, self.CONTEXT), dtype=np.float32)

    def __call__(self, frame: Any) -> float:
        np = self._np
        x = np.asarray(frame, dtype=np.float32).reshape(1, -1)
        if np.abs(x).max(initial=0.0) > 1.5:     # int16 samples
            x = x / 32768.0
        x = np.concatenate([self.context, x], axis=1)
        out, self.state = self.session.run(None, {"input": x, "state": self.state,
                                                  "sr": np.array(RATE, dtype=np.int64)})
        self.context = x[:, -self.CONTEXT:]
        return float(np.asarray(out).reshape(-1)[0])
