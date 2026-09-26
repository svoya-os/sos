#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Jackson's decision step on short requests the fast-path patterns miss («сделай-ка потише»).

Compares the decider SOS uses today (one token from the local chat model, jackson/decide.py) with
Laya, an open "System-1" decision model (Apache-2.0, convaiinnovations/laya), on phrases.tsv:
the model's pick, what Jackson would do with it at its thresholds (a wrong action is the number
that matters), and the time per decision on this machine's CPU.

    python3 tests/decide-eval/eval.py --laya --out dist/eval
    python3 tests/decide-eval/eval.py --llm http://127.0.0.1:8080/v1 --out dist/eval

Each run adds its decider to dist/eval/results.json; results.md summarizes all of them.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
import time
import traceback
import types

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "jackson"))

from jackson import decide, fastpath  # noqa: E402

INTENTS = [name for name, _, _ in fastpath.DECIDABLE]
LABELS = {  # Laya scores every option at its own label: short, plain labels
    "volume_up": "volume up", "volume_down": "volume down", "mute": "mute", "unmute": "unmute",
    "brightness_up": "brightness up", "brightness_down": "brightness down", "wifi_on": "wifi on",
    "wifi_off": "wifi off", "bluetooth_on": "bluetooth on", "bluetooth_off": "bluetooth off",
    "lock": "lock screen", "screenshot": "screenshot", "battery": "battery level", "time": "time",
    "none": "none",
}
INSTRUCTIONS = {"ru": "Какую системную команду просит выполнить пользователь?",
                "en": "Which system command does the user ask for?"}


def load_phrases() -> list[dict]:
    rows = []
    for line in (HERE / "phrases.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        lang, expected, text = line.split("\t")
        assert expected == "none" or expected in INTENTS, expected
        rows.append({"lang": lang, "expected": expected, "text": text})
    return rows


def action(text: str, index: int | None, p: float) -> tuple[str, str]:
    """What Jackson does, and how: a fast-path pattern first (no decider), then a candidate goes to the
    decider and only a sure pick acts; everything else is a full model turn (no command)."""
    m = fastpath.match(text)
    if m is not None:
        return (m.name if m.name in INTENTS else "none"), "pattern"
    norm = fastpath.decision_candidate(text)
    if norm is None:
        return "none", "model"
    if index is None:
        return "none", "decider"
    match = fastpath.decided_match(index, p, norm)
    return (match.name if match else "none"), "decider"


# ---------------------------------------------------------------------------------------------------
def decide_llm(url: str):
    prov = types.SimpleNamespace(cfg=types.SimpleNamespace(base_url=url.rstrip("/"), local=True),
                                 name="llama.cpp")

    def run(row: dict) -> tuple[int | None, float, list[float] | None]:
        picked = decide.choose(prov, "local", row["text"], fastpath.decision_options(row["lang"]), timeout=180)
        if picked is None:
            return None, 0.0, None
        return picked.index, picked.p, picked.probs
    return run


def load_laya(model: str):
    import laya  # noqa: F401  (pip install laya)
    if model == "router":                                   # Laya picks the checkpoint by language
        return laya.Router()
    if pathlib.Path(model).exists():                        # a checkpoint of ours: that one or nothing
        return laya.load(str(pathlib.Path(model).resolve()))
    attempts = []
    if "/" in model and model.count("/") == 2:            # repo/subfolder
        repo, sub = model.rsplit("/", 1)
        attempts.append(lambda: laya.load(repo, subfolder=sub))
    attempts += [lambda: laya.load(model), lambda: laya.load("convaiinnovations/laya-multilingual"),
                 lambda: laya.Router()]
    for make in attempts:
        try:
            return make()
        except Exception:
            traceback.print_exc()
    raise SystemExit("laya: no loader worked")


def decide_laya(model: str):
    agent = load_laya(model)
    names = INTENTS + ["none"]

    def run(row: dict) -> tuple[int | None, float, list[float] | None]:
        options = fastpath.decision_options(row["lang"])
        criteria = {LABELS[n]: desc for n, desc in zip(names, options)}
        questions = {"intent": {"type": "choice", "instructions": INSTRUCTIONS[row["lang"]], "criteria": criteria}}
        try:
            res = agent.predict(row["text"], questions)
        except TypeError:
            res = agent.predict({"document": row["text"]}, questions)
        ans = res["answers"]["intent"]
        choice = ans.get("choice")
        probs = ans.get("probabilities")
        by_label = {LABELS[n]: i for i, n in enumerate(names)}
        if isinstance(probs, dict):
            plist = [float(probs.get(LABELS[n], 0.0)) for n in names]
        elif isinstance(probs, list) and len(probs) == len(names):
            plist = [float(x) for x in probs]
        else:
            plist = None
        index = by_label.get(choice)
        p = float(ans.get("confidence") or (plist[index] if plist and index is not None else 0.0))
        return index, p, plist
    return run


# ---------------------------------------------------------------------------------------------------
def evaluate(name: str, run, rows: list[dict]) -> dict:
    out = []
    for row in rows:
        t0 = time.monotonic()
        try:
            index, p, probs = run(row)
            error = ""
        except Exception as exc:
            index, p, probs, error = None, 0.0, None, f"{type(exc).__name__}: {exc}"
        ms = (time.monotonic() - t0) * 1000
        picked = "none" if index is None or index >= len(INTENTS) else INTENTS[index]
        did, route = action(row["text"], index, p)
        out.append({**row, "picked": picked, "p": round(p, 4), "did": did, "route": route, "ms": round(ms, 1),
                    "error": error})
        print(f"[{name}] {row['lang']} {row['expected']:>15} → {picked:>15} p={p:.2f} did={did:>15} ({route:>7}) "
              f"{ms:7.0f} ms  {row['text']}", flush=True)
    return {"decider": name, "rows": out}


def summary(result: dict) -> list[str]:
    rows = result["rows"]
    lines = []
    for lang in ("ru", "en", "all"):
        sel = [r for r in rows if lang == "all" or r["lang"] == lang]
        if not sel:
            continue
        cmd = [r for r in sel if r["expected"] != "none"]
        neg = [r for r in sel if r["expected"] == "none"]
        picked_ok = sum(r["picked"] == r["expected"] for r in sel)
        did_ok = sum(r["did"] == r["expected"] for r in cmd)
        wrong = sum(r["did"] not in ("none", r["expected"]) and r.get("route") != "pattern" for r in sel)
        ms = sorted(r["ms"] for r in sel if not r["error"])
        p50 = statistics.median(ms) if ms else 0
        p95 = ms[min(len(ms) - 1, int(len(ms) * 0.95))] if ms else 0
        lines.append(f"| {result['decider']} | {lang} | {len(sel)} | {picked_ok / len(sel):.0%} | "
                     f"{did_ok}/{len(cmd)} | {wrong} | {sum(r['did'] == 'none' for r in neg)}/{len(neg)} | "
                     f"{p50:.0f} / {p95:.0f} | {sum(bool(r['error']) for r in sel)} |")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--llm", help="OpenAI-compatible base URL of a llama.cpp server (the decider SOS uses)")
    ap.add_argument("--laya", nargs="?", const="convaiinnovations/laya/multilingual",
                    help="Laya checkpoint (default: the multilingual one)")
    ap.add_argument("--name", help="decider name in the report")
    ap.add_argument("--out", default="dist/eval")
    args = ap.parse_args()
    rows = load_phrases()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    store = out / "results.json"
    results = json.loads(store.read_text()) if store.exists() else []
    if args.llm:
        results.append(evaluate(args.name or "llm (jackson/decide.py)", decide_llm(args.llm), rows))
    if args.laya:
        results.append(evaluate(args.name or f"laya ({args.laya})", decide_laya(args.laya), rows))
    store.write_text(json.dumps(results, ensure_ascii=False, indent=1))
    md = ["# Jackson's decision step: which command did the user mean?", "",
          f"{len(rows)} phrases (tests/decide-eval/phrases.tsv). *picked*: the decider's top option; *acted*: "
          "what Jackson would run — a fast-path pattern first, else the decider at his thresholds (p ≥ 0.9 to "
          "change something, 0.8 to read), commands only; *wrong*: a command the decider ran that nobody asked "
          "for (the number that must stay 0); *stayed out*: phrases that are not commands and ran nothing.", "",
          "| decider | lang | n | picked right | acted right | wrong | stayed out | ms p50 / p95 | errors |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        md += summary(r)
    md += ["", "## Misses", ""]
    for r in results:
        for row in r["rows"]:
            if row["did"] != row["expected"] or row["picked"] != row["expected"]:
                md.append(f"- {r['decider']} · {row['lang']} · «{row['text']}»: expected {row['expected']}, "
                          f"picked {row['picked']} (p {row['p']:.2f}), did {row['did']}"
                          + (f" — {row['error']}" if row["error"] else ""))
    (out / "results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:12 + 3 * len(results)]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
