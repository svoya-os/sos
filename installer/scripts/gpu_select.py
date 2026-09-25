#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Pick the NVIDIA driver branch for this machine from the medium's pool metadata.

    gpu_select.py --json /media/sos-medium/pool/svoya-gpu.json [--sysfs /sys] [--format shell|json]

Reads the PCI display devices from sysfs, keeps NVIDIA ones (vendor 0x10de, class 0x03xxxx) and
matches their modaliases against each branch's Modaliases patterns (from the nvidia-driver-*
metapackages, the same data ubuntu-drivers uses), in the order of the JSON (= preference).
Shell output (for eval): SOS_GPU_DEVICES, SOS_GPU_BRANCH, SOS_GPU_COMPONENT, SOS_GPU_PACKAGES,
SOS_GPU_DRIVER. An empty SOS_GPU_BRANCH with devices present means "no offline driver fits".
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import pathlib
import shlex
import sys

NVIDIA = "0x10de"


def nvidia_devices(sysfs: pathlib.Path) -> list[dict[str, str]]:
    devices = []
    base = sysfs / "bus" / "pci" / "devices"
    if not base.is_dir():
        return devices
    for dev in sorted(base.iterdir()):
        try:
            vendor = (dev / "vendor").read_text().strip().lower()
            klass = (dev / "class").read_text().strip().lower()
            alias = (dev / "modalias").read_text().strip()
        except OSError:
            continue
        if vendor == NVIDIA and klass.startswith("0x03"):
            devices.append({"slot": dev.name, "modalias": alias})
    return devices


def select(meta: dict, aliases: list[str]) -> dict | None:
    for branch in meta.get("branches", []):
        for pattern in branch.get("modaliases", []):
            if any(fnmatch.fnmatchcase(a, pattern) for a in aliases):
                return branch
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", required=True, type=pathlib.Path)
    ap.add_argument("--sysfs", default="/sys", type=pathlib.Path)
    ap.add_argument("--format", choices=("shell", "json"), default="shell")
    ns = ap.parse_args(argv)

    devices = nvidia_devices(ns.sysfs)
    meta = {"branches": []}
    if ns.json.is_file():
        meta = json.loads(ns.json.read_text(encoding="utf-8"))
    branch = select(meta, [d["modalias"] for d in devices]) if devices else None
    result = {
        "devices": devices,
        "branch": branch["id"] if branch else "",
        "component": branch["component"] if branch else "",
        "packages": branch["packages"] if branch else [],
        "driver": branch.get("driver", "") if branch else "",
    }
    if ns.format == "json":
        print(json.dumps(result, indent=1))
    else:
        print(f"SOS_GPU_DEVICES={shlex.quote(' '.join(d['slot'] for d in devices))}")
        print(f"SOS_GPU_BRANCH={shlex.quote(result['branch'])}")
        print(f"SOS_GPU_COMPONENT={shlex.quote(result['component'])}")
        print(f"SOS_GPU_PACKAGES={shlex.quote(' '.join(result['packages']))}")
        print(f"SOS_GPU_DRIVER={shlex.quote(result['driver'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
