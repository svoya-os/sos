import unittest

from svoya_cli.models import estimate as E
from svoya_cli.models import gguf

from .gguf_synth import llama_like
from .helpers import SandboxTest

GiB = 2**30


def shape(**kw) -> E.ModelShape:
    base = dict(arch="llama", n_layers=32, n_embd=4096, n_head=32, kv_heads=[8] * 32, d_k=128, d_v=128, n_vocab=128256,
                n_ctx_train=131072, weights=int(4.6 * GiB), layer_bytes=[int(4.2 * GiB / 32)] * 32,
                expert_bytes=[0] * 32, embd_bytes=int(0.2 * GiB), other_bytes=int(0.2 * GiB))
    base.update(kw)
    return E.ModelShape(**base)


class KvFormulaTest(unittest.TestCase):
    def test_textbook_formula(self):
        s = shape()
        est = E.estimate(s, 8192, "f16")
        # 2 × n_layers × n_ctx × n_kv_heads × head_dim × 2 bytes  (Llama-3-8B-like: 1 GiB at 8k)
        self.assertEqual(est.kv, 2 * 32 * 8192 * 8 * 128 * 2)
        self.assertEqual(est.kv, GiB)

    def test_q8_0_cache(self):
        est = E.estimate(shape(), 8192, "q8_0")
        self.assertEqual(est.kv, int(GiB * 34 / 32 / 2) // 32 * 32)

    def test_hybrid_layers_have_no_kv(self):
        kv = [8 if (i + 1) % 4 == 0 else 0 for i in range(32)]
        self.assertEqual(E.estimate(shape(kv_heads=kv), 8192).kv, GiB // 4)

    def test_mla(self):
        s = shape(kv_lora_rank=512, rope_dim=64)
        self.assertEqual(E.estimate(s, 8192).kv, 32 * 8192 * (512 + 64) * 2)

    def test_compute_buffer(self):
        s = shape()
        fa = E.estimate(s, 8192, flash_attn=True)
        nofa = E.estimate(s, 8192, flash_attn=False)
        act, scores, logits = 512 * 32 * 4096 * 4, 512 * 8192 * 32 * 4, 128256 * 4 * 8
        self.assertEqual(fa.compute, act + logits)                        # ≈ 260 MiB (llama.cpp: ~258)
        self.assertEqual(nofa.compute, scores + act // 10 + logits)       # ≈ 540 MiB (llama.cpp: ~560)
        self.assertTrue(250 * 2**20 < fa.compute < 270 * 2**20)
        self.assertEqual(fa.runtime, 400 * 2**20)
        self.assertEqual(fa.total, fa.weights + fa.kv + fa.compute + fa.runtime)

    def test_bad_kv_type(self):
        with self.assertRaises(ValueError):
            E.estimate(shape(), 8192, "q3_k")


class FitTest(unittest.TestCase):
    def test_fits(self):
        s = shape()
        f = E.fit(s, E.estimate(s, 8192), 24 * GiB, 1 * GiB, 32 * GiB)
        self.assertEqual((f.verdict, f.gpu_layers), ("fits", 32))

    def test_offload_dense(self):
        s = shape(weights=int(17 * GiB), layer_bytes=[int(16.4 * GiB / 32)] * 32)
        f = E.fit(s, E.estimate(s, 8192), 12 * GiB, int(0.5 * GiB), 64 * GiB)
        self.assertEqual(f.verdict, "offload")
        self.assertTrue(10 < f.gpu_layers < 32)
        self.assertIn("-ngl", f.notes[-1][0])
        self.assertGreater(f.ram_needed, 0)

    def test_offload_needs_ram(self):
        s = shape(weights=int(40 * GiB), layer_bytes=[int(39.5 * GiB / 32)] * 32)
        f = E.fit(s, E.estimate(s, 8192), 12 * GiB, 0, 8 * GiB)
        self.assertEqual(f.verdict, "no")

    def test_moe_experts_to_ram(self):
        per = int(0.6 * GiB)
        s = shape(weights=int(20 * GiB), layer_bytes=[per] * 32, expert_bytes=[int(per * 0.9)] * 32, expert_count=128)
        f = E.fit(s, E.estimate(s, 8192), 16 * GiB, int(0.5 * GiB), 64 * GiB)
        self.assertEqual(f.verdict, "offload")
        self.assertEqual(f.gpu_layers, 32)
        self.assertTrue(f.n_cpu_moe and 1 <= f.n_cpu_moe <= 32)
        self.assertIn("--n-cpu-moe", f.notes[-1][0])

    def test_no_gpu(self):
        s = shape()
        f = E.fit(s, E.estimate(s, 8192), None, None, 64 * GiB)
        self.assertEqual(f.verdict, "no")
        self.assertTrue(any("CPU" in n[0] for n in f.notes))

    def test_margin_and_suggested_ctx(self):
        self.assertEqual(E.margin(8 * GiB), 256 * 2**20)
        self.assertEqual(E.margin(48 * GiB), int(48 * GiB * 0.03))
        s = shape(weights=int(9 * GiB), layer_bytes=[int(8.6 * GiB / 32)] * 32)
        ctx = E.suggest_ctx(s, 12 * GiB)
        self.assertIsNotNone(ctx)
        self.assertLessEqual(E.estimate(s, ctx).total, 12 * GiB)
        self.assertGreater(E.estimate(s, ctx * 2).total, 12 * GiB)


class ShapeFromGGUFTest(SandboxTest):
    def test_shape_from_synthetic_file(self):
        p = self.sb.path("/m/x.gguf")
        p.parent.mkdir(parents=True)
        size = llama_like(p, n_layers=4, n_embd=256, n_head=8, n_head_kv=2)
        h = gguf.read_file(p)
        s = E.shape_from_headers([h], [size])
        self.assertEqual((s.n_layers, s.n_embd, s.n_head, s.d_k, s.n_vocab), (4, 256, 8, 32, 512))
        self.assertEqual(s.kv_heads, [2, 2, 2, 2])
        self.assertEqual(s.weights, h.tensor_bytes())
        self.assertEqual(sum(s.layer_bytes) + s.embd_bytes + s.other_bytes, s.weights)
        est = E.estimate(s, 1024)
        self.assertEqual(est.kv, 2 * 4 * 1024 * 2 * 32 * 2)
        self.assertEqual(s.license, "apache-2.0")

    def test_hybrid_interval_and_per_layer_kv_array(self):
        p = self.sb.path("/m/h.gguf")
        p.parent.mkdir(parents=True)
        size = llama_like(p, arch="qwen35", n_layers=8, n_head_kv=4, head_dim=64,
                          extra={"qwen35.full_attention_interval": 4})
        s = E.shape_from_headers([gguf.read_file(p)], [size])
        self.assertEqual(s.kv_heads, [0, 0, 0, 4, 0, 0, 0, 4])
        p2 = self.sb.path("/m/a.gguf")
        size = llama_like(p2, n_layers=4, n_head_kv=[4, 0, 4, 0])
        self.assertEqual(E.shape_from_headers([gguf.read_file(p2)], [size]).kv_heads, [4, 0, 4, 0])

    def test_moe_expert_bytes(self):
        p = self.sb.path("/m/moe.gguf")
        p.parent.mkdir(parents=True)
        size = llama_like(p, n_layers=2, experts=4)
        s = E.shape_from_headers([gguf.read_file(p)], [size])
        self.assertTrue(s.is_moe)
        self.assertTrue(all(e > 0 for e in s.expert_bytes))


if __name__ == "__main__":
    unittest.main()
