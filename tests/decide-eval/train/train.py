#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fine-tune Laya's multilingual checkpoint on Jackson's commands, on a CPU.

Laya's own recipe (notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb in NandhaKishorM/laya,
Apache-2.0): RLCD, a policy gradient on proper scoring rules plus a soft cross-entropy, then one
temperature fitted on a held-out slice. Ported to one CPU process: no DDP, no fp16, the token
embeddings frozen (256k-token vocabulary: most of the parameters, no FLOPs, and the optimizer state
would not fit a GitHub runner otherwise).

    python3 tests/decide-eval/train/train.py --out dist/laya-jackson

The questions are built exactly as tests/decide-eval/eval.py asks them (labels, descriptions from
jackson/fastpath.py DECIDABLE, the instruction), and every phrase of tests/decide-eval/phrases.tsv
is kept out of training.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "jackson"))

import base  # noqa: E402
from eval import INSTRUCTIONS, INTENTS, LABELS  # noqa: E402
from jackson import fastpath  # noqa: E402

PREFIX = {"ru": ["", "", "Джексон, ", "слушай, ", "эй, ", "ну ", "а ", "так, ", "джексон "],
          "en": ["", "", "Jackson, ", "hey, ", "ok ", "hey jackson ", "so "]}
SUFFIX = {"ru": ["", "", " пожалуйста", " плиз", "!", " срочно", " ок?", "."],
          "en": ["", "", " please", "!", " now", " thanks", "."]}
MIN_PER_CLASS = {"ru": 60, "en": 30}


def norm(text: str) -> str:
    return re.sub(r"[^\w]+", " ", text.lower().replace("ё", "е")).strip()


def held_out() -> set[str]:
    out = set()
    with open(os.path.join(HERE, "..", "phrases.tsv"), encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                out.add(norm(line.rstrip("\n").split("\t")[2]))
    return out


def examples(seed: int = 7) -> list[tuple[str, str, str]]:
    """(lang, intent, text): every base phrase, variants with fillers around it, small classes topped up."""
    rng = random.Random(seed)
    skip = held_out()
    rows = []
    for lang, table in (("ru", base.RU), ("en", base.EN)):
        for intent, phrases in table.items():
            phrases = [p for p in phrases if norm(p) not in skip]
            seen = set()
            out = []
            for p in phrases:
                out.append(p)
                seen.add(p)
            target = max(3 * len(phrases), MIN_PER_CLASS[lang])
            tries = 0
            while len(out) < target and tries < target * 20:
                tries += 1
                p = rng.choice(phrases)
                v = rng.choice(PREFIX[lang]) + p + rng.choice(SUFFIX[lang])
                if rng.random() < 0.3:
                    v = v[:1].upper() + v[1:]
                if v not in seen and norm(v) not in skip:
                    seen.add(v)
                    out.append(v)
            rows += [(lang, intent, t) for t in out]
    return rows


def question(lang: str) -> dict:
    names = INTENTS + ["none"]
    crit = {LABELS[n]: d for n, d in zip(names, fastpath.decision_options(lang))}
    return {"t": "choice", "ins": INSTRUCTIONS[lang], "crit": crit}


def build_items(tok, cfg: dict, rows) -> list[dict]:
    from laya.common import QTYPES, build_sequence, render_options
    names = INTENTS + ["none"]
    items = []
    for lang, intent, text in rows:
        q = question(lang)
        k = len(render_options(q))
        seq, markers = build_sequence(tok, text, q, cfg["max_len"], cfg["head_max_len"])
        if len(markers) != k:
            raise SystemExit(f"options cut off for «{text}»: {len(markers)} of {k} markers")
        label = names.index(intent)
        target = [0.1 / (k - 1)] * k      # a soft target: calibrated probabilities, not certainty
        target[label] = 0.9
        items.append({"ids": seq, "markers": markers, "qtype": QTYPES["choice"], "target": target,
                      "label": label, "lang": lang, "text": text})
    return items


def collate(items, pad_id):
    import torch
    n, L = len(items), max(len(it["ids"]) for it in items)
    kmax = max(len(it["markers"]) for it in items)
    ids = torch.full((n, L), pad_id, dtype=torch.long)
    att = torch.zeros((n, L), dtype=torch.long)
    mpos = torch.zeros((n, kmax), dtype=torch.long)
    mmask = torch.zeros((n, kmax), dtype=torch.bool)
    target = torch.zeros((n, kmax), dtype=torch.float32)
    for i, it in enumerate(items):
        ids[i, :len(it["ids"])] = torch.tensor(it["ids"])
        att[i, :len(it["ids"])] = 1
        k = len(it["markers"])
        mpos[i, :k] = torch.tensor(it["markers"])
        mmask[i, :k] = True
        target[i, :k] = torch.tensor(it["target"], dtype=torch.float32)
    return {"input_ids": ids, "attention_mask": att, "marker_pos": mpos, "marker_mask": mmask,
            "target": target, "qtype": torch.tensor([it["qtype"] for it in items]),
            "label": torch.tensor([it["label"] for it in items])}


def fit_one_temp(sel) -> float:
    import torch
    if len(sel) < 10:
        return 1.0
    kmax = max(len(z) for z, _ in sel)
    Z = torch.full((len(sel), kmax), -1e4)
    T = torch.zeros((len(sel), kmax))
    for i, (z, t) in enumerate(sel):
        Z[i, :len(z)] = torch.tensor(z)
        T[i, :len(t)] = torch.tensor(t, dtype=torch.float32)
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=100)

    def closure():
        opt.zero_grad()
        loss = -(T * torch.log_softmax(Z / log_t.exp(), -1)).sum(-1).mean()
        loss.backward()
        return loss
    opt.step(closure)
    return float(torch.clamp(log_t.exp(), 0.1, 10.0).item())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="dist/laya-jackson")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--micro-batch", type=int, default=8)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--lr-encoder", type=float, default=2e-5)
    ap.add_argument("--lr-head", type=float, default=1e-4)
    ap.add_argument("--dry-run", action="store_true", help="build the training set and stop")
    args = ap.parse_args()

    rows = examples()
    per = {}
    for lang, intent, _ in rows:
        per[(lang, intent)] = per.get((lang, intent), 0) + 1
    print(f"{len(rows)} training phrases:", ", ".join(f"{l}/{i} {n}" for (l, i), n in sorted(per.items())))
    if args.dry_run:
        return 0

    import torch
    from huggingface_hub import snapshot_download
    from safetensors.torch import load_file, save_file
    from transformers import AutoTokenizer
    from laya.agent import _fix_tokenizer_config
    from laya.common import build_model, proper_reward

    root = snapshot_download("convaiinnovations/laya", allow_patterns=["multilingual/*"])
    model_dir = os.path.join(root, "multilingual")
    _fix_tokenizer_config(model_dir)
    with open(os.path.join(model_dir, "rl_agent_config.json")) as f:
        cfg = json.load(f)
    tok = AutoTokenizer.from_pretrained(os.path.join(model_dir, "tokenizer"))
    torch.set_num_threads(os.cpu_count() or 4)

    items = build_items(tok, cfg, rows)
    order = list(range(len(items)))
    random.Random(20260926).shuffle(order)
    n_calib = max(40, len(items) // 10)
    calib = [items[i] for i in order[:n_calib]]
    train = [items[i] for i in order[n_calib:]]
    print(f"train {len(train)}, calibration {len(calib)}; max tokens {max(len(it['ids']) for it in items)}")

    model = build_model(cfg, encoder_dir=os.path.join(model_dir, "encoder"))
    model.load_state_dict(load_file(os.path.join(model_dir, "model.safetensors")), strict=True)
    emb = model.encoder.get_input_embeddings()
    emb.weight.requires_grad_(False)
    model.train()

    enc = [p for n, p in model.named_parameters() if n.startswith("encoder.") and p.requires_grad]
    head = [p for n, p in model.named_parameters() if not n.startswith("encoder.") and p.requires_grad]
    opt = torch.optim.AdamW([{"params": enc, "lr": args.lr_encoder}, {"params": head, "lr": args.lr_head}],
                            weight_decay=0.01)
    updates = max(1, (len(train) // (args.micro_batch * args.grad_accum)) * args.epochs)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=updates, eta_min=1e-6)
    G, S0, S1 = 4, 0.4, 0.1
    t0 = time.time()
    for epoch in range(args.epochs):
        random.Random(42 + epoch).shuffle(train)
        sigma = S0 + (S1 - S0) * (epoch / max(1, args.epochs - 1))
        total, n, step = 0.0, 0, 0
        opt.zero_grad(set_to_none=True)
        for b in range(0, len(train), args.micro_batch):
            batch = collate(train[b:b + args.micro_batch], tok.pad_token_id)
            logits, act = model(batch["input_ids"], batch["attention_mask"], batch["marker_pos"],
                                batch["marker_mask"], batch["qtype"])
            mask = batch["marker_mask"]
            k = mask.sum(-1, keepdim=True).float()
            target = batch["target"]
            eps = torch.randn((G,) + logits.shape) * sigma * mask
            eps = (eps - eps.sum(-1, keepdim=True) / k) * mask
            z = logits.detach().unsqueeze(0) + eps
            q = torch.softmax(z.masked_fill(~mask, -1e4), -1)
            with torch.no_grad():
                r = proper_reward(q, target.unsqueeze(0), batch["qtype"], mask, w_sph=0.75, w_rps=1.0)
                adv = r - r.mean(0, keepdim=True)
                adv = adv / (adv.std() + 1e-6)
            logp = -(((z - logits.unsqueeze(0)) ** 2) * mask).sum(-1) / (2 * sigma ** 2)
            loss_rl = -(adv * logp).mean()
            loss_ce = -(target * torch.log_softmax(logits.masked_fill(~mask, -1e4), -1)).sum(-1).mean()
            loss = (loss_rl + loss_ce) / args.grad_accum + 0.0 * act.sum()
            loss.backward()
            step += 1
            if step % args.grad_accum == 0 or b + args.micro_batch >= len(train):
                torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
                opt.step()
                sched.step()
                opt.zero_grad(set_to_none=True)
            total += loss.item() * args.grad_accum
            n += 1
            if n % 25 == 0:
                print(f"  epoch {epoch + 1}/{args.epochs} batch {n} loss {loss.item() * args.grad_accum:.4f} "
                      f"reward {r.mean().item():.3f} ({time.time() - t0:.0f} s)", flush=True)
        print(f"=== epoch {epoch + 1}/{args.epochs}: mean loss {total / max(1, n):.4f} ({time.time() - t0:.0f} s)",
              flush=True)

    model.eval()
    preds, right = [], 0
    with torch.no_grad():
        for c in range(0, len(calib), 16):
            chunk = calib[c:c + 16]
            cb = collate(chunk, tok.pad_token_id)
            logits, _ = model(cb["input_ids"], cb["attention_mask"], cb["marker_pos"], cb["marker_mask"], cb["qtype"])
            for i, it in enumerate(chunk):
                z = logits[i, :len(it["markers"])].float().numpy()
                preds.append((z, it["target"]))
                right += int(z.argmax() == it["label"])
    temp = fit_one_temp(preds)
    print(f"calibration slice: {right}/{len(calib)} right; temperature {temp:.3f}")

    out = args.out
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    save_file({k: v.half().contiguous() for k, v in model.state_dict().items()}, os.path.join(out, "model.safetensors"))
    model.encoder.config.save_pretrained(os.path.join(out, "encoder"))
    tok.save_pretrained(os.path.join(out, "tokenizer"))
    cfg["fine_tuned"] = True
    cfg["model_name"] = "laya-multilingual-jackson"
    cfg["temperature"] = [temp, cfg.get("temperature", [1.0, 1.0, 1.0])[1], cfg.get("temperature", [1.0, 1.0, 1.0])[2]]
    cfg.pop("temperature_by_options", None)
    with open(os.path.join(out, "rl_agent_config.json"), "w") as f:
        json.dump(cfg, f, indent=2)
    with open(os.path.join(out, "TRAINING.json"), "w") as f:
        json.dump({"base": "convaiinnovations/laya (multilingual)", "phrases": len(rows), "train": len(train),
                   "calibration": len(calib), "calibration_right": right, "temperature": temp,
                   "epochs": args.epochs, "seconds": round(time.time() - t0)}, f, indent=2)
    print(f"saved {out} ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
