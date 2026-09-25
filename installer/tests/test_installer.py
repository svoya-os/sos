# SPDX-License-Identifier: Apache-2.0
"""Installer helpers: GPU branch selection, firmware entry matching, Calamares config sanity."""
from __future__ import annotations

import io
import json
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

INSTALLER = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(INSTALLER / "scripts"))

import efi_entries  # noqa: E402
import gpu_select  # noqa: E402

META = {
    "schema": 1,
    "branches": [
        {"id": "595-open", "component": "nvidia-595-open", "driver": "595.91.07",
         "packages": ["linux-modules-nvidia-595-open-generic", "nvidia-utils-595"],
         "modaliases": ["pci:v000010DEd00002684sv*sd*bc03sc*i*", "pci:v000010DEd00002B85sv*sd*bc03sc*i*"]},
        {"id": "580", "component": "nvidia-580", "driver": "580.178.04",
         "packages": ["linux-modules-nvidia-580-generic", "nvidia-utils-580"],
         "modaliases": ["pci:v000010DEd00002684sv*sd*bc03sc*i*", "pci:v000010DEd00001B80sv*sd*bc03sc*i*"]},
    ],
}


def fake_sysfs(root: pathlib.Path, devices: list[tuple[str, str, str, str]]) -> pathlib.Path:
    for slot, vendor, klass, alias in devices:
        d = root / "bus" / "pci" / "devices" / slot
        d.mkdir(parents=True)
        (d / "vendor").write_text(vendor + "\n")
        (d / "class").write_text(klass + "\n")
        (d / "modalias").write_text(alias + "\n")
    return root


class GpuSelectTests(unittest.TestCase):
    def run_select(self, devices):
        with tempfile.TemporaryDirectory() as tmp:
            sysfs = fake_sysfs(pathlib.Path(tmp, "sys"), devices)
            meta = pathlib.Path(tmp, "svoya-gpu.json")
            meta.write_text(json.dumps(META))
            buf = io.StringIO()
            with redirect_stdout(buf):
                gpu_select.main(["--json", str(meta), "--sysfs", str(sysfs), "--format", "json"])
            return json.loads(buf.getvalue())

    def test_rtx_4090_gets_open_595(self):
        r = self.run_select([("0000:01:00.0", "0x10de", "0x030000", "pci:v000010DEd00002684sv00001043sd000088E2bc03sc00i00")])
        self.assertEqual(r["branch"], "595-open")
        self.assertIn("linux-modules-nvidia-595-open-generic", r["packages"])

    def test_pascal_falls_back_to_580(self):
        r = self.run_select([("0000:01:00.0", "0x10de", "0x030000", "pci:v000010DEd00001B80sv00001458sd00003702bc03sc00i00")])
        self.assertEqual(r["branch"], "580")

    def test_unknown_nvidia_device_has_no_branch(self):
        r = self.run_select([("0000:01:00.0", "0x10de", "0x030000", "pci:v000010DEd00000FFFsv0sd0bc03sc00i00")])
        self.assertEqual(r["branch"], "")
        self.assertEqual(len(r["devices"]), 1)

    def test_amd_and_nvidia_audio_are_ignored(self):
        r = self.run_select([
            ("0000:03:00.0", "0x1002", "0x030000", "pci:v00001002d0000744Csv0sd0bc03sc00i00"),
            ("0000:01:00.1", "0x10de", "0x040300", "pci:v000010DEd000022BAsv0sd0bc04sc03i00"),
        ])
        self.assertEqual(r["devices"], [])
        self.assertEqual(r["branch"], "")

    def test_shell_output_is_eval_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            sysfs = fake_sysfs(pathlib.Path(tmp, "sys"), [])
            buf = io.StringIO()
            with redirect_stdout(buf):
                gpu_select.main(["--json", str(pathlib.Path(tmp, "missing.json")), "--sysfs", str(sysfs)])
            self.assertIn("SOS_GPU_BRANCH=''", buf.getvalue())


EFIBOOTMGR = """BootCurrent: 0001
Timeout: 0 seconds
BootOrder: 0003,0001,0000
Boot0000* UiApp\tFvVol(7cb8bdc9-f8eb-4f34-aaea-3ee4af6516a1)/FvFile(462caa21-7614-4503-836e-8ab6f4662331)
Boot0001* ubuntu\tHD(1,GPT,5ab3c1de-0000-4000-8000-00000000abcd,0x800,0x100000)/File(\\EFI\\ubuntu\\shimx64.efi)
Boot0002* ubuntu\tHD(1,GPT,99999999-0000-4000-8000-000000000000,0x800,0x100000)/File(\\EFI\\ubuntu\\shimx64.efi)
Boot0003* SOS\tHD(1,GPT,5ab3c1de-0000-4000-8000-00000000abcd,0x800,0x100000)/File(\\EFI\\ubuntu\\shimx64.efi)
"""


class EfiEntriesTests(unittest.TestCase):
    def test_only_our_partition_and_label(self):
        entries = efi_entries.parse(EFIBOOTMGR)
        self.assertEqual(len(entries), 4)
        self.assertEqual(efi_entries.matching(entries, "5AB3C1DE-0000-4000-8000-00000000ABCD", "ubuntu",
                                              "\\EFI\\ubuntu\\shimx64.efi"), ["0001"])

    def test_old_space_separated_format(self):
        text = "Boot0004* ubuntu HD(1,GPT,5ab3c1de-0000-4000-8000-00000000abcd,0x800,0x1000)/File(\\EFI\\ubuntu\\shimx64.efi)\n"
        self.assertEqual(efi_entries.matching(efi_entries.parse(text), "5ab3c1de-0000-4000-8000-00000000abcd",
                                              "ubuntu", "\\EFI\\ubuntu\\shimx64.efi"), ["0004"])


class CalamaresConfigTests(unittest.TestCase):
    def test_all_configs_parse_and_instances_exist(self):
        try:
            import yaml  # type: ignore
        except ImportError:
            self.skipTest("PyYAML not installed")
        settings = yaml.safe_load((INSTALLER / "settings.conf").read_text())
        for conf in (INSTALLER / "modules").glob("*.conf"):
            with self.subTest(conf=conf.name):
                self.assertIsInstance(yaml.safe_load(conf.read_text()), dict)
        for inst in settings["instances"]:
            self.assertTrue((INSTALLER / "modules" / inst["config"]).is_file(), inst["config"])
        executed = [m for phase in settings["sequence"] for k, mods in phase.items() if k == "exec" for m in mods]
        order = {m: i for i, m in enumerate(executed)}
        # dracut must replace casper/initramfs-tools before grubcfg detects the initramfs tool
        self.assertLess(order["shellprocess@sos-dracut"], order["grubcfg"])
        self.assertLess(order["contextualprocess@sos-bootloader-packages"], order["bootloader"])
        self.assertLess(order["bootloader"], order["contextualprocess@sos-after-bootloader"])
        self.assertEqual(executed[-1], "umount")

    def test_btrfs_layout(self):
        try:
            import yaml  # type: ignore
        except ImportError:
            self.skipTest("PyYAML not installed")
        mount = yaml.safe_load((INSTALLER / "modules" / "mount.conf").read_text())
        subvols = {s["subvolume"]: s["mountPoint"] for s in mount["btrfsSubvolumes"]}
        self.assertEqual(subvols["/@ai"], "/srv/ai")
        for sv in ("/@", "/@home", "/@snapshots", "/@var_log", "/@var_cache", "/@containers"):
            self.assertIn(sv, subvols)
        self.assertEqual(mount["btrfsSwapSubvol"], "/@swap")


if __name__ == "__main__":
    unittest.main()
