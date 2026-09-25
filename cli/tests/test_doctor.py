import argparse
import json

from svoya_cli.doctor import checks as C
from svoya_cli.doctor import cli as doctor_cli
from svoya_cli.doctor.facts import gather, mount_for, parse_modprobe
from svoya_cli.runner import Result

from .helpers import FakeRunner, SandboxTest, capture, fixture

SB_ON = b"\x06\x00\x00\x00\x01"
SB_OFF = b"\x06\x00\x00\x00\x00"
KERNEL = "6.17.0-9-generic"
MOUNTS = "/dev/nvme0n1p2 / btrfs rw,subvol=/@ 0 0\n/dev/nvme0n1p2 /srv/ai btrfs rw,subvol=/@ai 0 0\n"


class DoctorBase(SandboxTest):
    def runner(self, lspci: str, groups: str = "tester render video ai", enabled: bool = True, extra: dict | None = None):
        states = "enabled\nenabled\nenabled\nenabled\ndisabled\n" if enabled else "disabled\ndisabled\ndisabled\ndisabled\ndisabled\n"
        table = {"lspci -Dnnk": fixture(f"lspci/{lspci}"), "systemctl is-enabled": Result(1 if not enabled else 0, states),
                 "id -Gn": groups + "\n", "nvidia-ctk --version": "NVIDIA Container Toolkit CLI version 1.18.0\n",
                 "nvidia-ctk cdi list": "INFO Found 2 CDI devices\nnvidia.com/gpu=0\nnvidia.com/gpu=all\n",
                 "snapper --utc --jsonout": fixture("snapper/list.json")}
        table.update(extra or {})
        return FakeRunner(table, available={"lspci", "systemctl", "nvidia-ctk", "podman", "uv", "snapper"})

    def base_system(self, *, kernel=KERNEL, mounts=MOUNTS, swaps="/dev/zram0 partition 8388604 0 100\n"):
        sb = self.sb
        sb.write("/proc/sys/kernel/osrelease", kernel + "\n")
        sb.write("/proc/mounts", mounts)
        sb.write("/proc/swaps", "Filename Type Size Used Priority\n" + swaps)
        sb.write("/proc/meminfo", "MemTotal:       65536000 kB\nMemAvailable:   50000000 kB\n")
        sb.write("/proc/cmdline", "BOOT_IMAGE=/vmlinuz root=UUID=x ro quiet splash\n")
        sb.kernel(kernel)

    def healthy_nvidia(self, *, open_=True):
        sb = self.sb
        self.base_system()
        sb.pci("0000:00:02.0", 0x0300, 0x8086, 0xA780, driver="i915", boot_vga=True)
        sb.pci("0000:01:00.0", 0x0300, 0x10DE, 0x2684, driver="nvidia", boot_vga=False)
        sb.mkdir("/sys/module/nvidia")
        sb.write("/sys/module/nvidia/taint", "O\n")
        sb.write("/proc/driver/nvidia/version", fixture("proc/nvidia-version-open.txt" if open_ else "proc/nvidia-version-proprietary.txt"))
        sb.write("/proc/driver/nvidia/params", fixture("proc/nvidia-params.txt"))
        sb.write("/sys/module/nvidia_drm/parameters/modeset", "Y\n")
        sb.mkdir("/sys/module/nvidia_uvm")
        sb.write("/dev/nvidia-uvm", "")
        sb.write("/etc/modprobe.d/svoya-nvidia.conf", C.modprobe_conf(type("F", (), {"nv_open": open_})()))
        sb.write("/usr/lib/systemd/system-sleep/svoya-nvidia-uvm", "#!/bin/sh\n")
        sb.write("/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-e0c16a4c8f68", SB_ON)
        sb.write("/usr/share/vulkan/icd.d/nvidia_icd.json", "{}")
        sb.write("/var/run/cdi/nvidia.yaml", "cdiVersion: 0.8.0\n")
        sb.mkdir("/srv/ai")
        sb.write("/etc/snapper/configs/root", "")

    def run_checks(self, runner, **env):
        ctx = self.sb.ctx(runner, **env)
        facts = gather(ctx)
        if facts.srv_ai and facts.srv_ai.get("group") not in (None, "root"):
            facts.srv_ai["group"] = "ai"   # the sandbox dir belongs to the CI user; on SOS /srv/ai is group "ai"
        return {c.id: c for c in C.run_all(facts, hook_source="#!/bin/sh\n", user_env_path="/u/env.conf")}, facts, ctx


class HealthyNvidiaTest(DoctorBase):
    def test_everything_ok(self):
        self.healthy_nvidia()
        checks, facts, _ = self.run_checks(self.runner("rtx4090-intel.txt"), UV_TORCH_BACKEND="cu130",
                                           AQ_DRM_DEVICES="/dev/dri/card0:/dev/dri/card1")
        self.assertEqual((facts.nv_version, facts.nv_open, facts.secure_boot), ("595.58", True, True))
        self.assertEqual(facts.nv_module_kind, "prebuilt")
        for cid in ("gpu.detect", "gpu.arch", "nvidia.driver", "nvidia.branch", "nvidia.open", "boot.secureboot",
                    "nvidia.kernel", "nvidia.uvm", "nvidia.modeset", "nvidia.suspend", "nvidia.resume",
                    "containers.gpu", "vulkan.icd", "compute.backend", "cuda.compat", "memory.zram", "fs.snapper",
                    "snapshots.recent", "user.groups"):
            self.assertEqual(checks[cid].status, "ok", f"{cid}: {checks[cid].msg}")
        self.assertIn(checks["gpu.prime"].status, ("ok",))
        # the fake /srv/ai sits on "btrfs" (per /proc/mounts) but is a plain directory → honest warning
        self.assertEqual(checks["storage.ai"].status, "warn")
        self.assertIn("subvolume", checks["storage.ai"].msg[0])
        rec = C.recommendation(facts)
        self.assertEqual(rec["packages"], ["nvidia-driver-595-open", "linux-modules-nvidia-595-open-generic"])
        self.assertEqual(rec["torchBackend"], "cu130")
        self.assertGreaterEqual(len(checks), 20)

    def test_every_check_is_bilingual(self):
        self.healthy_nvidia()
        checks, _, _ = self.run_checks(self.runner("rtx4090-intel.txt"))
        for c in checks.values():
            self.assertTrue(all(c.title) and all(c.msg), c.id)
            self.assertIn(c.status, ("ok", "warn", "fail", "skip"))


class ProblemsTest(DoctorBase):
    def test_uvm_missing_has_safe_fix(self):
        self.healthy_nvidia()
        (self.sb.path("/sys/module/nvidia_uvm")).rmdir()
        self.sb.path("/dev/nvidia-uvm").unlink()
        checks, _, _ = self.run_checks(self.runner("rtx4090-intel.txt"))
        c = checks["nvidia.uvm"]
        self.assertEqual(c.status, "fail")
        self.assertTrue(c.fix.safe)
        self.assertIn(["modprobe", "nvidia_uvm"], c.fix.commands)
        self.assertIn("/etc/modules-load.d/svoya-nvidia-uvm.conf", c.fix.files)

    def test_legacy_pascal_on_nouveau(self):
        self.base_system()
        self.sb.pci("0000:01:00.0", 0x0300, 0x10DE, 0x1B06, driver="nouveau")
        self.sb.mkdir("/sys/module/nouveau")
        checks, facts, _ = self.run_checks(self.runner("gtx1080ti-nouveau.txt"), UV_TORCH_BACKEND="auto")
        self.assertEqual(checks["gpu.arch"].status, "warn")
        drv = checks["nvidia.driver"]
        self.assertEqual(drv.status, "fail")
        self.assertEqual(drv.fix.commands, [["apt", "install", "nvidia-driver-580", "linux-modules-nvidia-580-generic"]])
        self.assertFalse(drv.fix.safe)
        self.assertEqual(checks["compute.backend"].status, "fail")       # uv 'auto' picks cu128+ (uv #14742)
        self.assertIn("UV_TORCH_BACKEND=cu126", checks["compute.backend"].fix.user_files["/u/env.conf"])

    def test_blackwell_requires_open_modules(self):
        self.healthy_nvidia(open_=False)
        checks, _, _ = self.run_checks(self.runner("rtx5090.txt"))
        self.assertEqual(checks["nvidia.open"].status, "fail")
        self.assertEqual(checks["nvidia.branch"].status, "warn")          # 580 < 595 recommended

    def test_secure_boot_with_unsigned_dkms(self):
        self.healthy_nvidia()
        self.sb.kernel(KERNEL, nvidia="dkms")
        import shutil
        shutil.rmtree(self.sb.path(f"/lib/modules/{KERNEL}/kernel"))
        self.sb.write("/sys/module/nvidia/taint", "OE\n")
        checks, facts, _ = self.run_checks(self.runner("rtx4090-intel.txt"))
        self.assertEqual(facts.nv_module_kind, "dkms")
        self.assertEqual(checks["boot.secureboot"].status, "fail")
        self.assertIn("linux-modules-nvidia-595-open-generic", checks["boot.secureboot"].fix.commands[0])

    def test_new_kernel_without_nvidia_module(self):
        self.healthy_nvidia()
        self.sb.kernel("6.17.0-10-generic", nvidia=None)
        checks, _, _ = self.run_checks(self.runner("rtx4090-intel.txt"))
        c = checks["nvidia.kernel"]
        self.assertEqual(c.status, "fail")
        self.assertEqual(c.fix.commands, [["apt", "install", "linux-modules-nvidia-595-open-6.17.0-10-generic"]])

    def test_software_rendering_is_said(self):
        checks, _, _ = self.run_checks(self.runner("rx7900xtx.txt"), SVOYA_RENDERER="software")
        c = checks["gpu.detect"]
        self.assertEqual(c.status, "ok")
        self.assertIn("drawn on the CPU", c.msg[0])
        self.assertIn("рисует процессор", c.msg[1])
        checks, _, _ = self.run_checks(self.runner("rx7900xtx.txt"))
        self.assertNotIn("CPU", checks["gpu.detect"].msg[0])

    def test_suspend_not_configured(self):
        self.healthy_nvidia()
        self.sb.path("/etc/modprobe.d/svoya-nvidia.conf").unlink()
        checks, _, _ = self.run_checks(self.runner("rtx4090-intel.txt", enabled=False))
        c = checks["nvidia.suspend"]
        self.assertEqual(c.status, "warn")
        self.assertTrue(c.fix.safe)
        conf = c.fix.files["/etc/modprobe.d/svoya-nvidia.conf"]
        self.assertIn("NVreg_PreserveVideoMemoryAllocations=1", conf)
        self.assertIn("NVreg_UseKernelSuspendNotifiers=1", conf)

    def test_prime_desktop_on_dgpu(self):
        self.healthy_nvidia()
        self.sb.path("/sys/bus/pci/devices/0000:00:02.0/boot_vga").write_text("0\n")
        self.sb.path("/sys/bus/pci/devices/0000:01:00.0/boot_vga").write_text("1\n")
        self.sb.drm("card0", "0000:00:02.0")
        self.sb.drm("card1", "0000:01:00.0")
        checks, _, _ = self.run_checks(self.runner("rtx4090-intel.txt"))
        c = checks["gpu.prime"]
        self.assertEqual(c.status, "warn")
        self.assertIn("AQ_DRM_DEVICES,/dev/dri/card0:/dev/dri/card1", c.fix.commands[0][-1])

    def test_store_zram_snapper(self):
        self.base_system(mounts="/dev/sda1 / ext4 rw 0 0\n", swaps="")
        checks, _, _ = self.run_checks(FakeRunner({"id -Gn": "tester\n"}, available=set()))
        self.assertEqual(checks["storage.ai"].status, "fail")
        self.assertEqual(checks["storage.ai"].fix.commands[0], ["mkdir", "-p", str(self.sb.path("/srv/ai"))])
        self.assertEqual(checks["memory.zram"].status, "warn")
        self.assertFalse(checks["memory.zram"].fix.safe)
        self.assertEqual(checks["fs.snapper"].status, "warn")
        self.assertEqual(checks["gpu.detect"].status, "warn")


class AmdTest(DoctorBase):
    def test_rx7900xtx(self):
        self.base_system()
        self.sb.pci("0000:03:00.0", 0x0300, 0x1002, 0x744C, driver="amdgpu")
        self.sb.write("/dev/kfd", "")
        self.sb.write("/usr/share/vulkan/icd.d/radeon_icd.x86_64.json", "{}")
        checks, facts, _ = self.run_checks(self.runner("rx7900xtx.txt"), UV_TORCH_BACKEND="rocm7.2")
        self.assertEqual(checks["amd.rocm"].status, "ok")
        self.assertEqual(checks["compute.backend"].status, "ok")
        self.assertEqual(checks["vulkan.icd"].status, "ok")
        self.assertEqual(checks["nvidia.driver"].status, "skip")
        self.assertEqual(checks["containers.gpu"].status, "ok")

    def test_strix_halo_gtt_advice(self):
        self.base_system()
        self.sb.pci("0000:c5:00.0", 0x0380, 0x1002, 0x1586, driver="amdgpu")
        self.sb.write("/dev/kfd", "")
        self.sb.write("/sys/module/ttm/parameters/pages_limit", "4194304\n")      # 16 GiB
        checks, _, _ = self.run_checks(self.runner("strix-halo.txt"))
        c = checks["amd.gtt"]
        self.assertEqual(c.status, "warn")
        self.assertFalse(c.fix.safe)                                            # kernel parameters: manual only
        want_gib = int(65536000 * 1024 / 2**30) - 8
        self.assertIn(f"ttm.pages_limit={want_gib * 262144}", c.fix.commands[0][-1])


class FixTest(DoctorBase):
    def test_apply_root_and_user_fixes(self):
        self.healthy_nvidia()
        self.sb.path("/etc/modprobe.d/svoya-nvidia.conf").unlink()
        r = self.runner("rtx4090-intel.txt", enabled=False, extra={"modprobe": "", "systemctl enable": "",
                                                                   "update-initramfs": ""})
        checks, _, ctx = self.run_checks(r)
        todo = [c for c in checks.values() if c.status in ("warn", "fail") and c.fix and c.fix.safe]
        log = doctor_cli.apply_fixes(ctx, todo, root=True)
        self.assertTrue(self.sb.path("/etc/modprobe.d/svoya-nvidia.conf").exists())
        self.assertTrue(r.called("systemctl", "enable", "nvidia-suspend.service"))
        self.assertTrue(any("update-initramfs" in line for line in log))

    def test_fix_cli_dry_run_json(self):
        self.healthy_nvidia()
        self.sb.path("/usr/lib/systemd/system-sleep/svoya-nvidia-uvm").unlink()
        r = self.runner("rtx4090-intel.txt")
        ctx = self.sb.ctx(r, dry_run=True, UV_TORCH_BACKEND="cu130")
        args = argparse.Namespace(gpu=False, apply_root=None, fix=True, json=True, yes=True)
        rc, out = capture(doctor_cli.main, args, ctx)
        data = json.loads(out)
        self.assertEqual(rc, 0)
        self.assertTrue(data["dryRun"])
        self.assertTrue(any("svoya-nvidia-uvm" in line for line in data["applied"]))
        self.assertFalse(self.sb.path("/usr/lib/systemd/system-sleep/svoya-nvidia-uvm").exists())

    def test_report_json_and_cache(self):
        self.healthy_nvidia()
        ctx = self.sb.ctx(self.runner("rtx4090-intel.txt"))
        args = argparse.Namespace(gpu=True, apply_root=None, fix=False, json=True, yes=False)
        rc, out = capture(doctor_cli.main, args, ctx)
        data = json.loads(out)
        self.assertEqual(data["torchBackend"], "cu130")
        self.assertIn("summary", data)
        self.assertNotIn("storage.ai", [c["id"] for c in data["checks"]])     # --gpu subset
        cache = json.loads((ctx.paths.state_dir / "doctor.json").read_text())
        self.assertIn("gpuOk", cache)


class ParsersTest(SandboxTest):
    def test_modprobe_and_mounts(self):
        mp = parse_modprobe(["options nvidia NVreg_A=1 NVreg_B=/x # c\noptions nvidia-drm modeset=1\n"])
        self.assertEqual(mp["nvidia"], {"NVreg_A": "1", "NVreg_B": "/x"})
        self.assertEqual(mp["nvidia_drm"]["modeset"], "1")
        self.assertEqual(mount_for("/srv/ai", MOUNTS), ("/srv/ai", "btrfs"))
        self.assertEqual(mount_for("/home/x", MOUNTS), ("/", "btrfs"))
