import unittest

from svoya_cli.hw import amd_db, nvidia_db
from svoya_cli.hw import gpu as gpu_mod
from svoya_cli.hw.pci import parse_lspci, scan_sysfs

from .helpers import FakeRunner, SandboxTest, fixture


class LspciTest(unittest.TestCase):
    def test_parse_display_devices_only(self):
        devs = parse_lspci(fixture("lspci/rtx4090-intel.txt"))
        self.assertEqual([d.slot for d in devs], ["0000:00:02.0", "0000:01:00.0"])
        nv = devs[1]
        self.assertEqual((nv.vendor, nv.device_id, nv.driver), ("nvidia", 0x2684, "nvidia"))
        self.assertIn("nouveau", nv.modules)
        self.assertEqual(nv.marketing_name, "GeForce RTX 4090")
        self.assertEqual(devs[0].vendor, "intel")

    def test_no_domain_and_nouveau(self):
        devs = parse_lspci(fixture("lspci/gtx1080ti-nouveau.txt"))
        self.assertEqual(len(devs), 1)
        self.assertEqual(devs[0].slot, "0000:01:00.0")
        self.assertEqual(devs[0].driver, "nouveau")

    def test_display_controller_class(self):
        devs = parse_lspci(fixture("lspci/strix-halo.txt"))
        self.assertEqual(devs[0].class_code, 0x0380)
        self.assertEqual(devs[0].device_id, 0x1586)


class NvidiaDbTest(unittest.TestCase):
    def test_arch_by_device_id(self):
        cases = {0x2684: "ada", 0x1b06: "pascal", 0x2b85: "blackwell", 0x2c02: "blackwell", 0x1e04: "turing",
                 0x2184: "turing", 0x1d81: "volta", 0x13c2: "maxwell", 0x2204: "ampere", 0x2330: "hopper",
                 0x20b5: "ampere", 0x1eb8: "turing", 0x2f04: "blackwell"}
        for did, arch in cases.items():
            self.assertEqual(nvidia_db.arch_from_id(did), arch, hex(did))

    def test_name_fallback(self):
        self.assertEqual(nvidia_db.arch_from_name("NVIDIA GeForce RTX 5070 Ti"), "blackwell")
        self.assertEqual(nvidia_db.arch_from_name("GeForce GTX 1660 SUPER"), "turing")
        self.assertEqual(nvidia_db.arch_from_name("GeForce GTX TITAN X"), "maxwell")
        self.assertEqual(nvidia_db.arch_from_name("TITAN Xp"), "pascal")
        self.assertEqual(nvidia_db.arch_from_name("Tesla V100-PCIE-32GB"), "volta")
        self.assertEqual(nvidia_db.arch_for(0xFFFF, "NVIDIA RTX 4000 Ada Generation"), "ada")

    def test_branch_and_backend_policy(self):
        self.assertEqual(nvidia_db.info("pascal").branch, "580")
        self.assertEqual(nvidia_db.info("pascal").torch, "cu126")
        self.assertEqual(nvidia_db.info("turing").torch, "cu130")
        self.assertEqual(nvidia_db.info("blackwell").open_modules, "required")
        self.assertIsNone(nvidia_db.info("kepler").branch)
        self.assertEqual(nvidia_db.driver_packages("595", True, "generic"),
                         ["nvidia-driver-595-open", "linux-modules-nvidia-595-open-generic"])
        self.assertEqual(nvidia_db.driver_packages("580", False, "generic"),
                         ["nvidia-driver-580", "linux-modules-nvidia-580-generic"])
        self.assertEqual(nvidia_db.kernel_flavor("6.17.0-9-generic"), "generic")
        self.assertEqual(nvidia_db.kernel_flavor("6.17.0-1004-lowlatency"), "lowlatency")

    def test_ranges_are_sorted_and_disjoint(self):
        last = -1
        for lo, hi, _ in nvidia_db.ARCH_RANGES:
            self.assertLessEqual(lo, hi)
            self.assertGreater(lo, last)
            last = hi


class AmdDbTest(unittest.TestCase):
    def test_gfx(self):
        self.assertEqual(amd_db.gfx_for(0x744C), "gfx1100")
        self.assertEqual(amd_db.gfx_for(0x7550), "gfx1201")
        self.assertEqual(amd_db.gfx_for(0x1586), "gfx1151")
        self.assertTrue(amd_db.is_apu(0x1586))
        self.assertEqual(amd_db.gfx_from_target_version(110501), "gfx1151")
        self.assertEqual(amd_db.gfx_from_target_version(90010), "gfx90a")
        self.assertEqual(amd_db.gfx_from_target_version(100300), "gfx1030")

    def test_intel_discrete(self):
        self.assertTrue(amd_db.intel_is_discrete(0xE20B))
        self.assertTrue(amd_db.intel_is_discrete(0x56A0))
        self.assertFalse(amd_db.intel_is_discrete(0xA780))


class NvidiaSmiTest(unittest.TestCase):
    def test_parse(self):
        g = gpu_mod.parse_nvidia_smi(fixture("nvidia-smi/rtx4090.csv"))[0]
        self.assertEqual(g, {"index": 0, "vendor": "nvidia", "name": "RTX 4090", "tempC": 64, "vramUsedMiB": 11468,
                             "vramTotalMiB": 24564, "util": 93, "powerW": 301, "driver": "595.58"})

    def test_not_available_fields_are_dropped(self):
        gs = gpu_mod.parse_nvidia_smi(fixture("nvidia-smi/two-gpus.csv"))
        self.assertEqual(len(gs), 2)
        self.assertNotIn("powerW", gs[1])
        self.assertEqual(gs[1]["index"], 1)

    def test_short_names(self):
        self.assertEqual(gpu_mod.short_name("NVIDIA GeForce RTX 4090 Laptop GPU"), "RTX 4090 Laptop GPU")
        self.assertEqual(gpu_mod.short_name("AMD Radeon RX 7900 XTX"), "RX 7900 XTX")


class InventoryTest(SandboxTest):
    def test_amd_sysfs_stats(self):
        self.sb.amd_card("card1", "0000:03:00.0", 0x744C, vram_used=4 * 2**30, vram_total=24 * 2**30, busy=37,
                         temp_mc=58000, power_uw=212_000_000)
        stats = gpu_mod.amd_stats(self.sb.ctx())
        self.assertEqual(stats[0]["vramTotalMiB"], 24576)
        self.assertEqual(stats[0]["vramUsedMiB"], 4096)
        self.assertEqual((stats[0]["tempC"], stats[0]["powerW"], stats[0]["util"]), (58, 212, 37))
        self.assertEqual(stats[0]["name"], "RX 7900 XTX / XT / GRE")
        self.assertNotIn("integrated", stats[0])

    def test_strix_halo_unified_memory(self):
        self.sb.amd_card("card0", "0000:c5:00.0", 0x1586, vram_total=512 * 2**20, gtt_total=96 * 2**30, gtt_used=2 * 2**30)
        g = gpu_mod.amd_stats(self.sb.ctx())[0]
        self.assertTrue(g["integrated"])
        self.assertEqual(g["gttTotalMiB"], 96 * 1024)

    def test_inventory_from_lspci_and_primary(self):
        r = FakeRunner({"lspci -Dnnk": fixture("lspci/rtx4090-intel.txt")}, available={"lspci"})
        ctx = self.sb.ctx(r)
        gpus = gpu_mod.inventory(ctx)
        self.assertEqual([g.vendor for g in gpus], ["intel", "nvidia"])
        self.assertTrue(gpus[0].integrated)
        p = gpu_mod.primary_compute(gpus)
        self.assertEqual((p.vendor, p.arch), ("nvidia", "ada"))
        self.assertEqual(gpu_mod.torch_backend(p), "cu130")

    def test_inventory_sysfs_fallback(self):
        self.sb.pci("0000:01:00.0", 0x0300, 0x10DE, 0x1B06, driver="nouveau")
        self.sb.pci("0000:00:1f.3", 0x0403, 0x8086, 0x7A50)   # audio: ignored
        gpus = gpu_mod.inventory(self.sb.ctx())
        self.assertEqual(len(gpus), 1)
        self.assertEqual(gpus[0].arch, "pascal")
        self.assertEqual(gpus[0].pci.driver, "nouveau")
        self.assertEqual(gpu_mod.torch_backend(gpus[0]), "cu126")

    def test_backend_for_each_vendor(self):
        self.sb.pci("0000:03:00.0", 0x0300, 0x1002, 0x744C, driver="amdgpu")
        g = gpu_mod.inventory(self.sb.ctx())[0]
        self.assertEqual(gpu_mod.torch_backend(g, "rocm7.2"), "rocm7.2")
        self.assertEqual(gpu_mod.torch_backend(None), "cpu")

    def test_scan_sysfs_handles_missing_dir(self):
        self.assertEqual(scan_sysfs(self.sb.path("/nope")), [])


if __name__ == "__main__":
    unittest.main()
