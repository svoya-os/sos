"""PCI display devices from ``lspci -Dnnk`` (preferred) or ``/sys/bus/pci/devices`` (fallback)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

VENDORS = {0x10DE: "nvidia", 0x1002: "amd", 0x8086: "intel"}
DISPLAY_CLASSES = {0x0300, 0x0302, 0x0380}   # VGA, 3D controller, display controller


@dataclass
class PciDevice:
    slot: str                 # 0000:01:00.0
    class_code: int           # 0x0300
    vendor_id: int
    device_id: int
    description: str = ""     # "NVIDIA Corporation AD102 [GeForce RTX 4090]"
    driver: str | None = None             # kernel driver in use
    modules: list[str] = field(default_factory=list)
    boot_vga: bool | None = None

    @property
    def vendor(self) -> str:
        return VENDORS.get(self.vendor_id, "other")

    @property
    def marketing_name(self) -> str:
        """``AD102 [GeForce RTX 4090]`` → ``GeForce RTX 4090`` (last bracketed group)."""
        m = re.findall(r"\[([^\]]+)\]", self.description)
        if m:
            return m[-1]
        return re.sub(r"^(NVIDIA Corporation|Advanced Micro Devices, Inc\.|Intel Corporation)\s*", "",
                      self.description).strip()


_LINE = re.compile(
    r"^(?P<slot>(?:[0-9a-f]{4}:)?[0-9a-f]{2}:[0-9a-f]{2}\.[0-7])\s+"
    r"(?P<cls>.+?)\s+\[(?P<cc>[0-9a-f]{4})\]:\s+(?P<rest>.*)$", re.I)
_IDS = re.compile(r"\[(?P<vid>[0-9a-f]{4}):(?P<did>[0-9a-f]{4})\]", re.I)


def parse_lspci(text: str) -> list[PciDevice]:
    """Parse ``lspci -Dnnk`` (or ``-nnk``) output; returns display-class devices only."""
    devices: list[PciDevice] = []
    cur: PciDevice | None = None
    for raw in text.splitlines():
        if not raw.strip():
            continue
        if not raw[0].isspace():
            cur = None
            m = _LINE.match(raw.strip())
            if not m:
                continue
            cc = int(m.group("cc"), 16)
            ids = list(_IDS.finditer(m.group("rest")))
            if not ids:
                continue
            last = ids[-1]
            desc = m.group("rest")[: last.start()].strip()
            slot = m.group("slot").lower()
            if len(slot) == 7:          # no domain
                slot = "0000:" + slot
            dev = PciDevice(slot=slot, class_code=cc, vendor_id=int(last.group("vid"), 16),
                            device_id=int(last.group("did"), 16), description=desc)
            if cc in DISPLAY_CLASSES:
                devices.append(dev)
                cur = dev
            continue
        if cur is None:
            continue
        line = raw.strip()
        if line.startswith("Kernel driver in use:"):
            cur.driver = line.split(":", 1)[1].strip()
        elif line.startswith("Kernel modules:"):
            cur.modules = [x.strip() for x in line.split(":", 1)[1].split(",") if x.strip()]
    return devices


def _hex(path: Path) -> int | None:
    try:
        return int(path.read_text().strip(), 16)
    except (OSError, ValueError):
        return None


def scan_sysfs(pci_root: Path) -> list[PciDevice]:
    """Fallback without lspci: read class/vendor/device/driver from sysfs."""
    devices: list[PciDevice] = []
    try:
        entries = sorted(pci_root.iterdir())
    except OSError:
        return devices
    for d in entries:
        cls = _hex(d / "class")
        if cls is None or (cls >> 8) not in DISPLAY_CLASSES:
            continue
        vid, did = _hex(d / "vendor"), _hex(d / "device")
        if vid is None or did is None:
            continue
        drv = None
        try:
            drv = (d / "driver").resolve().name if (d / "driver").exists() else None
        except OSError:
            pass
        devices.append(PciDevice(slot=d.name, class_code=cls >> 8, vendor_id=vid, device_id=did,
                                 driver=drv))
    return devices


def add_sysfs_details(devices: list[PciDevice], pci_root: Path) -> None:
    """boot_vga (which GPU the firmware lit the screen with) and driver fallback."""
    for dev in devices:
        base = pci_root / dev.slot
        try:
            dev.boot_vga = (base / "boot_vga").read_text().strip() == "1"
        except OSError:
            dev.boot_vga = None
        if dev.driver is None and (base / "driver").exists():
            try:
                dev.driver = (base / "driver").resolve().name
            except OSError:
                pass


def drm_cards(drm_root: Path) -> dict[str, str]:
    """PCI slot → DRM card name (``card1``) from ``/sys/class/drm/card*/device``."""
    out: dict[str, str] = {}
    try:
        for c in drm_root.iterdir():
            if not re.fullmatch(r"card\d+", c.name):
                continue
            try:
                out[(c / "device").resolve().name] = c.name
            except OSError:
                continue
    except OSError:
        pass
    return out
