#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""What a speech recognizer hears in each sample of render.py, and how fast each voice speaks.

    score.py DIR

Reads DIR/samples.jsonl, transcribes every WAV with Parakeet TDT 0.6B v3 (onnx-asr, Russian and
English), and writes DIR/results.json and DIR/results.md: per voice the character error rate
against the line as it should sound ('say' or the text) and the real-time factor on this CPU.
The recognizer is the one Jackson would listen with, so this also shows how well it hears.
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SPEC = json.loads((HERE / "lines.json").read_text(encoding="utf-8"))
SAY = {ln["id"]: ln.get("say") or ln["text"] for ln in SPEC["lines"]}
SAY.update({f"reference-{k}": v for k, v in SPEC["reference"].items()})


def norm(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


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


def main(argv: list[str]) -> int:
    root = Path(argv[1])
    records = [json.loads(x) for x in (root / "samples.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    samples = [r for r in records if "wav" in r]
    engines = [r for r in records if "wav" not in r]
    try:
        import onnx_asr
        t0 = time.monotonic()
        asr = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3")
        print(f"recognizer loaded in {time.monotonic() - t0:.0f} s", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"no recognizer: {exc}", flush=True)
        asr = None
    for r in samples:
        if asr is None:
            break
        try:
            t0 = time.monotonic()
            heard = asr.recognize(str(root / r["wav"]))
            r["heard"] = heard if isinstance(heard, str) else str(getattr(heard, "text", heard))
            r["asr_s"] = round(time.monotonic() - t0, 2)
            r["cer"] = round(cer(SAY.get(r["line"], r["text"]), r["heard"]), 3)
        except Exception as exc:  # noqa: BLE001
            r["heard_error"] = str(exc)[:200]

    voices: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in samples:
        voices[(r["engine"], r["voice"])].append(r)
    table = []
    for (engine, voice), rs in sorted(voices.items()):
        audio = sum(r["seconds"] for r in rs)
        synth = sum(r["synth_s"] for r in rs)
        cers = [r["cer"] for r in rs if "cer" in r]
        table.append({"engine": engine, "voice": voice, "samples": len(rs), "model": rs[0].get("model", ""),
                      "rtf": round(synth / audio, 2) if audio else None,
                      "cer": round(sum(cers) / len(cers), 3) if cers else None})
    (root / "results.json").write_text(json.dumps({"voices": table, "samples": samples, "engines": engines},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# Jackson's voice: candidates", "",
          "RTF: seconds of work per second of speech on this runner's CPU (under 1 is faster than speech). "
          "CER: share of characters a recognizer (Parakeet TDT 0.6B v3) hears differently from the line.", "",
          "| engine | voice | model | samples | RTF | CER |", "|---|---|---|---|---|---|"]
    for t in table:
        md.append(f"| {t['engine']} | {t['voice']} | {t['model']} | {t['samples']} | {t['rtf']} | {t['cer']} |")
    md += ["", "## Engines", ""]
    md += [f"- {e['engine']}: " + (f"error — {e['error']}" if "error" in e else f"done in {e.get('done_s')} s")
           for e in engines]
    md += ["", "## What the recognizer heard", ""]
    for r in samples:
        if "heard" in r:
            md.append(f"- `{r['engine']}/{r['voice']}/{r['line']}` ({r.get('cer')}): {r['heard']}")
    (root / "results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:len(table) + 6]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
