"""AMD and Intel GPU knowledge: PCI device → LLVM gfx target, ROCm support, APU flags.

ROCm 7.1 is in the engine archive. Officially supported here: RDNA3 gfx1100–1102, RDNA4
gfx1200/1201, Strix Halo gfx1151 (needs a larger GTT → kernel parameters), Instinct gfx90a/942/950,
RDNA2 gfx1030. Everything else gets Vulkan (llama.cpp's Vulkan backend works on all vendors).
The authoritative gfx target is read from KFD topology when the driver is loaded.
"""
from __future__ import annotations

import re
from pathlib import Path

# device id → (gfx target, marketing name, is_apu)   (pci.ids, 2026-09)
AMD_DEVICES: dict[int, tuple[str, str, bool]] = {
    # RDNA4
    0x7550: ("gfx1201", "Radeon RX 9070 / 9070 XT", False),
    0x7551: ("gfx1201", "Radeon AI PRO R9700", False),
    0x7590: ("gfx1200", "Radeon RX 9060 XT", False),
    # RDNA3
    0x744c: ("gfx1100", "Radeon RX 7900 XTX / XT / GRE", False),
    0x7448: ("gfx1100", "Radeon Pro W7900", False),
    0x7449: ("gfx1100", "Radeon Pro W7800 48GB", False),
    0x744a: ("gfx1100", "Radeon Pro W7900 Dual Slot", False),
    0x745e: ("gfx1100", "Radeon Pro W7800", False),
    0x747e: ("gfx1101", "Radeon RX 7800 XT / 7700 XT", False),
    0x7470: ("gfx1101", "Radeon PRO W7700", False),
    0x7460: ("gfx1101", "Radeon PRO V710", False),
    0x7461: ("gfx1101", "Radeon PRO V710", False),
    0x7480: ("gfx1102", "Radeon RX 7600 / 7600 XT", False),
    0x7483: ("gfx1102", "Radeon RX 7600M", False),
    0x7489: ("gfx1102", "Radeon Pro W7500", False),
    0x7499: ("gfx1102", "Radeon RX 7400 / 7300", False),
    0x73f0: ("gfx1102", "Radeon RX 7600M XT", False),
    # RDNA2
    0x73bf: ("gfx1030", "Radeon RX 6800 / 6800 XT / 6900 XT", False),
    0x73af: ("gfx1030", "Radeon RX 6900 XT", False),
    0x73a5: ("gfx1030", "Radeon RX 6950 XT", False),
    0x73a3: ("gfx1030", "Radeon PRO W6800", False),
    0x73df: ("gfx1031", "Radeon RX 6700 / 6700 XT / 6750 XT", False),
    0x73ff: ("gfx1032", "Radeon RX 6600 / 6600 XT", False),
    0x73ef: ("gfx1032", "Radeon RX 6650 XT", False),
    0x743f: ("gfx1034", "Radeon RX 6400 / 6500 XT", False),
    # APUs
    0x1586: ("gfx1151", "Radeon 8060S (Strix Halo)", True),
    0x150e: ("gfx1150", "Radeon 890M (Strix Point)", True),
    0x1114: ("gfx1152", "Radeon 860M (Krackan)", True),
    0x15bf: ("gfx1103", "Radeon 780M (Phoenix)", True),
    0x15c8: ("gfx1103", "Radeon 740M (Phoenix2)", True),
    0x164f: ("gfx1103", "Radeon 780M (Phoenix)", True),
    0x1900: ("gfx1103", "Radeon 780M (Hawk Point)", True),
    0x1901: ("gfx1103", "Radeon 760M (Hawk Point)", True),
    0x1681: ("gfx1035", "Radeon 680M (Rembrandt)", True),
    # Instinct
    0x74a1: ("gfx942", "Instinct MI300X", False),
    0x74a0: ("gfx942", "Instinct MI300A", True),
    0x74a5: ("gfx942", "Instinct MI325X", False),
    0x75a0: ("gfx950", "Instinct MI350X", False),
    0x75a3: ("gfx950", "Instinct MI355X", False),
    0x740f: ("gfx90a", "Instinct MI210", False),
    0x740c: ("gfx90a", "Instinct MI250X / MI250", False),
    0x738c: ("gfx908", "Instinct MI100", False),
}

ROCM_SUPPORTED = frozenset({"gfx1100", "gfx1101", "gfx1102", "gfx1200", "gfx1201", "gfx1151",
                            "gfx1030", "gfx90a", "gfx942", "gfx950", "gfx908"})
# Community workaround (unsupported by AMD): pretend to be a close, supported ISA.
HSA_OVERRIDE = {"gfx1031": "10.3.0", "gfx1032": "10.3.0", "gfx1034": "10.3.0", "gfx1035": "10.3.0",
                "gfx1103": "11.0.0"}
STRIX_HALO = "gfx1151"


def gfx_for(device_id: int | None) -> str | None:
    if device_id is None:
        return None
    hit = AMD_DEVICES.get(device_id)
    return hit[0] if hit else None


def name_for(device_id: int | None) -> str | None:
    hit = AMD_DEVICES.get(device_id or -1)
    return hit[1] if hit else None


def is_apu(device_id: int | None) -> bool | None:
    hit = AMD_DEVICES.get(device_id or -1)
    return hit[2] if hit else None


def gfx_from_target_version(v: int) -> str:
    """KFD ``gfx_target_version`` (major*10000 + minor*100 + stepping) → ``gfx1151``/``gfx90a``."""
    major, rest = divmod(int(v), 10000)
    minor, step = divmod(rest, 100)
    return f"gfx{major}{minor:x}{step:x}"


def kfd_targets(topology_nodes: Path) -> list[str]:
    """Parse ``/sys/class/kfd/kfd/topology/nodes/*/properties`` (CPU nodes report 0)."""
    out: list[str] = []
    try:
        nodes = sorted(topology_nodes.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 0)
    except OSError:
        return out
    for node in nodes:
        try:
            text = (node / "properties").read_text()
        except OSError:
            continue
        m = re.search(r"^gfx_target_version\s+(\d+)", text, re.M)
        if m and int(m.group(1)) > 0:
            out.append(gfx_from_target_version(int(m.group(1))))
    return out


# ---------------------------------------------------------------- Intel
INTEL_DISCRETE_PREFIXES = (0x56, 0xE2)   # Arc Alchemist (DG2) 0x56xx, Battlemage 0xE2xx


def intel_is_discrete(device_id: int | None) -> bool:
    return device_id is not None and (device_id >> 8) in INTEL_DISCRETE_PREFIXES
