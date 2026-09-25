#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Find firmware boot entries that grub-install created for Canonical's shim ("ubuntu").

    efibootmgr -v | efi_entries.py --partuuid PARTUUID [--label ubuntu] [--loader '\\EFI\\ubuntu\\shimx64.efi']

Prints the boot numbers (e.g. 0003) of entries with that label, on that EFI partition, starting that
loader; after-bootloader.sh deletes them once the "SOS" entry exists. Entries of other disks or
other systems are never touched.
"""
from __future__ import annotations

import argparse
import re
import sys

ENTRY_RE = re.compile(r"^Boot([0-9A-Fa-f]{4})(\*?)\s+(.*)$")


def parse(text: str) -> list[dict[str, str]]:
    entries = []
    for line in text.splitlines():
        m = ENTRY_RE.match(line.strip())
        if not m:
            continue
        rest = m.group(3)
        if "\t" in rest:
            label, path = rest.split("\t", 1)
        else:  # older efibootmgr: label and device path separated by spaces
            parts = re.split(r"\s+(?=(?:HD|PciRoot|VenHw|BBS|FvVol|MemoryMapped)\()", rest, maxsplit=1)
            label, path = (parts[0], parts[1]) if len(parts) == 2 else (rest, "")
        entries.append({"num": m.group(1).upper(), "label": label.strip(), "path": path.strip()})
    return entries


def matching(entries: list[dict[str, str]], partuuid: str, label: str, loader: str) -> list[str]:
    out = []
    for e in entries:
        path = e["path"].lower()
        if e["label"].lower() != label.lower():
            continue
        if partuuid.lower() not in path:
            continue
        if loader.lower().replace("/", "\\") not in path.replace("/", "\\"):
            continue
        out.append(e["num"])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--partuuid", required=True)
    ap.add_argument("--label", default="ubuntu")
    ap.add_argument("--loader", default="\\EFI\\ubuntu\\shimx64.efi")
    ns = ap.parse_args(argv)
    for num in matching(parse(sys.stdin.read()), ns.partuuid, ns.label, ns.loader):
        print(num)
    return 0


if __name__ == "__main__":
    sys.exit(main())
