# SPDX-License-Identifier: Apache-2.0
"""Microphone and speaker through PipeWire's own tools (``pw-record``/``pw-play``, raw PCM on a pipe).

No audio library in the venv and nothing in the audio path but PipeWire: the default source and
sink the user picked in the shell are what Jackson hears and speaks through. ALSA's
``arecord``/``aplay`` (pipewire-alsa routes them to PipeWire too) stand in when pw-cat lacks raw mode.
The microphone is open only between ``Recorder.start()`` and ``close()``.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from typing import Any, AsyncIterator, Callable

from .vad import FRAME, RATE


def _pw_raw() -> bool:
    """pw-cat has had --raw for years; check anyway: without it it would write a WAV header."""
    exe = shutil.which("pw-cat")
    if not exe:
        return False
    try:
        out = subprocess.run([exe, "--help"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return "--raw" in (out.stdout + out.stderr)


_RAW: bool | None = None


def record_command(rate: int = RATE) -> list[str]:
    global _RAW
    if os.environ.get("SVOYA_VOICE_RECORD"):          # tests and the VM bot: a file as the microphone
        return os.environ["SVOYA_VOICE_RECORD"].split()
    if _RAW is None:
        _RAW = _pw_raw()
    if _RAW:
        return ["pw-record", "--raw", "--rate", str(rate), "--channels", "1", "--format", "s16",
                "--latency", "32ms", "-"]
    return ["arecord", "-q", "-t", "raw", "-f", "S16_LE", "-r", str(rate), "-c", "1", "-"]


def play_command(rate: int) -> list[str]:
    global _RAW
    if os.environ.get("SVOYA_VOICE_PLAY"):
        return os.environ["SVOYA_VOICE_PLAY"].split()
    if _RAW is None:
        _RAW = _pw_raw()
    if _RAW:
        return ["pw-play", "--raw", "--rate", str(rate), "--channels", "1", "--format", "f32",
                "--latency", "60ms", "-"]
    return ["aplay", "-q", "-t", "raw", "-f", "FLOAT_LE", "-r", str(rate), "-c", "1", "-"]


class AudioError(Exception):
    pass


class Recorder:
    """16 kHz mono int16 frames of 512 samples from the default microphone."""

    def __init__(self, command: list[str] | None = None) -> None:
        self.command = command or record_command()
        self.proc: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        try:
            self.proc = await asyncio.create_subprocess_exec(
                *self.command, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)
        except OSError as exc:
            raise AudioError(f"cannot start {self.command[0]}: {exc}") from exc

    async def frames(self) -> AsyncIterator[bytes]:
        assert self.proc and self.proc.stdout
        size = FRAME * 2
        while True:
            try:
                data = await self.proc.stdout.readexactly(size)
            except asyncio.IncompleteReadError as exc:
                if exc.partial:
                    yield exc.partial + b"\0" * (size - len(exc.partial))
                return
            yield data

    async def close(self) -> str:
        """Stop recording; returns what the recorder said on stderr (for a missing microphone)."""
        proc, self.proc = self.proc, None
        if not proc:
            return ""
        if proc.returncode is None:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
        err = b""
        try:
            _, err = await asyncio.wait_for(proc.communicate(), 2)
        except (asyncio.TimeoutError, ValueError):
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        return (err or b"").decode(errors="replace").strip()[-300:]


class Player:
    """Mono float32 samples to the default speaker, paced in real time so that the scope's level
    matches what is heard and ``hush()`` silences it within a fraction of a second."""

    CHUNK_S = 0.04
    LEAD_S = 0.15

    def __init__(self, rate: int, command: list[str] | None = None,
                 on_level: Callable[[float], Any] | None = None) -> None:
        self.rate = rate
        self.command = command or play_command(rate)
        self.on_level = on_level
        self.proc: asyncio.subprocess.Process | None = None
        self.hushed = False
        self._t0 = 0.0
        self._played = 0.0     # seconds written so far

    async def _open(self) -> None:
        try:
            self.proc = await asyncio.create_subprocess_exec(
                *self.command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL)
        except OSError as exc:
            raise AudioError(f"cannot start {self.command[0]}: {exc}") from exc
        self._t0 = time.monotonic()
        self._played = 0.0

    async def play(self, samples: Any) -> bool:
        """Play; False when hushed meanwhile."""
        import numpy as np
        from .vad import level
        if self.hushed:
            return False
        if self.proc is None:
            await self._open()
        assert self.proc and self.proc.stdin
        data = np.asarray(samples, dtype=np.float32).reshape(-1)
        step = max(1, int(self.rate * self.CHUNK_S))
        for i in range(0, len(data), step):
            if self.hushed:
                return False
            chunk = data[i:i + step]
            ahead = self._t0 + self._played - time.monotonic()
            if ahead > self.LEAD_S:
                await asyncio.sleep(ahead - self.LEAD_S)
            elif ahead < 0:                    # fell behind (a slow sentence): start the clock again
                self._t0 = time.monotonic() - self._played
            try:
                self.proc.stdin.write(chunk.tobytes())
                await self.proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError) as exc:
                raise AudioError("the speaker went away") from exc
            self._played += len(chunk) / self.rate
            if self.on_level:
                self.on_level(level(chunk))
        return not self.hushed

    async def finish(self) -> None:
        """Let the last samples play out, then close."""
        proc, self.proc = self.proc, None
        if not proc:
            return
        rest = self._t0 + self._played - time.monotonic()
        if rest > 0 and not self.hushed:
            await asyncio.sleep(rest)
        if proc.stdin:
            try:
                proc.stdin.close()
            except (BrokenPipeError, ConnectionResetError):
                pass
        try:
            await asyncio.wait_for(proc.wait(), 2)
        except asyncio.TimeoutError:
            proc.kill()
        if self.on_level:
            self.on_level(0.0)

    async def hush(self) -> None:
        self.hushed = True
        proc, self.proc = self.proc, None
        if proc and proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
        if self.on_level:
            self.on_level(0.0)
