#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Jackson's character voices on a processor, without a graphics card: qwen3-tts.cpp (MIT, C++ and
ggml) runs Qwen3-TTS 12Hz 0.6B Base and says the lines of tests/voice-samples/lines.json in each
character's reference voice (the Voice samples run designed them); Jackson's own ears
(jackson/voice/stt.py) say what they hear. Nothing here ships.

    render.py --cli BIN --refs DIR --asr DIR --out DIR --variant NAME=MODELS[:DESIGN,…] … [--threads N]

For each variant (a folder of GGUF files: q8_0 or f16) and design, DIR/<variant>/<design>/<line>.wav
and one JSON line in DIR/samples.jsonl; DIR/results.md has the real-time factor (seconds of work
per second of speech, the model load not counted) and what the recognizers heard.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = json.loads((HERE.parent / "voice-samples" / "lines.json").read_text(encoding="utf-8"))
NAMES = {"kent": "Кентафурик", "calm": "Спокойный (в духе Джарвиса)", "dispatcher": "Диспетчер",
         "pirate": "Пиратское радио"}
TIMING = re.compile(r"^\s*(Load|Tokenize|Encode|Generate|Decode|Total):\s*(\d+)\s*ms", re.MULTILINE)


def norm(text: str) -> str:
    text = text.lower().replace("ё", "е")
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def cer(ref: str, hyp: str) -> float:
    a, b = norm(ref), norm(hyp)
    if not a:
        return 0.0 if not b else 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1] / len(a)


def read_wav(path: Path) -> tuple[list[float] | None, int, float]:
    with wave.open(str(path), "rb") as w:
        rate, n = w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    import numpy as np
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return samples, rate, n / float(rate)


def to_16k(samples, rate: int):
    import numpy as np
    if rate == 16000 or not len(samples):
        return samples
    n = int(len(samples) * 16000 / rate)
    return np.interp(np.arange(n) * (rate / 16000), np.arange(len(samples)), samples).astype(np.float32)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cli", required=True)
    ap.add_argument("--refs", type=Path, required=True, help="<design>/reference-<lang>.wav")
    ap.add_argument("--asr", type=Path, required=True, help="the voice models (jackson.voice.setup)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--variant", action="append", required=True, help="name=models_dir[:design,design]")
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args(argv)

    from jackson.voice.stt import BilingualSTT, GigaAMSTT, ParakeetSTT
    t0 = time.monotonic()
    ears = BilingualSTT(ParakeetSTT(args.asr / "parakeet-tdt-0.6b-v3"), GigaAMSTT(args.asr / "gigaam-v3-e2e-rnnt"))
    print(f"recognizers loaded in {time.monotonic() - t0:.1f} s", file=sys.stderr, flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    for spec in args.variant:
        name, _, rest = spec.partition("=")
        models, _, only = rest.partition(":")
        designs = [d for d in (only.split(",") if only else [d["id"] for d in SPEC["designs"]]) if d]
        for design in designs:
            for line in SPEC["lines"]:
                ref = args.refs / design / f"reference-{line['lang']}.wav"
                out = args.out / name / design / f"{line['id']}.wav"
                out.parent.mkdir(parents=True, exist_ok=True)
                cmd = [args.cli, "-m", models, "-t", line["text"], "-r", str(ref), "-o", str(out),
                       "-l", line["lang"], "-j", str(args.threads)]
                w0 = time.monotonic()
                proc = subprocess.run(cmd, capture_output=True, text=True)
                wall = time.monotonic() - w0
                rec = {"variant": name, "design": design, "line": line["id"], "lang": line["lang"], "text": line["text"]}
                if proc.returncode != 0 or not out.exists():
                    rec["error"] = (proc.stderr or proc.stdout)[-600:]
                    print(f"{name}/{design}/{line['id']}: failed\n{rec['error']}", file=sys.stderr, flush=True)
                    records.append(rec)
                    continue
                timing = {k.lower(): int(v) for k, v in TIMING.findall(proc.stderr)}
                work = sum(timing.get(k, 0) for k in ("tokenize", "encode", "generate", "decode")) / 1000.0
                samples, rate, seconds = read_wav(out)
                heard = ears.recognize(to_16k(samples, rate))
                rec.update(wav=str(out.relative_to(args.out)), seconds=round(seconds, 2), wall_s=round(wall, 2),
                           work_s=round(work or wall, 2), timing=timing, heard=heard, model=ears.last,
                           cer=round(cer(line.get("say") or line["text"], heard), 3))
                print(f"{name}/{design}/{line['id']}: {seconds:.1f} s of speech in {rec['work_s']:.1f} s "
                      f"(RTF {rec['work_s'] / max(seconds, 1e-3):.2f}), heard «{heard}» (CER {rec['cer']})",
                      file=sys.stderr, flush=True)
                records.append(rec)
    with open(args.out / "samples.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    md = ["## Jackson's characters on a processor (qwen3-tts.cpp, Qwen3-TTS 0.6B Base)", "",
          "RTF: seconds of work per second of speech on this runner (model loading not counted; under 1 keeps "
          "up with speech). PyTorch on the same kind of runner: about 6 for 0.6B (Voice samples run 36266187438). "
          "CER: share of characters Jackson's recognizers hear differently from the line.", "",
          "| variant | character | RTF | CER | lines |", "|---|---|---|---|---|"]
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in records:
        groups.setdefault((r["variant"], r["design"]), []).append(r)
    for (variant, design), rs in groups.items():
        ok = [r for r in rs if "seconds" in r]
        rtf = sum(r["work_s"] for r in ok) / max(sum(r["seconds"] for r in ok), 1e-3) if ok else None
        mean_cer = sum(r["cer"] for r in ok) / len(ok) if ok else None
        md.append(f"| {variant} | {NAMES.get(design, design)} | {'—' if rtf is None else f'{rtf:.2f}'} | "
                  f"{'—' if mean_cer is None else f'{mean_cer:.3f}'} | {len(ok)}/{len(rs)} |")
    md += ["", "### What the recognizers heard", ""]
    for r in records:
        if "heard" in r:
            md.append(f"- `{r['variant']}/{r['design']}/{r['line']}` ({r['seconds']} s, RTF "
                      f"{r['work_s'] / max(r['seconds'], 1e-3):.2f}, CER {r['cer']}): {r['heard']}")
        else:
            md.append(f"- `{r['variant']}/{r['design']}/{r['line']}`: failed")
    (args.out / "results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0 if any("heard" in r for r in records) else 1


if __name__ == "__main__":
    sys.exit(main())
