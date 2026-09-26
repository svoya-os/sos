# SPDX-License-Identifier: Apache-2.0
"""Voice (v0.2 «Голос»): talk to Jackson and hear him answer.

Two processes, so that jacksond stays on the standard library:

* the **voice service** (``svoya-voice``, :mod:`.service`) runs in the voice module's venv
  (``/opt/svoya/venvs/voice``, ``sos install voice``): it records the microphone through PipeWire
  (``pw-record``), finds the end of a phrase with Silero VAD (MIT), turns it into text with
  Parakeet TDT 0.6B v3 (CC-BY-4.0, Russian and English) through onnx-asr, and speaks sentences with
  a local text-to-speech engine (:mod:`.tts`) through ``pw-play``. Nothing leaves the computer and
  no audio is kept.
* **jacksond** (:mod:`.client`, :mod:`.speech`) asks it to listen when a client sends ``listen``,
  runs the transcript as a turn, and hands the answer over sentence by sentence while it streams.

Voice service socket ``$XDG_RUNTIME_DIR/svoya/voice.sock``, JSON Lines, one object per line:

    → {"type": "listen", "id": "t1", "mode": "tap"|"hold"|"follow", "lang": "ru"}
    → {"type": "stop", "id": "t1"}            the key is released: transcribe what was heard
    → {"type": "cancel", "id": "t1"}          drop the recording
    → {"type": "say", "id": "t1", "text": "…", "lang": "ru", "voice": "kent", "final": false}
    → {"type": "hush"}                        stop speaking now
    → {"type": "status"}
    ← {"type": "level", "id": "t1", "source": "mic"|"voice", "level": 0.42}
    ← {"type": "speech", "id": "t1", "state": "start"|"end"}
    ← {"type": "transcript", "id": "t1", "text": "…", "ms": 310}
    ← {"type": "nothing", "id": "t1"}         no speech before the timeout (or only noise)
    ← {"type": "spoken", "id": "t1", "hushed": false}   everything said for t1 has been played
    ← {"type": "status", "ready": true, "stt": "…", "tts": "…", "voices": […], "error": "…"}
    ← {"type": "error", "id": "t1", "message": "…"}

``tap`` ends the phrase after a pause, ``hold`` when the key is released (``stop``), ``follow`` is the
listening after an answer (conversation mode): it gives up quietly when nobody speaks.
"""

from __future__ import annotations

VOICE_SOCKET = "voice.sock"     # in $XDG_RUNTIME_DIR/svoya
