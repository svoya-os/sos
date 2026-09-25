# SPDX-License-Identifier: Apache-2.0
"""PPM parsing, PNG encoding and screen heuristics."""
from __future__ import annotations

import io
import pathlib
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import image  # noqa: E402


def ppm_p6(w: int, h: int, pixels: bytes, maxval: int = 255, comment: bool = False) -> bytes:
    head = b"P6\n" + (b"# written by QEMU\n" if comment else b"") + f"{w} {h}\n{maxval}\n".encode()
    return head + pixels


class PPMTests(unittest.TestCase):
    def test_p6_basic(self):
        img = image.parse_ppm(ppm_p6(2, 1, bytes([255, 0, 0, 0, 0, 255])))
        self.assertEqual((img.width, img.height), (2, 1))
        self.assertEqual(img.pixel(0, 0), (255, 0, 0))
        self.assertEqual(img.pixel(1, 0), (0, 0, 255))

    def test_p6_with_comment(self):
        img = image.parse_ppm(ppm_p6(1, 1, bytes([1, 2, 3]), comment=True))
        self.assertEqual(img.pixel(0, 0), (1, 2, 3))

    def test_p6_binary_data_starting_with_whitespace_byte(self):
        # The first sample is 0x0a ("\n"): only one whitespace byte after maxval belongs to the header.
        img = image.parse_ppm(ppm_p6(1, 1, bytes([10, 32, 9])))
        self.assertEqual(img.pixel(0, 0), (10, 32, 9))

    def test_p6_16bit_is_scaled(self):
        data = ppm_p6(1, 1, struct.pack(">3H", 65535, 0, 32768), maxval=65535)
        self.assertEqual(image.parse_ppm(data).pixel(0, 0), (255, 0, 127))

    def test_p6_low_maxval_is_scaled(self):
        self.assertEqual(image.parse_ppm(ppm_p6(1, 1, bytes([15, 0, 7]), maxval=15)).pixel(0, 0), (255, 0, 119))

    def test_p3_ascii(self):
        img = image.parse_ppm(b"P3\n2 1\n255\n255 0 0  0 255 0\n")
        self.assertEqual(img.pixel(1, 0), (0, 255, 0))

    def test_truncated_and_bad_magic(self):
        with self.assertRaises(ValueError):
            image.parse_ppm(ppm_p6(2, 2, bytes(5)))
        with self.assertRaises(ValueError):
            image.parse_ppm(b"P5\n1 1\n255\n\x00")


class PNGTests(unittest.TestCase):
    def sample(self) -> image.Image:
        w, h = 7, 3
        rgb = b"".join(bytes(t) for t in ((x * 30 % 256, y * 80 % 256, (x + y) * 20 % 256)
                                           for y in range(h) for x in range(w)))
        return image.Image(w, h, rgb)

    def test_stdlib_encoder_structure(self):
        png = image.encode_png(self.sample())
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        # IHDR: width, height, bit depth 8, colour type 2 (RGB)
        w, h, depth, ctype = struct.unpack(">IIBB", png[16:26])
        self.assertEqual((w, h, depth, ctype), (7, 3, 8, 2))
        # decompress IDAT and compare with the pixels
        idat_len = struct.unpack(">I", png[33:37])[0]
        raw = zlib.decompress(png[41:41 + idat_len])
        self.assertEqual(len(raw), 3 * (1 + 7 * 3))
        self.assertTrue(png.endswith(b"IEND\xaeB`\x82"))

    def test_stdlib_encoder_roundtrip_with_pillow(self):
        try:
            from PIL import Image as PILImage
        except ImportError:
            self.skipTest("Pillow not installed")
        img = self.sample()
        decoded = PILImage.open(io.BytesIO(image.encode_png(img))).convert("RGB")
        self.assertEqual(decoded.tobytes(), img.rgb)

    def test_write_png_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp, "s.png")
            how = image.write_png(self.sample(), str(path))
            self.assertIn(how, ("pillow", "stdlib"))
            self.assertTrue(path.read_bytes().startswith(b"\x89PNG"))


class HeuristicTests(unittest.TestCase):
    def test_blank_and_content(self):
        black = image.Image(100, 100, bytes(100 * 100 * 3))
        self.assertTrue(image.is_blank(black))
        rgb = bytearray(black.rgb)
        for i in range(0, len(rgb) // 3, 3):  # a third of the pixels amber
            rgb[i * 3:i * 3 + 3] = bytes([255, 181, 71])
        self.assertFalse(image.is_blank(image.Image(100, 100, bytes(rgb))))

    def test_difference(self):
        a = image.Image(10, 10, bytes(300))
        b = image.Image(10, 10, bytes([255]) * 300)
        self.assertEqual(image.difference(a, a), 0.0)
        self.assertEqual(image.difference(a, b), 1.0)
        self.assertEqual(image.difference(a, image.Image(5, 5, bytes(75))), 1.0)

    def test_digest_changes_with_content(self):
        self.assertNotEqual(image.Image(1, 1, b"\0\0\0").digest(), image.Image(1, 1, b"\0\0\1").digest())


if __name__ == "__main__":
    unittest.main()
