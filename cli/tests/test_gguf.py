import io
import struct
import unittest

from svoya_cli.models import gguf

from .gguf_synth import Q4_K, llama_like
from .helpers import SandboxTest


class GGUFTest(SandboxTest):
    def test_all_metadata_types_roundtrip(self):
        p = self.sb.path("/m/all.gguf")
        p.parent.mkdir(parents=True)
        meta = {"u8": 200, "i8": -5, "u16": 60000, "i16": -30000, "u32": 4_000_000_000, "i32": -2_000_000_000,
                "f32": 0.5, "b": True, "s": "привет", "u64": 2**40, "i64": -(2**40), "f64": 1.25,
                "arr_i": [1, 2, 3], "arr_s": ["a", "б"], "arr_nested": [[1, 2], [3]], "general.alignment": 64}
        types = {"u8": gguf.UINT8, "i8": gguf.INT8, "u16": gguf.UINT16, "i16": gguf.INT16, "u32": gguf.UINT32,
                 "i32": gguf.INT32, "u64": gguf.UINT64, "i64": gguf.INT64, "f64": gguf.FLOAT64,
                 "arr_i": (gguf.ARRAY, gguf.INT32), "arr_nested": (gguf.ARRAY, gguf.ARRAY)}
        gguf.write_file(p, meta, [("w", (64, 4), Q4_K)], types=types)
        h = gguf.read_file(p)
        self.assertEqual(h.version, 3)
        for k, v in meta.items():
            self.assertEqual(h.metadata[k], v, k)
        self.assertEqual(h.types["u8"], gguf.UINT8)
        self.assertEqual(h.alignment, 64)
        self.assertEqual(h.data_offset % 64, 0)
        self.assertEqual(h.tensors[0].nbytes, (64 * 4 // 256) * 144)

    def test_model_file_and_tensor_bytes(self):
        p = self.sb.path("/m/model.gguf")
        p.parent.mkdir(parents=True)
        size = llama_like(p, n_layers=3)
        h = gguf.read_file(p)
        self.assertEqual(h.arch, "llama")
        self.assertEqual(h.file_type, "Q4_K_M")
        self.assertEqual(h.tensor_count, len(h.tensors))
        self.assertEqual(h.arch_get("block_count"), 3)
        self.assertLessEqual(h.data_offset + h.tensor_bytes(), size)
        self.assertTrue(gguf.is_gguf(p))

    def test_big_arrays_are_skipped_with_sample(self):
        p = self.sb.path("/m/vocab.gguf")
        p.parent.mkdir(parents=True)
        llama_like(p, tokens=5000)
        h = gguf.read_file(p, keep_array=256)
        toks = h.metadata["tokenizer.ggml.tokens"]
        self.assertIsInstance(toks, gguf.GGUFArray)
        self.assertEqual(len(toks), 5000)
        self.assertEqual(toks.sample[:2], ["t0", "t1"])

    def test_big_endian(self):
        p = self.sb.path("/m/be.gguf")
        p.parent.mkdir(parents=True)
        llama_like(p, byteorder=">", n_layers=2)
        h = gguf.read_file(p)
        self.assertEqual(h.byteorder, ">")
        self.assertEqual(h.arch_get("block_count"), 2)

    def test_errors(self):
        with self.assertRaises(gguf.GGUFError):
            gguf.read_header(io.BytesIO(b"GGML" + b"\0" * 20))
        with self.assertRaises(gguf.GGUFError):
            gguf.read_header(io.BytesIO(b"GGUF" + struct.pack("<IQQ", 3, 0, 1) + b"\x05\0"))   # truncated
        with self.assertRaises(gguf.GGUFError):
            gguf.read_header(io.BytesIO(b"GGUF" + struct.pack("<IQQ", 3, 0, 10**9)))           # absurd counts
        with self.assertRaises(gguf.GGUFError):
            gguf.read_header(io.BytesIO(b"GGUF" + struct.pack("<I", 9)))                      # version

    def test_type_table_sizes(self):
        # bytes per block from ggml-common.h static_asserts
        expect = {"Q4_0": (32, 18), "Q8_0": (32, 34), "Q4_K": (256, 144), "Q5_K": (256, 176), "Q6_K": (256, 210),
                  "IQ4_XS": (256, 136), "IQ2_XXS": (256, 66), "IQ3_S": (256, 110), "IQ1_M": (256, 56),
                  "MXFP4": (32, 17), "TQ1_0": (256, 54), "BF16": (1, 2)}
        for name, (blk, size) in expect.items():
            _, b, s = gguf.GGML_TYPES[gguf.GGML_TYPE_ID[name]]
            self.assertEqual((b, s), (blk, size), name)


if __name__ == "__main__":
    unittest.main()
