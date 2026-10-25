"""``sos doctor --hardware``: a laptop in the fake root (Intel graphics, Intel Wi-Fi missing a firmware
file, Bluetooth switched off in software, a worn battery), a desktop with an unknown Wi-Fi chip and
no sound, and what the report must never contain (serial numbers, MAC addresses)."""
import contextlib
import io
import json
import os
import pathlib
import tempfile
from unittest import mock

from svoya_cli import commands
from svoya_cli.doctor import hardware as H

from .helpers import FakeRunner, Result, SandboxTest

JOURNAL_WARN = ("iwlwifi 0000:00:14.3: Direct firmware load for iwlwifi-so-a0-gf-a0-90.ucode failed with error -2\n"
                "iwlwifi 0000:00:14.3: Direct firmware load for iwlwifi-so-a0-gf-a0-90.ucode failed with error -2\n"
                "Bluetooth: hci0: Failed to load Intel firmware file intel/ibt-0040-0041.sfi (-2)\n")
JOURNAL_ERR = "ACPI BIOS Error (bug): Could not resolve symbol [\\_SB.PC00.XHCI.RHUB.HS14._PLD], AE_NOT_FOUND\n"


class Laptop(SandboxTest):
    def build(self):
        sb = self.sb
        for k, v in {"sys_vendor": "LENOVO", "product_name": "21CB", "product_version": "ThinkPad X1 Carbon Gen 10",
                     "bios_version": "N3AET69W", "bios_date": "01/12/2023", "product_serial": "PF3SECRET1",
                     "product_uuid": "11111111-2222-3333-4444-555555555555"}.items():
            sb.write(f"/sys/class/dmi/id/{k}", v + "\n")
        sb.mkdir("/sys/firmware/efi")
        sb.write("/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-e0c16a4c8f68", b"\x06\x00\x00\x00\x01")
        sb.write("/proc/cpuinfo", "processor\t: 0\nmodel name\t: 12th Gen Intel(R) Core(TM) i7-1260P\n"
                                  "processor\t: 1\nmodel name\t: 12th Gen Intel(R) Core(TM) i7-1260P\n")
        sb.write("/proc/meminfo", "MemTotal:       16127420 kB\n")
        sb.pci("0000:00:02.0", 0x0300, 0x8086, 0x46A6, driver="i915")
        sb.write("/sys/class/drm/card1-eDP-1/status", "connected\n")
        sb.write("/sys/class/drm/card1-HDMI-A-1/status", "disconnected\n")
        sb.pci("0000:00:14.3", 0x0280, 0x8086, 0x51F0, driver="iwlwifi")
        wl = sb.mkdir("/sys/class/net/wlan0")
        (wl / "device").symlink_to(sb.path("/sys/bus/pci/devices/0000:00:14.3"))
        sb.mkdir("/sys/class/net/wlan0/wireless")
        sb.write("/sys/class/net/wlan0/operstate", "up\n")
        sb.write("/sys/class/net/wlan0/address", "aa:bb:cc:dd:ee:ff\n")
        sb.mkdir("/sys/class/net/lo")
        for n, (t, soft) in {"rfkill0": ("wlan", "0"), "rfkill1": ("bluetooth", "1")}.items():
            sb.write(f"/sys/class/rfkill/{n}/type", t + "\n")
            sb.write(f"/sys/class/rfkill/{n}/soft", soft + "\n")
            sb.write(f"/sys/class/rfkill/{n}/hard", "0\n")
        sb.mkdir("/sys/class/bluetooth/hci0")
        sb.write("/proc/asound/cards", " 0 [sofhdadsp      ]: sof-hda-dsp - sof-hda-dsp\n"
                                       "                      LENOVO-21CB-ThinkPadX1CarbonGen10\n")
        for k, v in {"type": "Battery", "capacity": "81", "status": "Discharging", "energy_full": "36000000",
                     "energy_full_design": "57000000"}.items():
            sb.write(f"/sys/class/power_supply/BAT0/{k}", v + "\n")
        sb.write("/sys/class/power_supply/AC/type", "Mains\n")
        sb.write("/sys/class/power_supply/AC/online", "0\n")
        sb.write("/sys/class/power_supply/hidpp_battery_0/type", "Battery\n")
        sb.write("/sys/class/power_supply/hidpp_battery_0/scope", "Device\n")
        sb.write("/sys/power/mem_sleep", "[s2idle] deep\n")
        sb.write("/proc/bus/input/devices", 'I: Bus=0018\nN: Name="SYNA8016:00 06CB:CEB3 Touchpad"\n\n'
                                            'I: Bus=0011\nN: Name="AT Translated Set 2 keyboard"\n')
        sb.write("/sys/class/video4linux/video0/name", "Integrated Camera: Integrated C\n")
        sb.write("/sys/class/video4linux/video1/name", "Integrated Camera: Integrated C\n")
        for k, v in {"size": "1000215216", "removable": "0", "queue/rotational": "0",
                     "device/model": "SAMSUNG MZVL2512HCJQ-00BL7"}.items():
            sb.write(f"/sys/block/nvme0n1/{k}", v + "\n")
        sb.write("/sys/block/loop0/size", "1000\n")
        runner = FakeRunner(available={"journalctl"}, responses={
            ("journalctl", "-k", "-b", "-p", "warning"): Result(0, JOURNAL_WARN, ""),
            ("journalctl", "-k", "-b", "-p", "err"): Result(0, JOURNAL_ERR, "")})
        return self.sb.ctx(runner)

    def test_the_report(self):
        rep = H.gather(self.build())
        self.assertEqual(rep["computer"]["firmware"], "uefi")
        self.assertTrue(rep["computer"]["secureBoot"])
        self.assertEqual(rep["processor"]["threads"], 2)
        self.assertEqual(rep["processor"]["memoryGiB"], 15.4)
        self.assertEqual(rep["graphics"][0]["driver"], "i915")
        self.assertEqual(rep["screens"], ["eDP-1"])
        self.assertEqual(rep["network"], [{"name": "wlan0", "kind": "wifi", "driver": "iwlwifi", "state": "up"}])
        self.assertTrue(rep["bluetooth"])
        self.assertEqual(rep["sound"][0]["name"], "sof-hda-dsp")
        self.assertEqual([b["name"] for b in rep["power"]["batteries"]], ["BAT0"])        # not the mouse
        self.assertEqual(rep["power"]["batteries"][0]["healthPct"], 63)
        self.assertFalse(rep["power"]["ac"])
        self.assertEqual(rep["input"]["touchpad"], ["SYNA8016:00 06CB:CEB3 Touchpad"])
        self.assertEqual(rep["input"]["camera"], ["Integrated Camera: Integrated C"])
        self.assertEqual([d["name"] for d in rep["disks"]], ["nvme0n1"])
        self.assertEqual(rep["disks"][0]["sizeGB"], 512)
        self.assertEqual(rep["firmwareMissing"], ["iwlwifi-so-a0-gf-a0-90.ucode"])
        self.assertEqual(len(rep["kernelErrors"]), 1)
        said = " ".join(p["en"] for p in rep["problems"])
        self.assertIn("Bluetooth is switched off in software", said)
        self.assertIn("iwlwifi-so-a0-gf-a0-90.ucode", said)
        self.assertIn("holds 63%", said)
        self.assertNotIn("Wi-Fi adapter", said)

    def test_never_serials_or_mac_addresses(self):
        ctx = self.build()
        rep = H.gather(ctx)
        blob = json.dumps(rep) + H.render(rep, color=False)
        for secret in ("PF3SECRET1", "aa:bb:cc:dd:ee:ff", "11111111-2222"):
            self.assertNotIn(secret, blob)

    def test_save_writes_plain_text(self):
        ctx = self.build()
        out = pathlib.Path(tempfile.mkdtemp()) / "report.txt"
        args = type("A", (), {"json": False, "save": str(out)})()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = H.main(args, ctx)
        self.assertEqual(rc, 0)                                       # warnings only, nothing failing
        text = out.read_text()
        self.assertNotIn("\x1b", text)
        self.assertIn("LENOVO 21CB ThinkPad X1 Carbon Gen 10", text)
        self.assertIn("Secure Boot", text)


class Desktop(SandboxTest):
    def test_unknown_wifi_and_no_sound(self):
        sb = self.sb
        sb.pci("0000:01:00.0", 0x0300, 0x10DE, 0x2684, driver="nouveau")
        sb.pci("0000:03:00.0", 0x0280, 0x14C3, 0x0616)                 # MediaTek Wi-Fi, no driver
        sb.write("/proc/meminfo", "MemTotal:        6000000 kB\n")
        rep = H.gather(sb.ctx(FakeRunner()))
        def level(start):
            return next((p["level"] for p in rep["problems"] if p["en"].startswith(start)), None)
        self.assertEqual(level("Wi-Fi adapter MediaTek 14c3:0616 has no driver"), "fail")
        self.assertEqual(level("No sound card"), "fail")
        self.assertEqual(level("NVIDIA runs on nouveau"), "warn")
        self.assertTrue(any("local models" in p["en"] for p in rep["problems"]))
        self.assertEqual(rep["problems"][0]["level"], "fail")                       # the worst first
        self.assertEqual(rep["computer"]["firmware"], "bios")


class Words(SandboxTest):
    def test_sos_hardware_and_zhelezo(self):
        self.assertEqual(commands.normalize(["hardware"]), ["doctor", "--hardware"])
        self.assertEqual(commands.normalize(["железо", "--save"]), ["doctor", "--hardware", "--save"])
        self.assertEqual(commands.normalize(["hw", "--json"]), ["doctor", "--hardware", "--json"])

    def test_the_command_runs(self):
        from svoya_cli import main
        with mock.patch.dict(os.environ, self.sb.env(LANG="ru_RU.UTF-8")), contextlib.redirect_stdout(io.StringIO()):
            main.main(["железо"])
        self.assertIn("SOS: отчёт о железе", self.output())
        self.assertIn("Что не так", self.output())
