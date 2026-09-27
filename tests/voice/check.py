#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The voice service end to end, with real models and a file for a microphone.

    check.py --models DIR [--engine NAME] --phrase ru:FILE.raw:expected,words [--phrase ?ru:…]
             [--say "ru:Text to say:expected,words"] [--wav-dir DIR]

Starts `svoya-voice` on a private socket with the phrase as its microphone (tests/voice/mic.py),
asks it to listen, and checks that the transcript has the expected words. Then, for each --say, has
it speak with the engine into a file instead of a speaker, and hears that back with the recognizers
Jackson listens with: the voice must be understood. Prints a Markdown report. A spec that starts
with `?` is reported but does not fail the check (robotic speech).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


async def talk(sock: Path, messages: list[dict], until: set[str], timeout: float) -> list[dict]:
    reader, writer = await asyncio.open_unix_connection(str(sock))
    for m in messages:
        writer.write(json.dumps(m, ensure_ascii=False).encode() + b"\n")
    await writer.drain()
    got: list[dict] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            raw = await asyncio.wait_for(reader.readline(), deadline - time.monotonic())
        except asyncio.TimeoutError:
            break
        if not raw:
            break
        msg = json.loads(raw)
        msg["_t"] = time.monotonic()
        got.append(msg)
        if msg.get("type") in until:
            break
    writer.close()
    return got


async def wait_ready(sock: Path, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if sock.exists():
            got = await talk(sock, [{"type": "status"}], {"status"}, 5)
            if got and (got[-1].get("ready") or got[-1].get("error")):
                return got[-1]
        await asyncio.sleep(1)
    return {"ready": False, "error": "no status in time"}


class Service:
    """svoya-voice in a private folder: a file for a microphone, a file for a speaker."""

    def __init__(self, args: argparse.Namespace, mic: str = "") -> None:
        self.args = args
        self.mic = mic
        self.tmp = tempfile.TemporaryDirectory()
        self.sock = Path(self.tmp.name) / "voice.sock"
        self.speaker = Path(self.tmp.name) / "speaker.f32"     # what was played, float32 at the voice's rate
        self.proc: asyncio.subprocess.Process | None = None
        self.status: dict = {}
        self.load_s = 0.0

    async def __aenter__(self) -> "Service":
        path = os.pathsep.join(p for p in (str(ROOT / "jackson"), os.environ.get("PYTHONPATH", "")) if p)
        env = dict(os.environ, SVOYA_VOICE_PLAY=f"sh -c cat>>{self.speaker}", PYTHONPATH=path)
        if self.mic:
            env["SVOYA_VOICE_RECORD"] = f"{sys.executable} {HERE / 'mic.py'} {self.mic}"
        self.proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "jackson.voice.service", "--socket", str(self.sock), "--models", self.args.models,
            "--engine", self.args.engine, env=env)
        t0 = time.monotonic()
        self.status = await wait_ready(self.sock, 300)
        self.load_s = time.monotonic() - t0
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self.proc:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), 10)
            except asyncio.TimeoutError:
                self.proc.kill()
        self.tmp.cleanup()


def has_words(text: str, expected: list[str]) -> bool:
    low = text.lower().replace("ё", "е")
    return all(w.lower().replace("ё", "е") in low for w in expected)


async def run_phrase(args: argparse.Namespace, lang: str, raw: str, expected: list[str]) -> tuple[bool, str]:
    async with Service(args, raw) as svc:
        if not svc.status.get("ready"):
            return False, f"| {lang} | not ready: {svc.status.get('error')} | NO | |"
        t0 = time.monotonic()
        got = await talk(svc.sock, [{"type": "listen", "id": "c1", "mode": "tap"}], {"transcript", "nothing", "error"}, 60)
        took = time.monotonic() - t0
        last = got[-1] if got else {"type": "timeout"}
        text = last.get("text", "") if last.get("type") == "transcript" else f"({last.get('type')}: {last.get('message', '')})"
        ok = last.get("type") == "transcript" and has_words(text, expected)
        by = f" by {last['model']}" if last.get("model") else ""
        by += f" (sure {last['sure']:.2f})" if isinstance(last.get("sure"), (int, float)) else ""
        return ok, (f"| {lang} | {text} | {'yes' if ok else 'NO'} | recognized in {last.get('ms', '—')} ms{by}, "
                    f"phrase ended {took:.1f} s after the start; models loaded in {svc.load_s:.1f} s |")


def hear_back(args: argparse.Namespace, samples, rate: int) -> str:
    """What Jackson's own ears make of what his voice said."""
    import numpy as np
    sys.path.insert(0, str(ROOT / "jackson"))
    from jackson.voice.stt import BilingualSTT, GigaAMSTT, ParakeetSTT
    models = Path(args.models)
    if rate != 16000 and len(samples):
        n = int(len(samples) * 16000 / rate)
        samples = np.interp(np.arange(n) * (rate / 16000), np.arange(len(samples)), samples).astype(np.float32)
    global _STT
    if _STT is None:
        russian = models / "gigaam-v3-e2e-rnnt"
        _STT = BilingualSTT(ParakeetSTT(models / "parakeet-tdt-0.6b-v3"),
                            GigaAMSTT(russian) if russian.is_dir() else None)
    return _STT.recognize(samples)


_STT = None


async def run_say(args: argparse.Namespace, label: str, lang: str, text: str,
                  expected: list[str]) -> tuple[bool, str]:
    import numpy as np
    async with Service(args) as svc:
        if not svc.status.get("ready"):
            return False, f"| {label} | {text} | not ready: {svc.status.get('error')} | NO | |"
        voice = args.voice
        t0 = time.monotonic()
        got = await talk(svc.sock, [{"type": "say", "id": "s1", "text": text, "lang": lang, "voice": voice},
                                    {"type": "say", "id": "s1", "text": "", "final": True}], {"spoken", "error"}, 120)
        last = got[-1] if got else {"type": "timeout"}
        first = next((m["_t"] for m in got if m.get("type") == "level" and m.get("source") == "voice"), None)
        await asyncio.sleep(0.3)        # the player's last bytes
        rate = int(svc.status.get("rate") or 16000)
        samples = np.fromfile(svc.speaker, dtype=np.float32) if svc.speaker.exists() else np.zeros(0, np.float32)
        seconds = len(samples) / rate
        if args.wav_dir and len(samples):
            import wave
            Path(args.wav_dir).mkdir(parents=True, exist_ok=True)
            with wave.open(str(Path(args.wav_dir) / f"{lang}-{len(os.listdir(args.wav_dir)) + 1}.wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    if last.get("type") != "spoken" or not len(samples):
        return False, f"| {label} | {text} | ({last.get('type')}: {last.get('message', '')}) | NO | |"
    heard = hear_back(args, samples, rate)
    ok = has_words(heard, expected)
    start = f"first sound after {first - t0:.2f} s, " if first else ""
    return ok, (f"| {label} | {text} | {heard} | {'yes' if ok else 'NO'} | {svc.status.get('tts')} ({voice}): "
                f"{start}{seconds:.1f} s of speech at {rate} Hz |")


async def main_async(args: argparse.Namespace) -> int:
    ok_all = True
    rows = []
    for spec in args.phrase:
        optional = spec.startswith("?")
        lang, raw, words = spec.lstrip("?").split(":", 2)
        if not Path(raw).exists():
            rows.append(f"| {lang} | (no phrase {raw}) | {'—' if optional else 'NO'} | |")
            ok_all = ok_all and optional
            continue
        ok, row = await run_phrase(args, lang + (" (optional)" if optional else ""), raw,
                                   [w for w in words.split(",") if w])
        rows.append(row)
        ok_all = ok_all and (ok or optional)
    if rows:
        print("### Jackson hears\n\n| lang | heard | ok | details |\n|---|---|---|---|")
        print("\n".join(rows))
    rows = []
    for spec in args.say:
        optional = spec.startswith("?")
        lang, rest = spec.lstrip("?").split(":", 1)
        text, words = rest.rsplit(":", 1)       # the text may have a colon of its own
        ok, row = await run_say(args, lang + (" (optional)" if optional else ""), lang, text,
                                [w for w in words.split(",") if w])
        rows.append(row)
        ok_all = ok_all and (ok or optional)
    if rows:
        print("\n### Jackson speaks (and hears himself back)\n\n| lang | said | heard back | ok | details |\n"
              "|---|---|---|---|---|")
        print("\n".join(rows))
    return 0 if ok_all else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--engine", default="none")
    ap.add_argument("--voice", default="kent", help="the voice for --say: a character or the engine's own name")
    ap.add_argument("--phrase", action="append", default=[])
    ap.add_argument("--say", action="append", default=[])
    ap.add_argument("--wav-dir", default="", help="keep what Jackson said here as WAV")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
