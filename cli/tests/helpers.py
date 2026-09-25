"""Test sandbox: a fake system root (sysfs/procfs/etc), a fake home and a table-driven runner."""
from __future__ import annotations

import datetime as dt
import io
import os
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from svoya_cli import i18n, ui
from svoya_cli.context import Ctx
from svoya_cli.paths import Paths
from svoya_cli.runner import FakeRunner, Result

FIX = Path(__file__).resolve().parent / "fixtures"
NOW = dt.datetime(2026, 9, 24, 18, 42, tzinfo=dt.timezone.utc)
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def fixture(rel: str) -> str:
    return (FIX / rel).read_text(encoding="utf-8")


def strip_ansi(s: str) -> str:
    return ANSI.sub("", s)


class Sandbox:
    def __init__(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="sos-test-"))
        self.root = self.dir / "root"
        self.home = self.dir / "home"
        self.root.mkdir()
        self.home.mkdir()
        (self.dir / "run").mkdir()

    # ---- files in the fake root
    def path(self, p: str) -> Path:
        return self.root / p.lstrip("/")

    def write(self, p: str, content: str | bytes = "", mode: int | None = None) -> Path:
        f = self.path(p)
        f.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            f.write_bytes(content)
        else:
            f.write_text(content, encoding="utf-8")
        if mode is not None:
            os.chmod(f, mode)
        return f

    def mkdir(self, p: str) -> Path:
        d = self.path(p)
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ---- hardware
    def pci(self, slot: str, cls: int, vendor: int, device: int, driver: str | None = None,
            boot_vga: bool | None = None) -> Path:
        d = self.mkdir(f"/sys/bus/pci/devices/{slot}")
        (d / "class").write_text(f"0x{cls:04x}00\n")
        (d / "vendor").write_text(f"0x{vendor:04x}\n")
        (d / "device").write_text(f"0x{device:04x}\n")
        if driver:
            drv = self.mkdir(f"/sys/bus/pci/drivers/{driver}")
            (d / "driver").symlink_to(drv)
        if boot_vga is not None:
            (d / "boot_vga").write_text("1\n" if boot_vga else "0\n")
        return d

    def drm(self, card: str, slot: str) -> Path:
        c = self.mkdir(f"/sys/class/drm/{card}")
        (c / "device").symlink_to(self.path(f"/sys/bus/pci/devices/{slot}"))
        return c

    def amd_card(self, card: str, slot: str, device: int, *, vram_used=0, vram_total=0, busy=0, temp_mc=None,
                 power_uw=None, gtt_used=None, gtt_total=None) -> None:
        d = self.pci(slot, 0x0300, 0x1002, device, driver="amdgpu")
        (d / "mem_info_vram_used").write_text(f"{vram_used}\n")
        (d / "mem_info_vram_total").write_text(f"{vram_total}\n")
        (d / "gpu_busy_percent").write_text(f"{busy}\n")
        if gtt_total is not None:
            (d / "mem_info_gtt_total").write_text(f"{gtt_total}\n")
            (d / "mem_info_gtt_used").write_text(f"{gtt_used or 0}\n")
        hw = d / "hwmon" / "hwmon3"
        hw.mkdir(parents=True)
        if temp_mc is not None:
            (hw / "temp1_input").write_text(f"{temp_mc}\n")
        if power_uw is not None:
            (hw / "power1_average").write_text(f"{power_uw}\n")
        self.drm(card, slot)

    def kernel(self, release: str, nvidia: str | None = "prebuilt", branch: str = "595-open") -> None:
        self.write(f"/boot/vmlinuz-{release}", "")
        base = f"/lib/modules/{release}"
        self.mkdir(base)
        if nvidia == "prebuilt":
            self.write(f"{base}/kernel/nvidia-{branch}/nvidia.ko.zst", "")
        elif nvidia == "dkms":
            self.write(f"{base}/updates/dkms/nvidia.ko.zst", "")

    # ---- environment
    def env(self, **extra: str) -> dict:
        e = {"HOME": str(self.home), "SVOYA_ROOT": str(self.root), "XDG_RUNTIME_DIR": str(self.dir / "run"),
             "SVOYA_AI_ROOT": str(self.root / "srv" / "ai"), "SVOYA_VAR_LIB": str(self.root / "var/lib/svoya"),
             "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "USER": "tester"}
        e.update(extra)
        return e

    def ctx(self, runner: FakeRunner | None = None, *, now: dt.datetime = NOW, uid: int = 1000,
            dry_run: bool = False, **env_extra: str) -> Ctx:
        env = self.env(**env_extra)
        runner = runner or FakeRunner()
        runner.dry_run = dry_run
        return Ctx(paths=Paths(env=env), runner=runner, env=env, now=lambda: now, uid=uid, dry_run=dry_run)

    def cleanup(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


class SandboxTest(unittest.TestCase):
    lang = "en"

    def setUp(self) -> None:
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        i18n.set_lang(self.lang)
        self.buf = io.StringIO()
        ui.set_style(ui.Style(stream=self.buf, enabled=False))
        self.addCleanup(ui.set_style, None)

    def output(self) -> str:
        return strip_ansi(self.buf.getvalue())


def capture(fn, *a, **kw) -> tuple[object, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rv = fn(*a, **kw)
    return rv, buf.getvalue()


__all__ = ["Sandbox", "SandboxTest", "FakeRunner", "Result", "fixture", "strip_ansi", "capture", "NOW", "FIX"]
