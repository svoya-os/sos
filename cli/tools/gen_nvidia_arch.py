#!/usr/bin/env python3
"""Regenerate ``svoya_cli/hw/nvidia_db.py:ARCH_RANGES`` from a pci.ids file.

Usage: python3 cli/tools/gen_nvidia_arch.py /usr/share/misc/pci.ids   (or github.com/pciutils/pciids)

NVIDIA allocates PCI device IDs per chip, and pci.ids names the chip for almost every entry
(``2684  AD102 [GeForce RTX 4090]``). The chip prefix gives the architecture; consecutive IDs of
the same architecture are merged into ranges.
"""
import re
import sys

PREFIX = {"GF": "fermi", "GK": "kepler", "GM": "maxwell", "GP": "pascal", "GV": "volta",
          "TU": "turing", "GA": "ampere", "GH": "hopper", "AD": "ada", "GB": "blackwell"}


def main(path: str) -> None:
    rows = []
    in_nv = False
    for line in open(path, encoding="utf-8", errors="replace"):
        if re.match(r"^[0-9a-f]{4}\s", line):
            in_nv = line.startswith("10de")
            continue
        if not in_nv:
            continue
        m = re.match(r"^\t([0-9a-f]{4})\s+(\S+)", line)
        if not m:
            continue
        cm = re.match(r"(GF|GK|GM|GP|GV|TU|GA|GH|AD|GB)\d", m.group(2))
        if cm:
            rows.append((int(m.group(1), 16), PREFIX[cm.group(1)]))
    rows.sort()
    runs: list[list] = []
    for did, arch in rows:
        if runs and runs[-1][2] == arch:
            runs[-1][1] = did
        else:
            runs.append([did, did, arch])
    print("ARCH_RANGES: tuple[tuple[int, int, str], ...] = (")
    for a, b, arch in runs:
        print(f"    (0x{a:04x}, 0x{b:04x}, {arch!r}),")
    print(")")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/usr/share/misc/pci.ids")
