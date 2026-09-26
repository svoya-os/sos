# SPDX-License-Identifier: Apache-2.0
"""Fetch the voice models into the shared store: ``sos install voice`` runs this in the voice venv.

    python -m jackson.voice.setup --models /srv/ai/voice [--engine NAME] [--check]

Silero VAD and Parakeet TDT 0.6B v3 (int8) come through onnx-asr from Hugging Face, the speech
engine's files through its own ``fetch``. Each model lands in a ``.part`` folder first and is renamed
when complete, so an interrupted download is fetched again instead of being loaded half-way.
``--check`` loads everything once (offline) and says what it would use.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable

from .stt import PARAKEET


def _size(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e9


def fetch_dir(dest: Path, load: Callable[[Path], Any], what: str) -> None:
    if dest.is_dir():
        print(f"  {what}: {dest} ({_size(dest):.2f} GB)")
        return
    part = dest.with_name(dest.name + ".part")
    shutil.rmtree(part, ignore_errors=True)
    t0 = time.monotonic()
    print(f"  {what}: downloading…", flush=True)
    load(part)
    for cache in part.glob(".cache"):          # huggingface_hub's bookkeeping for local_dir downloads
        shutil.rmtree(cache, ignore_errors=True)
    part.rename(dest)
    print(f"  {what}: {dest} ({_size(dest):.2f} GB, {time.monotonic() - t0:.0f} s)")


def fetch(models: Path, engine: str) -> None:
    import onnx_asr
    from .tts import engine_class
    models.mkdir(parents=True, exist_ok=True)
    fetch_dir(models / "silero-vad", lambda d: onnx_asr.load_vad("silero", d), "Silero VAD")
    fetch_dir(models / "parakeet-tdt-0.6b-v3", lambda d: onnx_asr.load_model(PARAKEET, d, quantization="int8"),
              "Parakeet TDT 0.6B v3 (int8)")
    cls = engine_class(engine)
    if hasattr(cls, "fetch"):
        cls.fetch(models, fetch_dir)


def check(models: Path, engine: str) -> int:
    import numpy as np
    from .stt import ParakeetSTT
    from .tts import load_engine
    from .vad import FRAME, SileroVAD
    t0 = time.monotonic()
    vad = SileroVAD(str(models / "silero-vad" / "silero_vad.onnx"))
    print(f"VAD: silence → {vad(np.zeros(FRAME, dtype=np.float32)):.2f}")
    stt = ParakeetSTT(models / "parakeet-tdt-0.6b-v3")
    print(f"STT: {stt.name}, silence → {stt.recognize(np.zeros(16000, dtype=np.float32))!r}")
    tts = load_engine(engine, models=models)
    audio = tts.synth("Проверка связи.", "ru", tts.voices()[0])
    print(f"TTS: {tts.name}, voices {tts.voices()}, {len(audio) / tts.rate:.1f} s of speech")
    print(f"loaded in {time.monotonic() - t0:.1f} s")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m jackson.voice.setup", description=__doc__.splitlines()[0])
    ap.add_argument("--models", type=Path, default=Path("/srv/ai/voice"))
    ap.add_argument("--engine", default="")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    from .tts import pick_engine
    engine = args.engine or pick_engine(args.models)
    if args.check:
        return check(args.models, engine)
    print(f"voice models → {args.models} (speech: {engine})")
    fetch(args.models, engine)
    return 0


if __name__ == "__main__":
    sys.exit(main())
