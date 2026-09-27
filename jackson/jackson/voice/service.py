# SPDX-License-Identifier: Apache-2.0
"""The voice service (``svoya-voice``): listens when asked, speaks what it is given.

Runs with the voice module's venv (numpy, onnxruntime, onnx-asr, the speech engine); the protocol
is in :mod:`jackson.voice`. One phrase is heard at a time and one voice speaks at a time; it never
listens while it speaks (it would hear itself), so a new ``listen`` silences it first.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import VOICE_SOCKET
from .audio import AudioError, Player, Recorder
from .vad import EndpointConfig, Endpointer, level

log = logging.getLogger("jackson.voice")
SOUND_DIRS = ("/usr/share/sounds/svoya/stereo", "/usr/share/svoya/sounds/stereo")


@dataclass
class Capture:
    id: str
    mode: str
    conn: "Conn"
    stop: bool = False
    cancelled: bool = False
    task: asyncio.Task[Any] | None = None


@dataclass
class Line:
    id: str
    text: str
    lang: str
    voice: str
    final: bool
    conn: "Conn"
    audio: Any = None
    speed: float = 1.0


class Conn:
    def __init__(self, writer: asyncio.StreamWriter) -> None:
        self.writer = writer
        self.closed = False

    async def send(self, msg: dict[str, Any]) -> None:
        if self.closed:
            return
        try:
            self.writer.write(json.dumps(msg, ensure_ascii=False).encode() + b"\n")
            await self.writer.drain()
        except (ConnectionError, RuntimeError):
            self.closed = True

    def send_nowait(self, msg: dict[str, Any]) -> None:
        """For levels: in order with everything else, without waiting for the reader."""
        if self.closed:
            return
        try:
            self.writer.write(json.dumps(msg, ensure_ascii=False).encode() + b"\n")
        except (ConnectionError, RuntimeError):
            self.closed = True


class VoiceService:
    def __init__(self, *, load_stt: Callable[[], Any], load_tts: Callable[[], Any], load_vad: Callable[[], Any],
                 recorder: Callable[[], Recorder] = Recorder,
                 player: Callable[[int, Callable[[float], Any]], Player] | None = None,
                 endpoint: EndpointConfig | None = None, sounds: bool = False, warm_up: bool = False) -> None:
        self._load = {"stt": load_stt, "tts": load_tts, "vad": load_vad}
        self.stt: Any = None
        self.tts: Any = None
        self.vad: Any = None
        self.recorder = recorder
        self.player_factory = player or (lambda rate, on_level: Player(rate, on_level=on_level))
        self.endpoint = endpoint or EndpointConfig()
        self.sounds = sounds                # the earcons: the microphone opens, the phrase was heard
        self.warm_up = warm_up              # say one sentence to nobody once loaded (svoya-voice does)
        self.ready = asyncio.Event()
        self.error = ""
        self.capture: Capture | None = None
        self.lines: asyncio.Queue[Line] = asyncio.Queue()
        self.voiced: asyncio.Queue[Line | None] = asyncio.Queue(maxsize=2)
        self.player: Player | None = None
        self.hushed: set[str] = set()
        self.speaking_id = ""
        self.speaking_conn: Conn | None = None
        self.synthesizing: Line | None = None
        self.said_ids: collections.deque[str] = collections.deque(maxlen=64)   # answers played to the end
        self._tasks: list[asyncio.Task[Any]] = []

    # ---- models ---------------------------------------------------------------------------
    async def load(self) -> None:
        t0 = time.monotonic()
        try:
            for part in ("vad", "stt", "tts"):
                setattr(self, part, await asyncio.to_thread(self._load[part]))
        except Exception as exc:  # noqa: BLE001 - reported in status, the service stays up
            self.error = f"{exc.__class__.__name__}: {exc}"[:400]
            log.error("voice models did not load: %s", self.error)
        else:
            log.info("voice ready in %.1f s: %s + %s", time.monotonic() - t0, self.stt.name, self.tts.name)
        self.ready.set()

    async def close(self) -> None:
        """Stop listening and speaking, and the background tasks (SIGTERM)."""
        if self.capture:
            self.capture.cancelled = True
            if self.capture.task:
                await asyncio.gather(self.capture.task, return_exceptions=True)
        player, self.player = self.player, None
        if player:
            await player.hush()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def status(self) -> dict[str, Any]:
        ok = self.ready.is_set() and not self.error
        return {"type": "status", "ready": ok, "loading": not self.ready.is_set(), "error": self.error,
                "stt": getattr(self.stt, "name", ""), "tts": getattr(self.tts, "name", ""),
                "voices": list(self.tts.voices()) if ok else [],
                "readsNumbers": bool(getattr(self.tts, "reads_numbers", False)),
                "rate": int(getattr(self.tts, "rate", 0) or 0) if ok else 0,
                "listening": self.capture is not None, "speaking": bool(self.speaking_id)}

    # ---- the socket -----------------------------------------------------------------------
    async def start(self) -> None:
        self._tasks = [asyncio.create_task(self.load()), asyncio.create_task(self._synthesizer()),
                       asyncio.create_task(self._speaker())]

    async def serve(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() or path.is_symlink():
            path.unlink()
        server = await asyncio.start_unix_server(self.handle, path=str(path))
        os.chmod(path, 0o600)
        await self.start()
        log.info("voice service on %s", path)
        async with server:
            await server.serve_forever()

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        conn = Conn(writer)
        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    break
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(msg, dict):
                    await self.dispatch(conn, msg)
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            conn.closed = True
            if self.capture and self.capture.conn is conn:
                self.capture.cancelled = True
            writer.close()

    async def dispatch(self, conn: Conn, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        tid = str(msg.get("id") or "")
        if kind == "status":
            await conn.send(self.status())
        elif kind == "listen":
            await self.listen(conn, tid, str(msg.get("mode") or "tap"))
        elif kind == "stop" and self.capture and self.capture.id == tid:
            self.capture.stop = True
        elif kind == "cancel" and self.capture and (not tid or self.capture.id == tid):
            self.capture.cancelled = True
        elif kind == "say":
            if tid in self.hushed:
                return
            try:
                speed = min(1.5, max(0.7, float(msg.get("speed") or 1.0)))
            except (TypeError, ValueError):
                speed = 1.0
            self.lines.put_nowait(Line(tid, str(msg.get("text") or ""), str(msg.get("lang") or "ru"),
                                       str(msg.get("voice") or ""), bool(msg.get("final")), conn, speed=speed))
        elif kind == "hush":
            await self.hush(tid, conn)
        elif kind == "ping":
            await conn.send({"type": "pong"})

    # ---- listening ------------------------------------------------------------------------
    async def listen(self, conn: Conn, tid: str, mode: str) -> None:
        if self.capture:                        # a new press replaces the old one
            self.capture.cancelled = True
            if self.capture.task:
                await asyncio.gather(self.capture.task, return_exceptions=True)
        await self.hush()                       # never listen to ourselves
        if not self.ready.is_set():
            await conn.send({"type": "loading", "id": tid})
        await self.ready.wait()
        if self.error:
            await conn.send({"type": "error", "id": tid, "message": self.error})
            return
        cap = Capture(tid, mode if mode in ("tap", "hold", "follow") else "tap", conn)
        self.capture = cap
        cap.task = asyncio.create_task(self._capture(cap))

    async def _capture(self, cap: Capture) -> None:
        import numpy as np
        ep = Endpointer(self.endpoint, cap.mode)
        if hasattr(self.vad, "reset"):
            self.vad.reset()
        pre: collections.deque[Any] = collections.deque(maxlen=ep.preroll_frames)
        heard: list[Any] = []
        frames = 0
        peak = 0.0
        rec = self.recorder()
        outcome = "nothing"
        log.info("listening (%s)", cap.mode)
        await self.earcon("jackson-listen")       # before the microphone opens: it must not hear it
        try:
            await rec.start()
            async for data in rec.frames():
                if cap.cancelled:
                    return
                frame = np.frombuffer(data, dtype=np.int16)
                frames += 1
                if frames % 2 == 0:
                    cap.conn.send_nowait({"type": "level", "id": cap.id, "source": "mic", "level": level(frame)})
                prob = float(self.vad(frame))
                peak = max(peak, prob)
                event = ep.push(prob)
                if event == "start":
                    heard.extend(pre)
                    await cap.conn.send({"type": "speech", "id": cap.id, "state": "start"})
                if ep.speaking or cap.mode == "hold":
                    heard.append(frame)
                else:
                    pre.append(frame)
                if event in ("end", "max"):
                    await cap.conn.send({"type": "speech", "id": cap.id, "state": "end"})
                    outcome = "heard"
                    break
                if event == "timeout":
                    break
                if cap.stop:
                    break
            if outcome != "heard" and (cap.stop or cap.mode == "hold"):
                # released (or the recording ended): whatever was said until now
                outcome = "heard" if (ep.speaking or peak >= self.endpoint.start_prob) else "nothing"
        except AudioError as exc:
            await cap.conn.send({"type": "error", "id": cap.id, "message": str(exc)})
            return
        finally:
            said = await rec.close()
            if self.capture is cap:
                self.capture = None
            cap.conn.send_nowait({"type": "level", "id": cap.id, "source": "mic", "level": 0.0})
        if cap.cancelled:
            return
        if frames == 0:
            await cap.conn.send({"type": "error", "id": cap.id,
                                 "message": "no microphone" + (f": {said}" if said else "")})
            return
        if outcome != "heard" or not heard:
            await cap.conn.send({"type": "nothing", "id": cap.id})
            return
        audio = np.concatenate(heard).astype(np.float32) / 32768.0
        asyncio.get_running_loop().create_task(self.earcon("jackson-thinking"))
        t0 = time.monotonic()
        try:
            text = await asyncio.to_thread(self.stt.recognize, audio)
        except Exception as exc:  # noqa: BLE001
            await cap.conn.send({"type": "error", "id": cap.id, "message": f"recognition failed: {exc}"})
            return
        ms = int((time.monotonic() - t0) * 1000)
        describe = getattr(self.stt, "describe", None)
        detail = describe() if describe else getattr(self.stt, "last", "")
        log.info("heard %.1f s of speech, recognized in %d ms%s", len(audio) / 16000, ms,
                 f" ({detail})" if detail else "")
        if not text.strip():
            await cap.conn.send({"type": "nothing", "id": cap.id})
            return
        msg: dict[str, Any] = {"type": "transcript", "id": cap.id, "text": text.strip(), "ms": ms}
        if getattr(self.stt, "last", ""):
            msg["model"] = self.stt.last
        sure = self.stt.sureness() if hasattr(self.stt, "sureness") else None
        if sure is not None:
            msg["sure"] = round(sure, 3)
        await cap.conn.send(msg)

    async def earcon(self, name: str) -> None:
        """A short sound from the SOS sound theme (branding/sounds), played to its end."""
        if not self.sounds:
            return
        for base in SOUND_DIRS:
            path = Path(base) / f"{name}.oga"
            if path.is_file():
                break
        else:
            return
        try:
            proc = await asyncio.create_subprocess_exec("pw-play", str(path), stdin=asyncio.subprocess.DEVNULL,
                                                        stdout=asyncio.subprocess.DEVNULL,
                                                        stderr=asyncio.subprocess.DEVNULL)
            await asyncio.wait_for(proc.wait(), 2)
        except (OSError, asyncio.TimeoutError):
            pass

    # ---- speaking -------------------------------------------------------------------------
    def _synth(self, line: Line) -> Any:
        if line.speed != 1.0 and getattr(self.tts, "speeds", False):
            return self.tts.synth(line.text, line.lang, line.voice, speed=line.speed)
        return self.tts.synth(line.text, line.lang, line.voice)

    def _warm_up(self) -> None:
        """The first sentence an engine says takes it much longer (ONNX Runtime sets itself up):
        one short sentence nobody hears, before anyone asks (Voice workflow: the first sound came
        3 s after the answer on a CI runner)."""
        t0 = time.monotonic()
        try:
            voices = list(self.tts.voices())
            self.tts.synth("Проверка связи.", "ru", voices[0] if voices else "")
        except Exception as exc:  # noqa: BLE001 - only a warm-up
            log.info("voice warm-up failed: %s", exc)
            return
        log.info("voice warmed up in %.1f s", time.monotonic() - t0)

    async def _synthesizer(self) -> None:
        """Sentences → audio, one ahead of what is playing."""
        await self.ready.wait()
        if self.warm_up and self.tts is not None and not self.error:
            await asyncio.to_thread(self._warm_up)
        while True:
            line = await self.lines.get()
            if line.id in self.hushed:
                continue
            if line.text.strip() and self.tts is not None:
                self.synthesizing = line
                try:
                    line.audio = await asyncio.to_thread(self._synth, line)
                except Exception as exc:  # noqa: BLE001 - one bad sentence is skipped
                    log.warning("could not say %r: %s", line.text[:60], exc)
                    line.audio = None
                finally:
                    self.synthesizing = None
            if line.id in self.hushed:
                continue
            await self.voiced.put(line)

    async def _speaker(self) -> None:
        while True:
            line = await self.voiced.get()
            if line is None or line.id in self.hushed:
                continue
            self.speaking_id = line.id
            self.speaking_conn = conn = line.conn

            def on_level(value: float, conn: Conn = conn, tid: str = line.id) -> None:
                conn.send_nowait({"type": "level", "id": tid, "source": "voice", "level": value})

            try:
                if line.audio is not None and len(line.audio):
                    if self.player is None:
                        self.player = self.player_factory(self.tts.rate, on_level)
                    await self.player.play(line.audio)
                if line.id in self.hushed:           # silenced while it played: hush() has told
                    continue
                if line.final:
                    player, self.player = self.player, None
                    if player:
                        await player.finish()
                    self.speaking_id = ""
                    self.speaking_conn = None
                    self.said_ids.append(line.id)
                    await conn.send({"type": "spoken", "id": line.id, "hushed": False})
            except AudioError as exc:
                self.player = None
                self.speaking_id = ""
                self.speaking_conn = None
                await conn.send({"type": "error", "id": line.id, "message": str(exc)})

    async def hush(self, tid: str = "", conn: Conn | None = None) -> None:
        """Silence now: drop what is queued, stop what is playing (with *tid*: that answer only,
        including what jacksond has not sent yet). Each silenced answer gets ``spoken {hushed: true}``."""
        told: dict[str, Conn] = {}
        if self.speaking_id and self.speaking_conn and (not tid or self.speaking_id == tid):
            told[self.speaking_id] = self.speaking_conn
        if self.synthesizing and (not tid or self.synthesizing.id == tid):
            told.setdefault(self.synthesizing.id, self.synthesizing.conn)
        for q in (self.lines, self.voiced):
            keep = []
            while not q.empty():
                item = q.get_nowait()
                if item is None:
                    continue
                if tid and item.id != tid:
                    keep.append(item)
                else:
                    told.setdefault(item.id, item.conn)
            for item in keep:
                q.put_nowait(item)
        if tid and tid not in told and tid not in self.hushed and tid not in self.said_ids and conn is not None:
            told[tid] = conn                     # not started yet: whatever comes for it is dropped
        if not tid or self.speaking_id in told:
            player, self.player = self.player, None
            if player:
                await player.hush()
            self.speaking_id = ""
            self.speaking_conn = None
        self.hushed |= set(told)
        if len(self.hushed) > 64:
            self.hushed = set(list(self.hushed)[-32:])
        for hushed_id, who in told.items():
            await who.send({"type": "spoken", "id": hushed_id, "hushed": True})


# ---------------------------------------------------------------------------------------------
# the process

def socket_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(runtime) / "svoya" / VOICE_SOCKET


def default_loaders(models: Path, engine: str, engine_options: dict[str, Any]) -> dict[str, Callable[[], Any]]:
    from .stt import BilingualSTT, GigaAMSTT, ParakeetSTT
    from .tts import load_engine
    from .vad import SileroVAD

    def stt() -> Any:
        russian = models / "gigaam-v3-e2e-rnnt"
        return BilingualSTT(ParakeetSTT(models / "parakeet-tdt-0.6b-v3"),
                            GigaAMSTT(russian) if russian.is_dir() else None)

    return {
        "load_vad": lambda: SileroVAD(str(models / "silero-vad" / "silero_vad.onnx")),
        "load_stt": stt,
        "load_tts": lambda: load_engine(engine, models=models, **engine_options),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="svoya-voice", description="Jackson's ears and voice (local).")
    ap.add_argument("--models", default=os.environ.get("SVOYA_VOICE_MODELS", "/srv/ai/voice"))
    ap.add_argument("--engine", default=os.environ.get("SVOYA_VOICE_ENGINE", ""))
    ap.add_argument("--socket", default="")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from ..config import load_config
    from ..paths import Paths
    cfg = load_config(Paths.from_env()).voice
    engine = args.engine or str(cfg.get("engine") or "auto")
    models = Path(args.models)
    if engine == "auto":
        from .tts import pick_engine
        engine = pick_engine(models)
    options = dict(cfg.get("engine_options") or {})
    service = VoiceService(**default_loaders(models, engine, options), sounds=cfg.get("sounds", True) is not False,
                           warm_up=True)
    path = Path(args.socket) if args.socket else socket_path()

    async def run() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        serving = asyncio.create_task(service.serve(path))
        await asyncio.wait([serving, asyncio.create_task(stop.wait())], return_when=asyncio.FIRST_COMPLETED)
        await service.close()
        serving.cancel()
        await asyncio.gather(serving, return_exceptions=True)
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    asyncio.run(run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
