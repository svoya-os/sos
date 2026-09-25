#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Write the GPU driver metadata of the ISO pool (pool/svoya-gpu.json).

    pool_meta.py OUT.json BRANCH:COMPONENT:METAPKG:APT_CACHE_SHOW_FILE:PKG[,PKG...] ...

APT_CACHE_SHOW_FILE is the output of `apt-cache show --no-all-versions METAPKG`; its Modaliases
field (e.g. "nvidia(pci:v000010DEd00002684sv*sd*bc03sc*i*, ...)") tells which PCI devices the branch
supports. The installer (installer/scripts/gpu_select.py) matches the machine's modaliases against
these patterns, in list order (= preference).
"""
from __future__ import annotations

import json
import re
import sys

PATTERN_RE = re.compile(r"pci:[^,()\s]+")


def parse_show(text: str) -> dict[str, str]:
    """First paragraph of apt-cache show output as a dict (continuation lines joined)."""
    fields: dict[str, str] = {}
    last = None
    for line in text.splitlines():
        if not line.strip():
            if fields:
                break
            continue
        if line[0] in " \t" and last:
            fields[last] += " " + line.strip()
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            last = key.strip()
            fields[last] = value.strip()
    return fields


def modaliases(field: str) -> list[str]:
    return PATTERN_RE.findall(field or "")


def upstream_version(version: str) -> str:
    v = version.split(":", 1)[-1]
    return v.split("-", 1)[0]


def build(specs: list[str]) -> dict:
    branches = []
    for spec in specs:
        branch, component, meta, show_file, pkgs = spec.split(":", 4)
        with open(show_file, encoding="utf-8") as fh:
            fields = parse_show(fh.read())
        pats = modaliases(fields.get("Modaliases", ""))
        if not pats:
            raise SystemExit(f"pool_meta: {meta} has no Modaliases; cannot map devices to {branch}")
        branches.append({
            "id": branch,
            "component": component,
            "metapackage": meta,
            "version": fields.get("Version", ""),
            "driver": upstream_version(fields.get("Version", "")),
            "packages": [p for p in pkgs.split(",") if p],
            "modaliases": pats,
        })
    return {"schema": 1, "vendor": "nvidia", "branches": branches}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    data = build(argv[2:])
    with open(argv[1], "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
        fh.write("\n")
    for b in data["branches"]:
        print(f"{b['id']}: driver {b['driver']}, {len(b['modaliases'])} device patterns", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
