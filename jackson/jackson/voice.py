# SPDX-License-Identifier: Apache-2.0
"""Voice (v0.2 «Голос») — interface only, nothing here runs in v0.1.

Plan: push-to-talk on Super+J (hold). All speech stays on the machine and runs on the CPU by
default, as separate Wyoming-protocol services (TCP JSON header + binary payload events):

    wyoming-vad   Silero VAD (MIT)                                 audio-chunk → voice-started/stopped
    wyoming-stt   Parakeet-TDT-0.6B-v3 (CC-BY-4.0, RU/EN/ET) or    audio-start/chunk/stop → transcript
                  GigaAM-v3 (MIT, RU) via onnx-asr
    wyoming-tts   Silero v5_cis_base (MIT) or Piper (GPL-3.0,      synthesize → audio-start/chunk/stop
                  voices dmitri/denis); Qwen3-TTS (Apache-2.0) on GPU
    wyoming-wake  livekit-wakeword (Apache-2.0) trained for «Джексон»/"Jackson" (opt-in, off by default)

Socket protocol additions (all additive, see README "Contract notes"):

    client → service  {"type": "listen", "id": "t-…", "mode": "ptt"}      start capturing
                      {"type": "listen-stop", "id": "t-…"}                 key released
    service → client  {"type": "state", "state": "listening", "level": 0.42}   live mic level for the scope
                      {"type": "transcript", "id": "t-…", "text": "…", "final": true}
                      then the normal turn events; while TTS plays: state "speaking" with "level"

The interfaces below are what the v0.2 implementation will satisfy; they exist so other
components (shell, tests) can code against them now.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol


@dataclass
class Transcript:
    text: str
    lang: str
    final: bool
    confidence: float | None = None


@dataclass
class AudioChunk:
    pcm: bytes          # 16-bit little-endian mono
    rate: int = 16000


class SpeechToText(Protocol):
    async def transcribe(self, audio: AsyncIterator[AudioChunk], lang_hint: str | None = None
                         ) -> AsyncIterator[Transcript]: ...


class TextToSpeech(Protocol):
    async def speak(self, text: str, voice: str, lang: str) -> AsyncIterator[AudioChunk]: ...


class VoiceActivity(Protocol):
    def is_speech(self, chunk: AudioChunk) -> bool: ...


WYOMING_DEFAULTS = {
    "stt": "tcp://127.0.0.1:10300",
    "tts": "tcp://127.0.0.1:10200",
    "vad": "tcp://127.0.0.1:10500",
    "wake": "tcp://127.0.0.1:10400",
}
