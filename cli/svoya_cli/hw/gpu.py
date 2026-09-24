"""GPU inventory (what is installed) and live stats (what it is doing right now).

Live stats feed ``svoya status`` (polled every 2 s), so they avoid slow probes:
NVIDIA → one ``nvidia-smi --query-gpu`` call; AMD → sysfs reads only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import amd_db, nvidia_db
from .pci import PciDevice, add_sysfs_details, drm_cards, parse_lspci, scan_sysfs

NVSMI_FIELDS = "index,name,temperature.gpu,memory.used,memory.total,utilization.gpu,power.draw,driver_version"
NVSMI_ARGV = ["nvidia-smi", f"--query-gpu={NVSMI_FIELDS}", "--format=csv,noheader,nounits"]


def short_name(name: str) -> str:
    """``NVIDIA GeForce RTX 4090`` → ``RTX 4090``; ``AMD Radeon RX 7900 XTX`` → ``RX 7900 XTX``."""
    n = re.sub(r"^(NVIDIA|AMD|ATI|Intel\(R\)|Intel)\s+", "", name.strip())
    n = re.sub(r"^(GeForce|Radeon(?=\s+RX)|Radeon\s+Pro(?=\s))\s*", "", n)
    return n.strip() or name


def _num(s: str) -> float | None:
    s = s.strip()
    if not s or s.startswith("[") or s.upper() in ("N/A", "NA"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_nvidia_smi(text: str) -> list[dict]:
    gpus: list[dict] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        f = [x.strip() for x in line.split(",")]
        if len(f) < 8:
            continue
        # a name could contain a comma in theory: rejoin the middle
        if len(f) > 8:
            f = [f[0], ",".join(f[1:len(f) - 6])] + f[len(f) - 6:]
        idx = _num(f[0])
        g: dict = {"index": int(idx) if idx is not None else len(gpus), "vendor": "nvidia",
                   "name": short_name(f[1])}
        for key, val in (("tempC", f[2]), ("vramUsedMiB", f[3]), ("vramTotalMiB", f[4]),
                         ("util", f[5]), ("powerW", f[6])):
            v = _num(val)
            if v is not None:
                g[key] = int(round(v))
        if f[7] and not f[7].startswith("["):
            g["driver"] = f[7]
        gpus.append(g)
    return gpus


def nvidia_stats(ctx, timeout: float = 2.0) -> list[dict] | None:
    """None when there is no working nvidia-smi (no NVIDIA GPU or driver not loaded)."""
    if not ctx.runner.which("nvidia-smi"):
        return None
    r = ctx.runner.run(NVSMI_ARGV, timeout=timeout)
    if not r.ok:
        return None
    return parse_nvidia_smi(r.out)


def _read_int(p: Path) -> int | None:
    try:
        return int(p.read_text().strip())
    except (OSError, ValueError):
        return None


def amd_stats(ctx) -> list[dict]:
    drm = ctx.sys("/sys/class/drm")
    out: list[dict] = []
    try:
        cards = sorted((c for c in drm.iterdir() if re.fullmatch(r"card\d+", c.name)),
                       key=lambda c: int(c.name[4:]))
    except OSError:
        return out
    for card in cards:
        dev = card / "device"
        try:
            if (dev / "vendor").read_text().strip().lower() != "0x1002":
                continue
            did = int((dev / "device").read_text().strip(), 16)
        except (OSError, ValueError):
            continue
        g: dict = {"vendor": "amd", "name": short_name(amd_db.name_for(did) or "Radeon GPU"), "card": card.name}
        used, total = _read_int(dev / "mem_info_vram_used"), _read_int(dev / "mem_info_vram_total")
        if used is not None:
            g["vramUsedMiB"] = used // 2**20
        if total is not None:
            g["vramTotalMiB"] = total // 2**20
        busy = _read_int(dev / "gpu_busy_percent")
        if busy is not None:
            g["util"] = busy
        for hw in sorted((dev / "hwmon").glob("hwmon*")) if (dev / "hwmon").is_dir() else []:
            t = _read_int(hw / "temp1_input")
            if t is not None and "tempC" not in g:
                g["tempC"] = int(round(t / 1000))
            for pname in ("power1_average", "power1_input"):
                p = _read_int(hw / pname)
                if p is not None and "powerW" not in g:
                    g["powerW"] = int(round(p / 1e6))
        apu = amd_db.is_apu(did)
        gtt_used, gtt_total = _read_int(dev / "mem_info_gtt_used"), _read_int(dev / "mem_info_gtt_total")
        if apu is None:
            apu = bool(total is not None and total <= 4 * 2**30 and gtt_total and gtt_total > (total or 0))
        if apu:
            g["integrated"] = True
            if gtt_total is not None:
                g["gttTotalMiB"] = gtt_total // 2**20
            if gtt_used is not None:
                g["gttUsedMiB"] = gtt_used // 2**20
        g["driver"] = "amdgpu"
        out.append(g)
    return out


def live_stats(ctx) -> list[dict]:
    """GPU list for ``svoya status``: NVIDIA (nvidia-smi order) then AMD (card order)."""
    gpus = list(nvidia_stats(ctx) or [])
    for g in amd_stats(ctx):
        g["index"] = len(gpus)
        gpus.append(g)
    return gpus


# ---------------------------------------------------------------- inventory (doctor, fit, new)

@dataclass
class GpuInfo:
    pci: PciDevice
    vendor: str
    name: str
    arch: str | None = None          # NVIDIA architecture id (nvidia_db.ARCH)
    gfx: str | None = None           # AMD LLVM target
    integrated: bool = False
    drm_card: str | None = None
    discrete_intel: bool = False

    @property
    def arch_info(self):
        return nvidia_db.info(self.arch) if self.vendor == "nvidia" else None


def inventory(ctx) -> list[GpuInfo]:
    pci_root = ctx.sys("/sys/bus/pci/devices")
    devices: list[PciDevice] = []
    if ctx.runner.which("lspci"):
        r = ctx.runner.run(["lspci", "-Dnnk"], timeout=5)
        if r.ok:
            devices = parse_lspci(r.out)
    if not devices:
        devices = scan_sysfs(pci_root)
    add_sysfs_details(devices, pci_root)
    cards = drm_cards(ctx.sys("/sys/class/drm"))
    kfd = amd_db.kfd_targets(ctx.sys("/sys/class/kfd/kfd/topology/nodes"))
    out: list[GpuInfo] = []
    amd_seen = 0
    for d in devices:
        g = GpuInfo(pci=d, vendor=d.vendor, name=d.marketing_name, drm_card=cards.get(d.slot))
        if d.vendor == "nvidia":
            g.arch = nvidia_db.arch_for(d.device_id, d.description)
            g.name = nvidia_db.KNOWN.get(d.device_id) or d.marketing_name
        elif d.vendor == "amd":
            g.gfx = amd_db.gfx_for(d.device_id)
            if g.gfx is None and amd_seen < len(kfd):
                g.gfx = kfd[amd_seen]
            amd_seen += 1
            g.name = amd_db.name_for(d.device_id) or d.marketing_name
            g.integrated = bool(amd_db.is_apu(d.device_id))
        elif d.vendor == "intel":
            g.discrete_intel = amd_db.intel_is_discrete(d.device_id)
            g.integrated = not g.discrete_intel
        out.append(g)
    return out


def primary_compute(gpus: list[GpuInfo]) -> GpuInfo | None:
    """The GPU AI work should run on: NVIDIA dGPU > AMD dGPU > Strix Halo/AMD APU > Intel Arc."""
    def rank(g: GpuInfo) -> tuple:
        if g.vendor == "nvidia":
            info = g.arch_info
            return (0, -(info.order if info else 0))
        if g.vendor == "amd" and not g.integrated:
            return (1, 0)
        if g.vendor == "amd":
            return (2, 0 if g.gfx == amd_db.STRIX_HALO else 1)
        if g.vendor == "intel" and g.discrete_intel:
            return (3, 0)
        return (9, 0)
    ranked = sorted(gpus, key=rank)
    return ranked[0] if ranked and rank(ranked[0])[0] < 9 else None


def torch_backend(g: GpuInfo | None, rocm_backend: str = "rocm7.2") -> str:
    """PyTorch wheel backend for UV_TORCH_BACKEND (cu130 · cu126 · rocmX.Y · xpu · cpu)."""
    if g is None:
        return "cpu"
    if g.vendor == "nvidia":
        info = g.arch_info
        return info.torch if info else "cu130"
    if g.vendor == "amd":
        if g.gfx in amd_db.ROCM_SUPPORTED or g.gfx in amd_db.HSA_OVERRIDE:
            return rocm_backend
        return "cpu"
    if g.vendor == "intel" and g.discrete_intel:
        return "xpu"
    return "cpu"
