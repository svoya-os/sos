#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Render Jackson's lines (lines.json) in candidate voices, to choose his voice by ear.

    render.py ENGINE [ENGINE…] --out DIR

Engines: qwen (Qwen3-TTS: a voice per character designed from a description, then cloned — the
0.6B model is the one a CPU could run), supertonic (Supertonic 3), vosk (Vosk TTS, Russian),
silero (Silero v5_cis_base_nostress with silero-stress, Russian), kokoro (Kokoro-82M, English).

Each sample lands in DIR/<engine>/<voice>/<line>.wav with one JSON line in DIR/samples.jsonl:
{engine, voice, line, lang, text, wav, seconds, synth_s, model}. An engine that fails writes an
{engine, error} line and the next one runs; `score.py` then says what a recognizer hears.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import tempfile
import time
import traceback
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SPEC = json.loads((HERE / "lines.json").read_text(encoding="utf-8"))
LANG_NAME = {"ru": "Russian", "en": "English"}


def lines(lang: str | None = None) -> list[dict[str, Any]]:
    return [ln for ln in SPEC["lines"] if lang is None or ln["lang"] == lang]


class Out:
    def __init__(self, root: Path, engine: str) -> None:
        self.root = root
        self.engine = engine
        root.mkdir(parents=True, exist_ok=True)

    def log(self, rec: dict[str, Any]) -> None:
        with open(self.root / "samples.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def save(self, voice: str, line: dict[str, Any], wav: Any, sr: int, synth_s: float, **extra: Any) -> None:
        import numpy as np
        import soundfile as sf
        data = np.asarray(wav, dtype=np.float32).reshape(-1)
        path = self.root / self.engine / voice / f"{line['id']}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(path, data, int(sr))
        seconds = len(data) / float(sr)
        self.log({"engine": self.engine, "voice": voice, "line": line["id"], "lang": line["lang"],
                  "text": line["text"], "wav": str(path.relative_to(self.root)), "seconds": round(seconds, 2),
                  "synth_s": round(synth_s, 2), **extra})
        print(f"{self.engine}/{voice}/{line['id']}: {seconds:.1f} s of audio in {synth_s:.1f} s "
              f"(RTF {synth_s / max(seconds, 1e-3):.2f})", flush=True)


def timed(fn: Any, *args: Any, **kwargs: Any) -> tuple[Any, float]:
    t0 = time.monotonic()
    result = fn(*args, **kwargs)
    return result, time.monotonic() - t0


def fetch(url: str, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"download {url}", flush=True)
        urllib.request.urlretrieve(url, dest)
    return dest


# ---------------------------------------------------------------------------------------------
# engines

def qwen(out: Out) -> None:
    """Design a voice per character (1.7B VoiceDesign), then clone it with the Base models."""
    import torch
    from qwen_tts import Qwen3TTSModel

    torch.manual_seed(7)
    kw = {"device_map": "cpu", "dtype": torch.float32}
    design = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", **kw)
    refs: dict[tuple[str, str], tuple[Any, int]] = {}
    for d in SPEC["designs"]:
        for lang in ("ru", "en"):
            ref = {"id": f"reference-{lang}", "lang": lang, "text": SPEC["reference"][lang]}
            (wavs, sr), dt = timed(design.generate_voice_design, text=ref["text"], language=LANG_NAME[lang],
                                   instruct=d["instruct"])
            refs[(d["id"], lang)] = (wavs[0], sr)
            out.save(f"{d['id']}-design", ref, wavs[0], sr, dt, model="Qwen3-TTS-12Hz-1.7B-VoiceDesign",
                     instruct=d["instruct"])
    del design
    gc.collect()

    for size in ("1.7B", "0.6B"):
        model = f"Qwen3-TTS-12Hz-{size}-Base"
        base = Qwen3TTSModel.from_pretrained(f"Qwen/{model}", **kw)
        for d in SPEC["designs"]:
            for ref_lang in ("ru", "en"):
                prompt = base.create_voice_clone_prompt(ref_audio=refs[(d["id"], ref_lang)],
                                                        ref_text=SPEC["reference"][ref_lang])
                for line in lines():
                    if ref_lang == "en" and line["lang"] == "ru":
                        continue          # Russian lines only from the Russian reference
                    if size == "0.6B" and line["id"] not in SPEC["quick_lines"]:
                        continue
                    (wavs, sr), dt = timed(base.generate_voice_clone, text=line["text"],
                                           language=LANG_NAME[line["lang"]], voice_clone_prompt=prompt)
                    out.save(f"{d['id']}-{size}-from-{ref_lang}", line, wavs[0], sr, dt, model=model)
        del base
        gc.collect()


def supertonic(out: Out) -> None:
    root = Path(os.environ["SUPERTONIC_DIR"])
    sys.path.insert(0, str(root / "py"))
    from helper import load_text_to_speech, load_voice_style  # type: ignore[import-not-found]

    tts = load_text_to_speech(str(root / "assets" / "onnx"), False)
    for voice in ("M1", "M2", "M3", "M4", "M5"):
        style = load_voice_style([str(root / "assets" / "voice_styles" / f"{voice}.json")])
        for line in lines():
            (wav, duration), dt = timed(tts, line["text"], line["lang"], style, 8, 1.05)
            samples = wav[0, : int(tts.sample_rate * duration[0].item())]
            out.save(voice, line, samples, tts.sample_rate, dt, model="supertonic-3")


def vosk(out: Out) -> None:
    import soundfile as sf
    from vosk_tts import Model, Synth

    synth = Synth(Model(model_name="vosk-model-tts-ru-0.9-multi"))
    with tempfile.TemporaryDirectory() as tmp:
        for speaker in range(5):
            for line in lines("ru"):
                path = Path(tmp) / "out.wav"
                _, dt = timed(synth.synth, line["text"], str(path), speaker_id=speaker)
                wav, sr = sf.read(path)
                out.save(f"speaker-{speaker}", line, wav, sr, dt, model="vosk-model-tts-ru-0.9-multi")


def silero(out: Out) -> None:
    import torch
    from silero_stress import load_accentor

    cache = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir())
    path = fetch("https://models.silero.ai/models/tts/ru/v5_cis_base_nostress.pt", cache / "v5_cis_base_nostress.pt")
    model = torch.package.PackageImporter(str(path)).load_pickle("tts_models", "model")
    accentor = load_accentor()
    speakers = [s for s in getattr(model, "speakers", []) if str(s).startswith("ru_")]
    print("silero Russian speakers:", speakers, flush=True)
    for speaker in speakers:
        for line in lines("ru"):
            stressed = accentor(line.get("say") or line["text"])
            audio, dt = timed(model.apply_tts, text=stressed, speaker=speaker, sample_rate=48000)
            out.save(speaker, line, audio.numpy(), 48000, dt, model="silero v5_cis_base_nostress",
                     stressed=stressed)


def kokoro(out: Out) -> None:
    from kokoro_onnx import Kokoro

    cache = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "kokoro"
    rel = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
    tts = Kokoro(str(fetch(rel + "kokoro-v1.0.onnx", cache / "kokoro-v1.0.onnx")),
                 str(fetch(rel + "voices-v1.0.bin", cache / "voices-v1.0.bin")))
    for voice in ("am_michael", "am_fenrir", "am_puck", "am_onyx", "bm_george", "bm_lewis", "bm_fable",
                  "bm_daniel"):
        for line in lines("en"):
            (samples, sr), dt = timed(tts.create, line["text"], voice=voice, speed=1.0,
                                      lang="en-gb" if voice.startswith("b") else "en-us")
            out.save(voice, line, samples, sr, dt, model="kokoro-v1.0")


ENGINES = {"qwen": qwen, "supertonic": supertonic, "vosk": vosk, "silero": silero, "kokoro": kokoro}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("engines", nargs="+", choices=sorted(ENGINES))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    for name in args.engines:
        out = Out(args.out, name)
        t0 = time.monotonic()
        try:
            ENGINES[name](out)
            out.log({"engine": name, "done_s": round(time.monotonic() - t0, 1)})
        except Exception as exc:  # noqa: BLE001 - one engine failing must not stop the others
            traceback.print_exc()
            out.log({"engine": name, "error": f"{exc.__class__.__name__}: {exc}"[:500]})
        gc.collect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
