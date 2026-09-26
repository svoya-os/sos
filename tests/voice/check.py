#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The voice service end to end, with real models and a file for a microphone.

    check.py --models DIR --phrase ru:FILE.raw:expected,words [--phrase …] [--engine none]

Starts `svoya-voice` on a private socket with the phrase as its microphone (tests/voice/mic.py)
and the speaker going nowhere, asks it to listen, and checks that the transcript has the expected
words; then has it say two sentences and waits until they are spoken. Prints a Markdown report.
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


async def run_phrase(args: argparse.Namespace, lang: str, raw: str, expected: list[str]) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        sock = Path(tmp) / "voice.sock"
        env = dict(os.environ, SVOYA_VOICE_RECORD=f"{sys.executable} {HERE / 'mic.py'} {raw}",
                   SVOYA_VOICE_PLAY="sh -c cat>/dev/null", PYTHONPATH=str(ROOT / "jackson"))
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "jackson.voice.service", "--socket", str(sock), "--models", args.models,
            "--engine", args.engine, env=env)
        try:
            t0 = time.monotonic()
            status = await wait_ready(sock, 300)
            load_s = time.monotonic() - t0
            if not status.get("ready"):
                return False, f"| {lang} | not ready: {status.get('error')} | | |"
            t0 = time.monotonic()
            got = await talk(sock, [{"type": "listen", "id": "c1", "mode": "tap"}], {"transcript", "nothing", "error"}, 60)
            took = time.monotonic() - t0
            last = got[-1] if got else {"type": "timeout"}
            text = last.get("text", "") if last.get("type") == "transcript" else f"({last.get('type')}: {last.get('message', '')})"
            ok = last.get("type") == "transcript" and all(w.lower() in text.lower() for w in expected)
            said = await talk(sock, [{"type": "say", "id": "s1", "text": "Проверка связи.", "lang": "ru"},
                                     {"type": "say", "id": "s1", "text": "", "final": True}], {"spoken", "error"}, 60)
            spoken = bool(said) and said[-1].get("type") == "spoken"
            ok = ok and spoken
            return ok, (f"| {lang} | {text} | {'yes' if ok else 'NO'} | recognized in {last.get('ms', '—')} ms, "
                        f"phrase ended {took:.1f} s after the start; models loaded in {load_s:.1f} s; "
                        f"spoken: {spoken} |")
        finally:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), 10)
            except asyncio.TimeoutError:
                proc.kill()


async def main_async(args: argparse.Namespace) -> int:
    rows, ok_all = [], True
    for spec in args.phrase:
        lang, raw, words = spec.split(":", 2)
        ok, row = await run_phrase(args, lang, raw, [w for w in words.split(",") if w])
        rows.append(row)
        ok_all = ok_all and ok
    print("| lang | heard | ok | details |\n|---|---|---|---|")
    print("\n".join(rows))
    return 0 if ok_all else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--engine", default="none")
    ap.add_argument("--phrase", action="append", default=[])
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
