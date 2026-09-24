"""Will it fit? VRAM estimate for llama.cpp-style inference of a GGUF model.

Formula (bytes)::

  weights  = Σ tensor bytes of the chosen quant  (from tensor infos, all shards of a split GGUF;
             fallback: file size − header)
  kv       = n_ctx × Σ_layers n_kv_heads(l) × (d_k + d_v) × b(kv_type)
           = 2 × n_layers × n_ctx × n_kv_heads × head_dim × b   (the usual case d_k = d_v = head_dim)
             b = 2 (f16, bf16) · 34/32 (q8_0) · 18/32 (q4_0) · 4 (f32)
             MLA models (DeepSeek-style, kv_lora_rank > 0): n_ctx × n_layers × (kv_lora_rank + rope_dim) × b
             layers with n_kv_heads = 0 (recurrent layers of hybrid models) add nothing;
             sliding-window layers are counted at full n_ctx, so this is an upper bound for Gemma-style models.
  compute  = n_ubatch × 4 × (n_vocab + 8 × n_embd)                      logits + activations (f32)
           + (no flash attention: n_ubatch × n_ctx × n_head × 4)         KQ scores
  runtime  = 400 MiB for CUDA/ROCm (context + BLAS workspace), 256 MiB for Vulkan
  total    = weights + kv + compute + runtime

Verdicts, with budget = VRAM total − VRAM used by others − margin (max(256 MiB, 3 % of VRAM)):

  fits               total ≤ budget
  fits with offload  MoE: experts of the first N layers stay in RAM (llama.cpp ``--n-cpu-moe N``)
                     dense: the last k layers go to the GPU (``-ngl k``), k ≥ 1, where each GPU layer
                     costs its weights + its KV; the CPU part must fit in available RAM − 2 GiB
  doesn't fit        otherwise (a note says when CPU-only inference would still work)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .gguf import GGUFArray, GGUFHeader

MiB = 2**20
GiB = 2**30
KV_BYTES = {"f32": 4.0, "f16": 2.0, "bf16": 2.0, "q8_0": 34 / 32, "q5_1": 24 / 32, "q5_0": 22 / 32,
            "q4_1": 20 / 32, "q4_0": 18 / 32, "iq4_nl": 18 / 32}
RUNTIME = {"cuda": 400 * MiB, "rocm": 400 * MiB, "vulkan": 256 * MiB, "cpu": 0}
RAM_RESERVE = 2 * GiB
N_UBATCH = 512
_BLK = re.compile(r"^blk\.(\d+)\.")


@dataclass
class ModelShape:
    arch: str
    name: str | None = None
    n_layers: int = 0
    n_ctx_train: int | None = None
    n_embd: int = 0
    n_head: int = 0
    kv_heads: list[int] = field(default_factory=list)   # per layer
    d_k: int = 0
    d_v: int = 0
    n_vocab: int = 0
    expert_count: int = 0
    expert_used: int = 0
    kv_lora_rank: int = 0
    rope_dim: int = 0
    weights: int = 0
    layer_bytes: list[int] = field(default_factory=list)
    expert_bytes: list[int] = field(default_factory=list)
    embd_bytes: int = 0
    other_bytes: int = 0
    params: int | None = None
    quant: str | None = None
    size_label: str | None = None
    license: str | None = None
    exact_weights: bool = True

    @property
    def is_moe(self) -> bool:
        return self.expert_count > 1 and sum(self.expert_bytes) > 0

    @property
    def is_llm(self) -> bool:
        return self.n_layers > 0 and self.n_embd > 0


def _int(v, default: int = 0) -> int:
    if isinstance(v, bool):
        return default
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return default


def _per_layer(v, n_layers: int, default: int) -> list[int]:
    if isinstance(v, list):
        vals = [_int(x, default) for x in v]
        return (vals + [vals[-1] if vals else default] * n_layers)[:n_layers]
    if isinstance(v, GGUFArray):
        vals = [_int(x, default) for x in v.sample]
        return (vals + [vals[-1] if vals else default] * n_layers)[:n_layers]
    return [_int(v, default)] * n_layers


def shape_from_headers(headers: list[GGUFHeader], file_sizes: list[int]) -> ModelShape:
    """Build the shape from the first shard's metadata and every shard's tensor infos."""
    h = headers[0]
    a = h.arch
    n_layers = _int(h.arch_get("block_count"))
    n_embd = _int(h.arch_get("embedding_length"))
    heads = _per_layer(h.arch_get("attention.head_count"), max(n_layers, 1), 0)
    n_head = max(heads) if heads else 0
    kv_raw = h.arch_get("attention.head_count_kv")
    kv_heads = _per_layer(kv_raw if kv_raw is not None else h.arch_get("attention.head_count"), n_layers, n_head)
    d_default = n_embd // n_head if n_head else 0
    d_k = _int(h.arch_get("attention.key_length"), d_default)
    d_v = _int(h.arch_get("attention.value_length"), d_k or d_default)
    vocab = _int(h.arch_get("vocab_size"))
    if not vocab:
        toks = h.get("tokenizer.ggml.tokens")
        vocab = len(toks) if isinstance(toks, (list, GGUFArray)) else 0
    s = ModelShape(arch=a, name=h.get("general.name") or h.get("general.basename"), n_layers=n_layers,
                   n_ctx_train=_int(h.arch_get("context_length")) or None, n_embd=n_embd, n_head=n_head,
                   kv_heads=kv_heads, d_k=d_k, d_v=d_v, n_vocab=vocab,
                   expert_count=_int(h.arch_get("expert_count")), expert_used=_int(h.arch_get("expert_used_count")),
                   kv_lora_rank=_int(h.arch_get("attention.kv_lora_rank")),
                   rope_dim=_int(h.arch_get("rope.dimension_count")), quant=h.file_type,
                   size_label=h.get("general.size_label"), license=h.get("general.license"))
    layer = [0] * n_layers
    experts = [0] * n_layers
    embd = other = 0
    params = 0
    exact = True
    for hdr, fsize in zip(headers, file_sizes):
        tb = hdr.tensor_bytes()
        if hdr.tensors is None or tb is None:
            exact = False
            other += max(0, fsize - (hdr.data_offset or 0))
            continue
        for t in hdr.tensors:
            nb = t.nbytes or 0
            params += t.n_elements
            m = _BLK.match(t.name)
            if m and int(m.group(1)) < n_layers:
                i = int(m.group(1))
                layer[i] += nb
                if "_exps" in t.name:
                    experts[i] += nb
            elif t.name.startswith("token_embd"):
                embd += nb
            else:
                other += nb
    s.layer_bytes, s.expert_bytes, s.embd_bytes, s.other_bytes = layer, experts, embd, other
    s.weights = sum(layer) + embd + other
    s.params = params or None
    s.exact_weights = exact
    return s


def kv_per_layer(s: ModelShape, n_ctx: int, kv_type: str = "f16") -> list[int]:
    b = KV_BYTES.get(kv_type.lower())
    if b is None:
        raise ValueError(f"unknown KV cache type {kv_type!r} (use {', '.join(KV_BYTES)})")
    if s.kv_lora_rank:
        per = n_ctx * (s.kv_lora_rank + s.rope_dim) * b
        return [int(per)] * s.n_layers
    return [int(n_ctx * h * (s.d_k + s.d_v) * b) for h in s.kv_heads]


@dataclass
class Estimate:
    weights: int
    kv: int
    compute: int
    runtime: int
    n_ctx: int
    kv_type: str
    flash_attn: bool
    kv_layers: list[int] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.weights + self.kv + self.compute + self.runtime


def estimate(s: ModelShape, n_ctx: int = 8192, kv_type: str = "f16", *, flash_attn: bool = True,
             n_ubatch: int = N_UBATCH, backend: str = "cuda") -> Estimate:
    kv_layers = kv_per_layer(s, n_ctx, kv_type) if s.is_llm else []
    compute = 0
    if s.is_llm:
        ub = min(n_ubatch, n_ctx)
        compute = ub * 4 * (s.n_vocab + 8 * s.n_embd)
        if not flash_attn:
            compute += ub * n_ctx * s.n_head * 4
    return Estimate(weights=s.weights, kv=sum(kv_layers), compute=compute, runtime=RUNTIME.get(backend, RUNTIME["cuda"]),
                    n_ctx=n_ctx, kv_type=kv_type, flash_attn=flash_attn, kv_layers=kv_layers)


@dataclass
class Fit:
    verdict: str                     # fits | offload | no
    budget: int
    vram_total: int | None
    vram_used: int | None
    n_layers: int
    gpu_layers: int
    ram_needed: int = 0
    ram_available: int | None = None
    n_cpu_moe: int | None = None
    notes: list[tuple[str, str]] = field(default_factory=list)   # (en, ru)

    def as_json(self) -> dict:
        return {"verdict": self.verdict, "budgetBytes": self.budget, "vramTotalBytes": self.vram_total,
                "vramUsedBytes": self.vram_used, "nLayers": self.n_layers, "gpuLayers": self.gpu_layers,
                "ramNeededBytes": self.ram_needed, "ramAvailableBytes": self.ram_available,
                "nCpuMoe": self.n_cpu_moe, "notes": [{"en": en, "ru": ru} for en, ru in self.notes]}


def margin(vram_total: int) -> int:
    return max(256 * MiB, int(vram_total * 0.03))


def fit(s: ModelShape, est: Estimate, vram_total: int | None, vram_used: int | None = 0,
        ram_available: int | None = None) -> Fit:
    used = vram_used or 0
    budget = max(0, (vram_total or 0) - used - margin(vram_total or 0)) if vram_total else 0
    f = Fit(verdict="no", budget=budget, vram_total=vram_total, vram_used=vram_used, n_layers=s.n_layers,
            gpu_layers=0, ram_available=ram_available)
    ram_ok = (lambda need: ram_available is None or need <= max(0, ram_available - RAM_RESERVE))

    if s.n_ctx_train and est.n_ctx > s.n_ctx_train:
        f.notes.append((f"context {est.n_ctx} is longer than the model was trained for ({s.n_ctx_train})",
                        f"контекст {est.n_ctx} длиннее обучающего ({s.n_ctx_train})"))
    if vram_total and est.total <= budget:
        f.verdict, f.gpu_layers = "fits", s.n_layers
        return f
    if not vram_total or not s.is_llm:
        if est.total <= (ram_available or 0) - RAM_RESERVE:
            f.notes.append(("no GPU memory for it, but it runs on the CPU (slowly)",
                            "в видеопамять не влезает, но пойдёт на процессоре (медленно)"))
        return f

    fixed = est.runtime + est.compute
    # MoE: keep all layers on the GPU, move the experts of the first N layers to RAM (--n-cpu-moe N)
    if s.is_moe:
        gpu_cost = est.total
        for n in range(1, s.n_layers + 1):
            gpu_cost -= s.expert_bytes[n - 1]
            if gpu_cost <= budget:
                need = sum(s.expert_bytes[:n])
                if ram_ok(need):
                    f.verdict, f.gpu_layers, f.n_cpu_moe, f.ram_needed = "offload", s.n_layers, n, need
                    f.notes.append((f"llama.cpp: --n-cpu-moe {n} (experts of {n} layers in RAM, attention on the GPU)",
                                    f"llama.cpp: --n-cpu-moe {n} (эксперты {n} слоёв в ОЗУ, внимание на ГП)"))
                    return f
                break

    # dense layer offload: last k layers on the GPU (llama.cpp -ngl k)
    avail = budget - fixed - s.other_bytes
    k = 0
    cost = 0
    for i in range(s.n_layers - 1, -1, -1):
        c = s.layer_bytes[i] + (est.kv_layers[i] if i < len(est.kv_layers) else 0)
        if cost + c > avail:
            break
        cost += c
        k += 1
    if k >= 1:
        cpu_part = est.weights + est.kv - cost - s.other_bytes
        if ram_ok(cpu_part):
            f.verdict, f.gpu_layers, f.ram_needed = "offload", k, cpu_part
            f.notes.append((f"llama.cpp: -ngl {k} ({k} of {s.n_layers} layers on the GPU, the rest in RAM — slower)",
                            f"llama.cpp: -ngl {k} ({k} из {s.n_layers} слоёв на ГП, остальное в ОЗУ — медленнее)"))
            return f
        f.ram_needed = cpu_part
        f.notes.append(("not enough free RAM for the offloaded part", "не хватает свободной ОЗУ для выгрузки"))
        return f
    if est.total <= (ram_available or 0) - RAM_RESERVE:
        f.notes.append(("runs on the CPU only (slowly)", "пойдёт только на процессоре (медленно)"))
    return f


def suggest_ctx(s: ModelShape, budget: int, kv_type: str = "f16", flash_attn: bool = True,
                backend: str = "cuda") -> int | None:
    """Largest power-of-two context (≥ 2048) that still fits entirely in ``budget``."""
    best = None
    n = 2048
    limit = s.n_ctx_train or 131072
    while n <= limit:
        if estimate(s, n, kv_type, flash_attn=flash_attn, backend=backend).total <= budget:
            best = n
        else:
            break
        n *= 2
    return best
