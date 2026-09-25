"""Synthetic GGUF files for tests: realistic metadata and tensor layouts, tiny tensor payloads."""
from __future__ import annotations

from pathlib import Path

from svoya_cli.models import gguf

Q4_K = gguf.GGML_TYPE_ID["Q4_K"]
Q6_K = gguf.GGML_TYPE_ID["Q6_K"]
F32 = gguf.GGML_TYPE_ID["F32"]
MXFP4 = gguf.GGML_TYPE_ID["MXFP4"]


def llama_like(path: Path, *, arch: str = "llama", n_layers: int = 4, n_embd: int = 256, n_head: int = 8,
               n_head_kv: int | list = 2, vocab: int = 512, ctx: int = 4096, experts: int = 0, head_dim: int | None = None,
               extra: dict | None = None, types: dict | None = None, byteorder: str = "<", split: tuple | None = None,
               with_tensors: bool = True, tokens: int | None = None) -> int:
    meta = {
        "general.architecture": arch,
        "general.name": f"Synth {arch}",
        "general.file_type": 15,           # Q4_K_M
        "general.license": "apache-2.0",
        "general.alignment": 32,
        f"{arch}.block_count": n_layers,
        f"{arch}.context_length": ctx,
        f"{arch}.embedding_length": n_embd,
        f"{arch}.attention.head_count": n_head,
        f"{arch}.attention.head_count_kv": n_head_kv,
        "tokenizer.ggml.model": "gpt2",
        "tokenizer.ggml.tokens": [f"t{i}" for i in range(tokens if tokens is not None else vocab)],
        "tokenizer.ggml.scores": [0.0] * (tokens if tokens is not None else vocab),
    }
    if head_dim:
        meta[f"{arch}.attention.key_length"] = head_dim
        meta[f"{arch}.attention.value_length"] = head_dim
    if experts:
        meta[f"{arch}.expert_count"] = experts
        meta[f"{arch}.expert_used_count"] = 2
    if split:
        meta["split.no"], meta["split.count"] = split
    meta.update(extra or {})
    t = {"tokenizer.ggml.scores": (gguf.ARRAY, gguf.FLOAT32)}
    if isinstance(n_head_kv, list):
        t[f"{arch}.attention.head_count_kv"] = (gguf.ARRAY, gguf.UINT32)
    t.update(types or {})
    tensors = []
    if with_tensors:
        tensors.append(("token_embd.weight", (n_embd, vocab), Q4_K))
        for i in range(n_layers):
            tensors += [(f"blk.{i}.attn_q.weight", (n_embd, n_embd), Q4_K),
                        (f"blk.{i}.attn_k.weight", (n_embd, n_embd // 4), Q4_K),
                        (f"blk.{i}.attn_v.weight", (n_embd, n_embd // 4), Q6_K),
                        (f"blk.{i}.attn_output.weight", (n_embd, n_embd), Q4_K),
                        (f"blk.{i}.attn_norm.weight", (n_embd,), F32)]
            if experts:
                tensors += [(f"blk.{i}.ffn_up_exps.weight", (n_embd, 512, experts), Q4_K),
                            (f"blk.{i}.ffn_down_exps.weight", (512, n_embd, experts), Q4_K)]
            else:
                tensors += [(f"blk.{i}.ffn_up.weight", (n_embd, 4 * n_embd), Q4_K),
                            (f"blk.{i}.ffn_down.weight", (4 * n_embd, n_embd), Q6_K)]
        tensors += [("output_norm.weight", (n_embd,), F32), ("output.weight", (n_embd, vocab), Q6_K)]
    return gguf.write_file(path, meta, tensors, types=t, byteorder=byteorder)
