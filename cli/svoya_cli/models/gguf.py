"""Pure-Python GGUF reader (v2/v3, little- and big-endian) — header, metadata and tensor infos.

Spec: github.com/ggml-org/ggml docs/gguf.md. Layout::

    magic "GGUF" · u32 version · u64 tensor_count · u64 kv_count
    kv_count × (gguf_string key · u32 value_type · value)
    tensor_count × (gguf_string name · u32 n_dims · u64 dims[n_dims] · u32 ggml_type · u64 offset)
    padding to general.alignment (default 32) · tensor data

Reads only what it needs through any object with ``read(n)`` (a file or an HTTP range reader), so
a remote header costs a few MB at most. Big arrays (tokenizer vocab, merges) are skipped and kept as
``GGUFArray(type, length, sample)``. Hostile files are bounded (sizes/counts sanity-checked).
"""
from __future__ import annotations

import io
import os
import struct
from dataclasses import dataclass, field
from typing import Any, BinaryIO, Iterable

MAGIC = b"GGUF"

UINT8, INT8, UINT16, INT16, UINT32, INT32, FLOAT32, BOOL, STRING, ARRAY, UINT64, INT64, FLOAT64 = range(13)
_FMT = {UINT8: "B", INT8: "b", UINT16: "H", INT16: "h", UINT32: "I", INT32: "i", FLOAT32: "f",
        BOOL: "?", UINT64: "Q", INT64: "q", FLOAT64: "d"}
TYPE_NAMES = {UINT8: "u8", INT8: "i8", UINT16: "u16", INT16: "i16", UINT32: "u32", INT32: "i32",
              FLOAT32: "f32", BOOL: "bool", STRING: "str", ARRAY: "arr", UINT64: "u64", INT64: "i64",
              FLOAT64: "f64"}

# ggml_type id → (name, elements per block, bytes per block)   (ggml/src/ggml-common.h, 2026-09)
GGML_TYPES: dict[int, tuple[str, int, int]] = {
    0: ("F32", 1, 4), 1: ("F16", 1, 2), 2: ("Q4_0", 32, 18), 3: ("Q4_1", 32, 20),
    6: ("Q5_0", 32, 22), 7: ("Q5_1", 32, 24), 8: ("Q8_0", 32, 34), 9: ("Q8_1", 32, 36),
    10: ("Q2_K", 256, 84), 11: ("Q3_K", 256, 110), 12: ("Q4_K", 256, 144), 13: ("Q5_K", 256, 176),
    14: ("Q6_K", 256, 210), 15: ("Q8_K", 256, 292), 16: ("IQ2_XXS", 256, 66), 17: ("IQ2_XS", 256, 74),
    18: ("IQ3_XXS", 256, 98), 19: ("IQ1_S", 256, 50), 20: ("IQ4_NL", 32, 18), 21: ("IQ3_S", 256, 110),
    22: ("IQ2_S", 256, 82), 23: ("IQ4_XS", 256, 136), 24: ("I8", 1, 1), 25: ("I16", 1, 2),
    26: ("I32", 1, 4), 27: ("I64", 1, 8), 28: ("F64", 1, 8), 29: ("IQ1_M", 256, 56),
    30: ("BF16", 1, 2), 34: ("TQ1_0", 256, 54), 35: ("TQ2_0", 256, 66), 39: ("MXFP4", 32, 17),
    40: ("NVFP4", 64, 36), 41: ("Q1_0", 128, 18), 42: ("Q2_0", 64, 18),
}
GGML_TYPE_ID = {v[0]: k for k, v in GGML_TYPES.items()}

# general.file_type (llama.h LLAMA_FTYPE_*)
FILE_TYPES = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 7: "Q8_0", 8: "Q5_0", 9: "Q5_1", 10: "Q2_K",
    11: "Q3_K_S", 12: "Q3_K_M", 13: "Q3_K_L", 14: "Q4_K_S", 15: "Q4_K_M", 16: "Q5_K_S",
    17: "Q5_K_M", 18: "Q6_K", 19: "IQ2_XXS", 20: "IQ2_XS", 21: "Q2_K_S", 22: "IQ3_XS",
    23: "IQ3_XXS", 24: "IQ1_S", 25: "IQ4_NL", 26: "IQ3_S", 27: "IQ3_M", 28: "IQ2_S", 29: "IQ2_M",
    30: "IQ4_XS", 31: "IQ1_M", 32: "BF16", 36: "TQ1_0", 37: "TQ2_0", 38: "MXFP4_MOE",
    39: "NVFP4", 40: "Q1_0", 41: "Q2_0",
}

MAX_STRING = 64 * 2**20        # a single metadata string (chat templates can be large)
MAX_ARRAY = 2**26              # elements
MAX_KV = 2**16
MAX_TENSORS = 2**20
MAX_DIMS = 8


class GGUFError(ValueError):
    pass


@dataclass
class GGUFArray:
    """A large array that was skipped: element type, length and the first few elements."""
    type: int
    length: int
    sample: list = field(default_factory=list)

    def __len__(self) -> int:
        return self.length


@dataclass
class TensorInfo:
    name: str
    shape: tuple[int, ...]
    type: int
    offset: int

    @property
    def n_elements(self) -> int:
        n = 1
        for d in self.shape:
            n *= d
        return n

    @property
    def type_name(self) -> str:
        return GGML_TYPES.get(self.type, (f"type{self.type}", 1, 0))[0]

    @property
    def nbytes(self) -> int | None:
        t = GGML_TYPES.get(self.type)
        if t is None:
            return None
        _, blck, size = t
        return (self.n_elements // blck) * size


@dataclass
class GGUFHeader:
    version: int
    tensor_count: int
    kv_count: int
    metadata: dict[str, Any]
    types: dict[str, int]
    tensors: list[TensorInfo] | None = None
    data_offset: int | None = None       # absolute offset of tensor data (after padding)
    byteorder: str = "<"

    @property
    def alignment(self) -> int:
        a = self.metadata.get("general.alignment", 32)
        return a if isinstance(a, int) and a > 0 else 32

    @property
    def arch(self) -> str:
        return str(self.metadata.get("general.architecture", "llama"))

    def get(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    def arch_get(self, suffix: str, default: Any = None) -> Any:
        return self.metadata.get(f"{self.arch}.{suffix}", default)

    @property
    def file_type(self) -> str | None:
        ft = self.metadata.get("general.file_type")
        if isinstance(ft, int):
            return FILE_TYPES.get(ft & ~1024, f"ftype{ft}")
        return None

    def tensor_bytes(self) -> int | None:
        if self.tensors is None:
            return None
        total = 0
        for t in self.tensors:
            nb = t.nbytes
            if nb is None:
                return None
            total += nb
        return total


class _Reader:
    def __init__(self, f: BinaryIO, order: str = "<"):
        self.f = f
        self.order = order
        self.pos = 0

    def read(self, n: int) -> bytes:
        b = self.f.read(n)
        if len(b) != n:
            raise GGUFError(f"unexpected end of file at byte {self.pos + len(b)} (wanted {n})")
        self.pos += n
        return b

    def skip(self, n: int) -> None:
        if n <= 0:
            return
        seek = getattr(self.f, "seek", None)
        if seek is not None and getattr(self.f, "seekable", lambda: False)():
            self.f.seek(n, io.SEEK_CUR)
            self.pos += n
            return
        while n:
            chunk = min(n, 1 << 20)
            self.read(chunk)
            n -= chunk

    def scalar(self, t: int) -> Any:
        fmt = _FMT[t]
        size = struct.calcsize(fmt)
        return struct.unpack(self.order + fmt, self.read(size))[0]

    def u32(self) -> int:
        return self.scalar(UINT32)

    def u64(self) -> int:
        return self.scalar(UINT64)

    def string(self, limit: int = MAX_STRING) -> str:
        n = self.u64()
        if n > limit:
            raise GGUFError(f"string of {n} bytes exceeds limit")
        return self.read(n).decode("utf-8", errors="replace")

    def skip_string(self) -> None:
        n = self.u64()
        if n > MAX_STRING:
            raise GGUFError(f"string of {n} bytes exceeds limit")
        self.skip(n)

    def value(self, t: int, keep_array: int) -> Any:
        if t in _FMT:
            return self.scalar(t)
        if t == STRING:
            return self.string()
        if t == ARRAY:
            et = self.u32()
            n = self.u64()
            if n > MAX_ARRAY:
                raise GGUFError(f"array of {n} elements exceeds limit")
            if et not in _FMT and et not in (STRING, ARRAY):
                raise GGUFError(f"unknown array element type {et}")
            if n <= keep_array:
                return [self.value(et, keep_array) for _ in range(n)]
            sample = [self.value(et, keep_array) for _ in range(min(8, n))]
            rest = n - len(sample)
            if et in _FMT:
                self.skip(rest * struct.calcsize(_FMT[et]))
            elif et == STRING:
                for _ in range(rest):
                    self.skip_string()
            else:
                for _ in range(rest):
                    self.value(ARRAY, 0)
            return GGUFArray(et, n, sample)
        raise GGUFError(f"unknown metadata value type {t}")


def read_header(f: BinaryIO, *, read_tensors: bool = True, keep_array: int = 256) -> GGUFHeader:
    raw = f.read(4)
    if raw != MAGIC:
        raise GGUFError("not a GGUF file (bad magic)")
    r = _Reader(f)
    r.pos = 4
    vb = r.read(4)
    version = struct.unpack("<I", vb)[0]
    if version > 0xFFFF:  # written big-endian
        r.order = ">"
        version = struct.unpack(">I", vb)[0]
    if version not in (2, 3):
        raise GGUFError(f"unsupported GGUF version {version}")
    tensor_count, kv_count = r.u64(), r.u64()
    if kv_count > MAX_KV or tensor_count > MAX_TENSORS:
        raise GGUFError("implausible header counts")
    meta: dict[str, Any] = {}
    types: dict[str, int] = {}
    for _ in range(kv_count):
        key = r.string(limit=65535)
        t = r.u32()
        meta[key] = r.value(t, keep_array)
        types[key] = t
    hdr = GGUFHeader(version=version, tensor_count=tensor_count, kv_count=kv_count, metadata=meta,
                     types=types, byteorder=r.order)
    if read_tensors:
        tensors = []
        for _ in range(tensor_count):
            name = r.string(limit=65535)
            nd = r.u32()
            if nd > MAX_DIMS:
                raise GGUFError(f"tensor {name!r} has {nd} dimensions")
            shape = tuple(r.u64() for _ in range(nd))
            tensors.append(TensorInfo(name=name, shape=shape, type=r.u32(), offset=r.u64()))
        hdr.tensors = tensors
        align = hdr.alignment
        hdr.data_offset = r.pos + (align - r.pos % align) % align
    return hdr


def read_file(path: str | os.PathLike, **kw) -> GGUFHeader:
    with open(path, "rb", buffering=1 << 20) as f:
        return read_header(f, **kw)


def is_gguf(path: str | os.PathLike) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(4) == MAGIC
    except OSError:
        return False


# ---------------------------------------------------------------- writer (tests, tooling)

def _infer_type(v: Any) -> int:
    if isinstance(v, bool):
        return BOOL
    if isinstance(v, int):
        return UINT32 if 0 <= v < 2**32 else INT64
    if isinstance(v, float):
        return FLOAT32
    if isinstance(v, str):
        return STRING
    if isinstance(v, (list, tuple)):
        return ARRAY
    raise TypeError(f"cannot store {type(v).__name__} in GGUF")


def _pack_value(order: str, t: int, v: Any, elem_type: int | None = None) -> bytes:
    if t in _FMT:
        return struct.pack(order + _FMT[t], v)
    if t == STRING:
        b = v.encode("utf-8")
        return struct.pack(order + "Q", len(b)) + b
    if t == ARRAY:
        items = list(v)
        et = elem_type if elem_type is not None else (_infer_type(items[0]) if items else UINT32)
        out = [struct.pack(order + "IQ", et, len(items))]
        out.extend(_pack_value(order, et, x) for x in items)
        return b"".join(out)
    raise GGUFError(f"unknown type {t}")


def write_file(path: str | os.PathLike, metadata: dict[str, Any],
               tensors: Iterable[tuple[str, tuple[int, ...], int]] = (), *,
               types: dict[str, int | tuple[int, int]] | None = None, byteorder: str = "<",
               version: int = 3, fill: bytes = b"\0") -> int:
    """Write a valid GGUF file. ``tensors``: (name, shape, ggml_type); data is ``fill`` bytes.
    ``types`` forces value types: ``{"key": UINT64}`` or ``{"key": (ARRAY, INT32)}``. Returns size."""
    types = types or {}
    tensors = list(tensors)
    order = byteorder
    buf = bytearray()
    buf += MAGIC + struct.pack(order + "IQQ", version, len(tensors), len(metadata))
    for k, v in metadata.items():
        spec = types.get(k)
        et = None
        if isinstance(spec, tuple):
            t, et = spec
        else:
            t = spec if spec is not None else _infer_type(v)
        buf += _pack_value(order, STRING, k) + struct.pack(order + "I", t) + _pack_value(order, t, v, et)
    align = int(metadata.get("general.alignment", 32))
    offset = 0
    sizes = []
    for name, shape, gtype in tensors:
        ti = TensorInfo(name, tuple(shape), gtype, offset)
        nb = ti.nbytes or 0
        buf += _pack_value(order, STRING, name) + struct.pack(order + "I", len(shape))
        buf += b"".join(struct.pack(order + "Q", d) for d in shape)
        buf += struct.pack(order + "IQ", gtype, offset)
        sizes.append(nb)
        offset += nb + (align - nb % align) % align
    buf += b"\0" * ((align - len(buf) % align) % align)
    with open(path, "wb") as f:
        f.write(buf)
        for nb in sizes:
            pad = (align - nb % align) % align
            if nb:
                f.write((fill * (nb // len(fill) + 1))[:nb])
            if pad:
                f.write(b"\0" * pad)
        return f.tell()
