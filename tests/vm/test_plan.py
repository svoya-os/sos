# SPDX-License-Identifier: Apache-2.0
"""The shipped plan is valid; keys parse; the QEMU command line is what CI expects."""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import keys  # noqa: E402
import run  # noqa: E402


class PlanTests(unittest.TestCase):
    def test_shipped_plan_is_valid_and_covers_milestones(self):
        plan = run.load_plan(HERE / "plan.json")
        shots = [s["name"] for s in plan["steps"] if s["action"] == "screenshot"]
        self.assertEqual(shots, ["01-boot-menu", "02-plymouth", "03-live-desktop", "04-launcher", "05-jackson"])
        combos = [keys.parse_combo(s["keys"]) for s in plan["steps"] if s["action"] == "key"]
        self.assertIn(["meta_l", "spc"], combos)
        self.assertIn(["meta_l", "j"], combos)

    def test_safe_graphics_plan_boots_the_second_entry(self):
        plan = run.load_plan(HERE / "safe-graphics.json")
        keys_pressed = [keys.parse_combo(s["keys"]) for s in plan["steps"] if s["action"] == "key"]
        self.assertEqual(keys_pressed[:2], [["down"], ["ret"]])      # «SOS (safe graphics)», then Enter
        shots = [s["name"] for s in plan["steps"] if s["action"] == "screenshot"]
        self.assertIn("03-live-desktop", shots)
        grub = (HERE.parents[1] / "image/boot/grub.cfg").read_text()
        entries = re.findall(r'^    menuentry "([^"]+)"', grub, re.M)
        self.assertIn("safe graphics", entries[1])                    # what "down" lands on
        self.assertIn("nomodeset", grub.split("--id sos-safe", 1)[1].split("}", 1)[0])

    def test_invalid_plans_are_rejected(self):
        bad = [
            {"steps": []},
            {"steps": [{"action": "dance"}]},
            {"steps": [{"action": "screenshot", "name": "../x"}]},
            {"steps": [{"action": "screenshot", "name": "a"}, {"action": "screenshot", "name": "a"}]},
            {"steps": [{"action": "wait_serial", "pattern": "("}]},
            {"steps": [{"action": "sleep"}]},
        ]
        for plan in bad:
            with self.subTest(plan=plan), self.assertRaises(Exception):
                run.validate_plan(plan)


class KeyTests(unittest.TestCase):
    def test_combos_and_aliases(self):
        self.assertEqual(keys.parse_combo("Super+Space"), ["meta_l", "spc"])
        self.assertEqual(keys.parse_combo("meta_l+j"), ["meta_l", "j"])
        self.assertEqual(keys.parse_combo(["ctrl", "alt", "Delete"]), ["ctrl", "alt", "delete"])
        with self.assertRaises(ValueError):
            keys.parse_combo("")

    def test_text(self):
        self.assertEqual(keys.text_to_combos("aZ1 ?"),
                         [["a"], ["shift", "z"], ["1"], ["spc"], ["shift", "slash"]])
        with self.assertRaises(ValueError):
            keys.text_to_combos("я")


class QemuCommandTests(unittest.TestCase):
    def args(self, firmware: str) -> argparse.Namespace:
        return argparse.Namespace(iso="/tmp/sos.iso", firmware=firmware, accel="tcg", memory=None, smp=None,
                                  qemu="qemu-system-x86_64")

    def test_uefi_secure_boot_command(self):
        plan = run.load_plan(HERE / "plan.json")
        cmd = run.qemu_command(self.args("uefi-sb"), plan, pathlib.Path("/tmp/out"), "/tmp/out/VARS.fd",
                               "/usr/share/OVMF/OVMF_CODE_4M.secboot.fd")
        line = " ".join(cmd)
        self.assertIn("q35,smm=on,accel=tcg", line)
        self.assertIn("driver=cfi.pflash01,property=secure,value=on", line)
        self.assertIn("type=1,manufacturer=SOS,product=sos-vm-test", line)
        self.assertIn("file:/tmp/out/serial.log", line)
        self.assertIn("unix:/tmp/out/qmp.sock,server=on,wait=off", line)
        self.assertIn("virtio-vga,xres=1440,yres=900", line)

    def test_bios_command_has_no_pflash(self):
        plan = run.load_plan(HERE / "plan.json")
        line = " ".join(run.qemu_command(self.args("bios"), plan, pathlib.Path("/tmp/out"), None, None))
        self.assertNotIn("pflash", line)
        self.assertIn("bootindex=0", line)

    def test_auto_accel_falls_back_to_tcg(self):
        plan = run.load_plan(HERE / "plan.json")
        args = self.args("uefi")
        args.accel = "auto"
        saved = run.kvm_usable
        try:
            run.kvm_usable = lambda: True
            cmd = run.qemu_command(args, plan, pathlib.Path("/tmp/out"), "/tmp/out/VARS.fd", "/x/CODE.fd")
        finally:
            run.kvm_usable = saved
        line = " ".join(cmd)
        self.assertIn("q35,accel=kvm:tcg", line)
        self.assertEqual(cmd[cmd.index("-cpu") + 1], "max")  # "host" would abort under the TCG fallback


if __name__ == "__main__":
    unittest.main()
