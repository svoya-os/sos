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

    def test_every_shipped_plan_is_valid(self):
        plans = sorted(HERE.glob("*.json"))
        self.assertGreaterEqual(len(plans), 4)
        for path in plans:
            with self.subTest(plan=path.name):
                plan = run.load_plan(path)
                self.assertTrue(plan.get("name"))
                memory = plan.get("vm", {}).get("memory_mib", 6144)
                self.assertLessEqual(memory, 12288)          # GitHub's runners have 16 GB
                for step in plan["steps"]:
                    if "count" in step:
                        self.assertEqual(step["action"], "wait_serial")

    def test_install_plan_boots_the_installed_disk(self):
        plan = run.load_plan(HERE / "install.json")
        self.assertEqual((plan["vm"]["disk_gib"], plan["vm"]["reboot"]), (64, True))
        actions = [s["action"] for s in plan["steps"]]
        self.assertLess(actions.index("eject"), actions.index("reset"))   # the ISO out first, then the reset
        waits = [s for s in plan["steps"] if s["action"] == "wait_serial" and "installation finalized" in s["pattern"]]
        self.assertEqual(len(waits), 1)
        for s in plan["steps"]:
            if s["action"] == "type":
                keys.text_to_combos(s["text"])
        typed = [s["text"] for s in plan["steps"] if s["action"] == "type"]
        self.assertEqual(typed[0], "/usr/lib/svoya/vm-test-installer\n")      # short: long typing got lost
        helper = (HERE.parents[1] / "image/overlay-live/usr/lib/svoya/vm-test-installer")
        self.assertTrue(helper.stat().st_mode & 0o111)
        text = helper.read_text()
        self.assertIn("initialPartitioningChoice: erase", text)
        self.assertIn('exec sos-install -c "$cfg"', text)
        self.assertIn("SOS-STEP installer-start", text)
        lib = (HERE.parents[1] / "installer/scripts/lib.sh").read_text()
        self.assertIn("logger -t sos-installer", lib)                  # what the wait above reads
        self.assertIn('log "installation finalized"', (HERE.parents[1] / "installer/scripts/finalize.sh").read_text())

    def test_model_plan_waits_for_each_answer(self):
        plan = run.load_plan(HERE / "model.json")
        answers = [s for s in plan["steps"] if s["action"] == "wait_serial" and "turn done" in s["pattern"]]
        self.assertEqual([s.get("count", 1) for s in answers], [1, 2, 3])
        typed = " ".join(s.get("text", "") for s in plan["steps"] if s["action"] == "type")
        self.assertIn("sos install qwen3.5-4b:Q4_K_M --yes", typed)
        for s in plan["steps"]:
            if s["action"] == "type":
                keys.text_to_combos(s["text"])                  # US keys only

    def test_downloads_wait_for_the_network(self):
        # ISO #8: a live session without a wired connection failed `sos install` with «Temporary failure
        # resolving»; the smoke test now checks the network, the plans that download wait for it.
        agent = (HERE.parents[1] / "image/overlay-live/usr/lib/svoya/vm-test-agent").read_text()
        self.assertIn("mark network-online", agent)
        self.assertIn("mark network-offline", agent)
        for name in ("plan.json", "model.json", "games.json"):
            with self.subTest(plan=name):
                steps = run.load_plan(HERE / name)["steps"]
                waits = [i for i, s in enumerate(steps) if s["action"] == "wait_serial" and "network-online" in s["pattern"]]
                self.assertEqual(len(waits), 1)
                self.assertIn("network-offline", steps[waits[0]]["fail_pattern"])
                typed = [i for i, s in enumerate(steps) if s["action"] == "type" and "sos install" in s.get("text", "")]
                self.assertTrue(all(waits[0] < i for i in typed))
        netplan = (HERE.parents[1] / "packages/svoya-base/files/etc/netplan/01-network-manager-all.yaml").read_text()
        self.assertRegex(netplan, r"(?m)^  renderer: NetworkManager$")      # Ethernet is managed, as on Ubuntu Desktop
        rules = (HERE.parents[1] / "packages/svoya-base/debian/rules").read_text()
        self.assertIn("chmod 0600 $(PKG)/etc/netplan/01-network-manager-all.yaml", rules)
        shadow = HERE.parents[1] / "packages/svoya-base/files/etc/NetworkManager/conf.d/10-globally-managed-devices.conf"
        self.assertTrue(all(line.startswith("#") for line in shadow.read_text().splitlines()))   # no unmanaged-devices

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

    def test_install_disk_and_reboot(self):
        plan = {"vm": {"disk_gib": 64, "reboot": True}, "steps": [{"action": "click", "at": [10, 20]}]}
        run.validate_plan(plan)
        cmd = " ".join(run.qemu_command(self.args("uefi"), plan, pathlib.Path("/tmp/out"), "/tmp/out/VARS.fd",
                                        "/x/CODE.fd", disk="/tmp/out/disk.qcow2"))
        self.assertIn("file=/tmp/out/disk.qcow2,if=none,id=hd0,format=qcow2", cmd)
        self.assertIn("nvme,drive=hd0,serial=SOS-VM-TEST,bootindex=1", cmd)
        self.assertIn("ide-cd,drive=cd0,bus=ide.0,bootindex=0,id=cdrom", cmd)
        self.assertNotIn("-no-reboot", cmd)
        smoke = " ".join(run.qemu_command(self.args("uefi"), run.load_plan(HERE / "plan.json"),
                                          pathlib.Path("/tmp/out"), "/tmp/out/VARS.fd", "/x/CODE.fd"))
        self.assertIn("-no-reboot", smoke)
        self.assertNotIn("nvme", smoke)
        with self.assertRaises(ValueError):
            run.validate_plan({"steps": [{"action": "click", "at": [10]}]})

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

    def test_display_adapters(self):
        # vm.display: virtio (default), vmware (VMware SVGA II), std (bochs). QEMU's VMware adapter is no
        # stand-in for VirtualBox: vmwgfx does not bind to it and the guest has no DRM device at all.
        plan = {"vm": {"display": "std"}, "steps": [{"action": "sleep", "seconds": 1}]}
        run.validate_plan(plan)
        cmd = run.qemu_command(self.args("uefi"), plan, pathlib.Path("/tmp/out"), "/tmp/out/VARS.fd", "/x/CODE.fd")
        self.assertEqual(cmd[cmd.index("-vga") + 1], "std")
        self.assertNotIn("virtio-vga", " ".join(cmd))
        with self.assertRaises(ValueError):
            run.validate_plan({"vm": {"display": "cirrus"}, "steps": [{"action": "sleep", "seconds": 1}]})

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
