# SPDX-License-Identifier: Apache-2.0
"""Screenshots: parse the PPM files QEMU's screendump writes, write PNG (Pillow if present,
otherwise a small stdlib encoder), and answer simple questions (is it blank? did it change?)."""
from __future__ import annotations

import hashlib
import struct
import zlib
from collections import Counter
from dataclasses import dataclass


@dataclass
class Image:
    width: int
    height: int
    rgb: bytes  # width * height * 3 bytes, row-major

    def pixel(self, x: int, y: int) -> tuple[int, int, int]:
        i = (y * self.width + x) * 3
        return self.rgb[i], self.rgb[i + 1], self.rgb[i + 2]

    def digest(self) -> str:
        return hashlib.sha256(self.rgb).hexdigest()


def _tokens(data: bytes, count: int) -> tuple[list[bytes], int]:
    """Read `count` whitespace-separated header tokens (skipping # comments); return end offset."""
    out: list[bytes] = []
    i, n = 0, len(data)
    while len(out) < count:
        while i < n and data[i:i + 1].isspace():
            i += 1
        if i < n and data[i:i + 1] == b"#":
            while i < n and data[i:i + 1] not in (b"\n", b"\r"):
                i += 1
            continue
        start = i
        while i < n and not data[i:i + 1].isspace() and data[i:i + 1] != b"#":
            i += 1
        if start == i:
            raise ValueError("truncated PPM header")
        out.append(data[start:i])
    return out, i


def parse_ppm(data: bytes) -> Image:
    """P6 (binary) and P3 (ASCII) PPM; maxval up to 65535 is scaled to 8 bits."""
    (magic, w, h, maxval), end = _tokens(data, 4)
    width, height, maxv = int(w), int(h), int(maxval)
    if width <= 0 or height <= 0 or not 0 < maxv < 65536:
        raise ValueError("bad PPM dimensions or maxval")
    count = width * height * 3
    if magic == b"P6":
        body = data[end + 1:]  # exactly one whitespace byte after maxval
        if maxv < 256:
            if len(body) < count:
                raise ValueError("truncated PPM data")
            samples = body[:count]
            if maxv != 255:
                samples = bytes(s * 255 // maxv for s in samples)
        else:
            if len(body) < count * 2:
                raise ValueError("truncated PPM data")
            vals = struct.unpack(f">{count}H", body[:count * 2])
            samples = bytes(v * 255 // maxv for v in vals)
    elif magic == b"P3":
        vals = [int(t) for t in data[end:].split()[:count]]
        if len(vals) < count:
            raise ValueError("truncated PPM data")
        samples = bytes(v * 255 // maxv for v in vals)
    else:
        raise ValueError(f"not a PPM file (magic {magic!r})")
    return Image(width, height, samples)


def encode_png(img: Image) -> bytes:
    """Stdlib PNG encoder (8-bit RGB, filter 0)."""
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))
    stride = img.width * 3
    raw = b"".join(b"\x00" + img.rgb[y * stride:(y + 1) * stride] for y in range(img.height))
    ihdr = struct.pack(">IIBBBBB", img.width, img.height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 6))
            + chunk(b"IEND", b""))


def write_png(img: Image, path: str) -> str:
    """Write PNG with Pillow when available (better compression), else with encode_png."""
    try:
        from PIL import Image as PILImage  # type: ignore
    except ImportError:
        with open(path, "wb") as fh:
            fh.write(encode_png(img))
        return "stdlib"
    PILImage.frombytes("RGB", (img.width, img.height), img.rgb).save(path, optimize=True)
    return "pillow"


def dominant_fraction(img: Image, step: int = 7) -> float:
    """Share of sampled pixels that have the most common colour (1.0 = uniform screen)."""
    counts: Counter[bytes] = Counter()
    stride = 3 * step
    for i in range(0, len(img.rgb) - 2, stride):
        counts[img.rgb[i:i + 3]] += 1
    total = sum(counts.values())
    return counts.most_common(1)[0][1] / total if total else 1.0


def is_blank(img: Image, threshold: float = 0.995) -> bool:
    return dominant_fraction(img) >= threshold


def difference(a: Image, b: Image, step: int = 5) -> float:
    """Fraction of sampled pixels that differ (0.0 = identical); 1.0 if sizes differ."""
    if (a.width, a.height) != (b.width, b.height):
        return 1.0
    stride = 3 * step
    diff = total = 0
    for i in range(0, len(a.rgb) - 2, stride):
        total += 1
        if a.rgb[i:i + 3] != b.rgb[i:i + 3]:
            diff += 1
    return diff / total if total else 0.0
