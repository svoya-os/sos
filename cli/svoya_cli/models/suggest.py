"""``sos models suggest`` — one best local model for this machine plus two alternatives.

1. Hardware: the biggest GPU (VRAM; VRAM+GTT on unified-memory APUs such as Strix Halo), RAM, free
   disk in the store. No usable GPU (< 4 GiB) → the CPU tier, judged against RAM.
2. Tier (``data/model_ladder.toml``) by usable GiB; its picks are checked with the fit estimator at
   8k context (+ the vision projector when the model has one) against the budget minus a desktop
   allowance. The first pick that fits is the default; the others are the alternatives.
3. Speed class (rough): tokens/s ≈ 0.55 × memory bandwidth / bytes read per token, where bytes per
   token = file size × active/total parameters (MoE) and bandwidth is guessed from the memory class
   (CPU 60 GB/s · APU 256 · ≤8 GB 300 · ≤12 GB 450 · ≤16 GB 550 · ≤24 GB 900 · ≤32 GB 1500).
   Offloaded models are counted three times slower. Classes: fast ≥ 40 · good ≥ 15 · slow ≥ 6.
"""
from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ..context import Ctx
from ..hw import gpu as gpu_mod
from ..i18n import pick, tr
from . import estimate as est_mod

GiB = 2**30
CTX = 8192
DESKTOP_MIN = int(0.4 * GiB)
DESKTOP_MAX = int(1.5 * GiB)


def load_ladder(data_dir: Path | None = None) -> dict:
    base = data_dir or Path(__file__).resolve().parent.parent / "data"
    with open(base / "model_ladder.toml", "rb") as f:
        data = tomllib.load(f)
    return {"models": {m["id"]: m for m in data.get("model", [])}, "tiers": data.get("tier", [])}


@dataclass
class Choice:
    model: dict
    quant: dict

    @property
    def id(self) -> str:
        return f"{self.model['id']}:{self.quant['name']}"

    @property
    def files(self) -> list[dict]:
        q = self.quant
        return list(q["files"]) if "files" in q else [{"file": q["file"], "size": q["size"]}]

    @property
    def size(self) -> int:
        return sum(f["size"] for f in self.files)

    @property
    def mmproj(self) -> dict | None:
        return self.model.get("mmproj")


def resolve(alias: str, ladder: dict | None = None) -> Choice | None:
    """``qwen3.5-27b:Q4_K_M`` → that quant; ``qwen3.5-27b`` → its first (smallest) quant."""
    ladder = ladder or load_ladder()
    mid, _, qname = alias.strip().lower().partition(":")
    m = ladder["models"].get(mid)
    if not m:
        return None
    quants = m["quants"]
    if not qname:
        return Choice(m, quants[0])
    q = next((q for q in quants if q["name"].lower() == qname), None)
    return Choice(m, q) if q else None


def shape_for(c: Choice) -> est_mod.ModelShape:
    a = c.model["arch"]
    layers, every = int(a["layers"]), int(a.get("attn_every", 1))
    kv = [a["kv_heads"] if (i + 1) % every == 0 else 0 for i in range(layers)]
    weights = c.size + (c.mmproj["size"] if c.mmproj else 0)
    s = est_mod.ModelShape(arch=a.get("name", "llama"), name=c.model["name"], n_layers=layers,
                           n_ctx_train=a.get("ctx_train"), n_embd=a["embd"], n_head=a["heads"], kv_heads=kv,
                           d_k=a["head_dim"], d_v=a["head_dim"], n_vocab=a["vocab"],
                           expert_count=int(c.model.get("experts", 0)), quant=c.quant["name"],
                           license=c.model.get("license"), exact_weights=False)
    # no tensor infos offline: spread the weights evenly; MoE experts ≈ everything but the active share
    per_layer = int(weights * 0.97 / layers)
    s.layer_bytes = [per_layer] * layers
    s.other_bytes = weights - per_layer * layers
    s.weights = weights
    if s.expert_count:
        active = float(c.model.get("active_b", c.model["params_b"])) / float(c.model["params_b"])
        s.expert_bytes = [int(per_layer * (1 - active))] * layers
    else:
        s.expert_bytes = [0] * layers
    s.params = int(float(c.model["params_b"]) * 1e9)
    return s


def hardware(ctx: Ctx) -> dict:
    gpus = gpu_mod.live_stats(ctx)
    from .cli import ram_available
    mem = ctx.read("/proc/meminfo") or ""
    import re
    m = re.search(r"^MemTotal:\s+(\d+)\s+kB", mem, re.M)
    ram_total = int(m.group(1)) * 1024 if m else None
    best = None
    for g in gpus:
        total = (g.get("vramTotalMiB") or 0) * 2**20
        if g.get("integrated"):
            total += (g.get("gttTotalMiB") or 0) * 2**20
        if best is None or total > best[1]:
            best = (g, total)
    root = ctx.paths.ai_root
    probe = root if root.exists() else root.parent if root.parent.exists() else Path("/")
    try:
        disk_free = shutil.disk_usage(probe).free
    except OSError:
        disk_free = None
    hw = {"gpu": None, "vendor": None, "memoryBytes": None, "unified": False, "usedBytes": 0,
          "ramTotalBytes": ram_total, "ramAvailableBytes": ram_available(ctx), "diskFreeBytes": disk_free,
          "backend": "cpu"}
    if best and best[1] >= 4 * GiB:
        g, total = best
        used = min(DESKTOP_MAX, max(DESKTOP_MIN, (g.get("vramUsedMiB") or 0) * 2**20))
        hw.update(gpu=g.get("name"), vendor=g.get("vendor"), memoryBytes=total, unified=bool(g.get("integrated")),
                  usedBytes=used, backend={"nvidia": "cuda", "amd": "rocm"}.get(g.get("vendor", ""), "vulkan"))
    return hw


def _bandwidth(hw: dict) -> float:
    if hw["backend"] == "cpu":
        return 60.0
    if hw["unified"]:
        return 256.0
    gb = (hw["memoryBytes"] or 0) / GiB
    for limit, bw in ((8.5, 300.0), (12.5, 450.0), (16.5, 550.0), (24.5, 900.0), (32.5, 1500.0)):
        if gb <= limit:
            return bw
    return 900.0


SPEED = {"fast": ("fast", "быстро"), "good": ("comfortable", "комфортно"), "slow": ("slow", "медленно"),
         "very-slow": ("very slow", "очень медленно")}


def _speed(c: Choice, hw: dict, verdict: str) -> tuple[str, int]:
    active = float(c.model.get("active_b", c.model["params_b"])) / float(c.model["params_b"])
    per_token = c.size * active / 1e9
    tps = 0.55 * _bandwidth(hw) / max(per_token, 0.1)
    if verdict == "offload":
        tps /= 3
    # people read ~5–8 tokens/s: from 10 tok/s an answer outruns the eye
    cls = "fast" if tps >= 30 else "good" if tps >= 10 else "slow" if tps >= 4 else "very-slow"
    return cls, int(round(tps))


def evaluate(c: Choice, hw: dict) -> dict:
    s = shape_for(c)
    backend = hw["backend"] if hw["backend"] != "cpu" else "cpu"
    est = est_mod.estimate(s, CTX, "f16", backend=backend)
    if hw["backend"] == "cpu":
        avail = (hw["ramAvailableBytes"] or hw["ramTotalBytes"] or 0) - est_mod.RAM_RESERVE
        verdict, n_cpu_moe, gpu_layers = ("fits" if est.total <= avail else "no"), None, 0
    else:
        f = est_mod.fit(s, est, hw["memoryBytes"], hw["usedBytes"], hw["ramAvailableBytes"])
        verdict, n_cpu_moe, gpu_layers = f.verdict, f.n_cpu_moe, f.gpu_layers
    disk_ok = hw["diskFreeBytes"] is None or c.size + (c.mmproj["size"] if c.mmproj else 0) <= hw["diskFreeBytes"]
    speed, tps = _speed(c, hw, verdict)
    return {
        "id": c.id, "model": c.model["id"], "name": c.model["name"], "quant": c.quant["name"],
        "repo": c.model["repo"], "files": [f["file"] for f in c.files],
        "mmproj": c.mmproj["file"] if c.mmproj else None,
        "sizeBytes": c.size + (c.mmproj["size"] if c.mmproj else 0),
        "memoryBytes8k": est.total, "ctx": CTX, "verdict": verdict, "nCpuMoe": n_cpu_moe, "gpuLayers": gpu_layers,
        # what it takes to run at all: on CPU the model plus what the system keeps for itself
        "needBytes": est.total + (est_mod.RAM_RESERVE if hw["backend"] == "cpu" else 0),
        "needKind": "ram" if hw["backend"] == "cpu" else "vram",
        "diskOk": disk_ok, "speed": speed, "tokensPerSecond": tps, "license": c.model.get("license"),
        "vision": bool(c.model.get("vision")), "note": pick(c.model.get("note")),
        "pull": f"sos models pull {c.id} --yes",
    }


def choose_tier(ladder: dict, hw: dict) -> dict:
    tiers = sorted(ladder["tiers"], key=lambda t: t["min_gb"])
    if hw["backend"] == "cpu":
        return next(t for t in tiers if t["id"] == "cpu")
    gb = (hw["memoryBytes"] or 0) / GiB
    chosen = tiers[0]
    for t in tiers:
        if t["id"] != "cpu" and gb >= t["min_gb"]:
            chosen = t
    return chosen


def suggest(ctx: Ctx, hw: dict | None = None, ladder: dict | None = None) -> dict:
    ladder = ladder or load_ladder()
    hw = hw or hardware(ctx)
    tiers = sorted(ladder["tiers"], key=lambda t: t["min_gb"])
    tier = choose_tier(ladder, hw)
    evals = [evaluate(resolve(p, ladder), hw) for p in tier["picks"]]
    ok = [e for e in evals if e["verdict"] == "fits" and e["diskOk"]]
    if not ok:  # the tier is optimistic for this exact card: borrow from the tier below
        idx = tiers.index(tier)
        for lower in reversed(tiers[:idx]):
            if lower["id"] == "cpu" and hw["backend"] != "cpu":
                continue
            more = [evaluate(resolve(p, ladder), hw) for p in lower["picks"]]
            ok = [e for e in more if e["verdict"] == "fits" and e["diskOk"]]
            if ok:
                evals = ok[:1] + evals
                break
    default = (ok or [e for e in evals if e["verdict"] == "offload"] or evals)[0]
    alts = [e for e in evals if e["id"] != default["id"]][:2]
    return {"hardware": hw, "tier": tier["id"], "tierName": pick(tier.get("name")), "ctx": CTX,
            "default": default, "alternatives": alts}


VERDICT_TEXT = {"fits": ("fits", "влезет"), "offload": ("with offload to RAM", "с выгрузкой в ОЗУ"),
                "no": ("does not fit", "не влезет")}


def describe(e: dict) -> str:
    v = tr(*VERDICT_TEXT[e["verdict"]])
    if e["verdict"] == "no":
        # a speed for a model that cannot run here only confuses: say what it would need instead
        need = e.get("needBytes") or e.get("memoryBytes8k") or e.get("sizeBytes") or 0
        gb = f"{need / 1024 ** 3:.1f}".replace(".", "," if tr("en", "ru") == "ru" else ".")
        what = tr("RAM", "ОЗУ") if e.get("needKind") == "ram" else tr("VRAM", "видеопамяти")
        return f"{v} · {tr('needs', 'нужно')} ~{gb} {tr('GB', 'ГБ')} {what}"
    sp = tr(*SPEED[e["speed"]])
    return f"{v} · {sp} (~{e['tokensPerSecond']} {tr('tok/s', 'ток/с')})"
