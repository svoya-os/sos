#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Boot the SOS ISO in QEMU and follow a test plan (tests/vm/plan.json): wait for serial markers,
press keys over QMP, take screenshots at milestones.

    python3 tests/vm/run.py --iso dist/iso/sos-26.10-amd64.iso --firmware uefi --out out/vm-uefi
    python3 tests/vm/run.py --iso x.iso --dry-run          # print the QEMU command, validate plan

Firmware: uefi (OVMF), uefi-sb (OVMF with Secure Boot + Microsoft keys), bios (SeaBIOS).
The VM identifies itself with SMBIOS product "sos-vm-test": the ISO's GRUB then mirrors its menu to
the serial port and the live image's sos-vm-test.service writes "SOS-MARK <uptime> <event>" lines.
Outputs in --out: screens/*.png, serial.log, report.json, report.md (for GITHUB_STEP_SUMMARY).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import image  # noqa: E402
import keys  # noqa: E402
from qmp import QMPClient, QMPError, QMPTimeout  # noqa: E402

ACTIONS = {"sleep", "screenshot", "wait_screen", "wait_serial", "key", "type", "click", "eject", "reset"}
# The guest's display adapter (vm.display): virtio-gpu (Mesa renders on the CPU by itself), the VMware
# SVGA II adapter that VirtualBox and VMware give a guest (vmwgfx without 3D), QEMU's standard VGA
# (bochs-drm, no render node) — the last two draw in software (packages/svoya-session gpu-env).
DISPLAYS = {"virtio", "vmware", "std"}
OVMF_DIRS = ["/usr/share/OVMF", "/usr/share/ovmf", "/usr/share/edk2/ovmf", "/usr/share/edk2-ovmf/x64",
             "/usr/share/qemu"]
OVMF_SETS = {
    "uefi": [("OVMF_CODE_4M.fd", "OVMF_VARS_4M.fd"), ("OVMF_CODE.fd", "OVMF_VARS.fd")],
    "uefi-sb": [("OVMF_CODE_4M.secboot.fd", "OVMF_VARS_4M.ms.fd"), ("OVMF_CODE.secboot.fd", "OVMF_VARS.ms.fd")],
}


class StepFailed(Exception):
    pass


# ---------------------------------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------------------------------
def load_plan(path: pathlib.Path) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8"))
    validate_plan(plan)
    return plan


def validate_plan(plan: dict) -> None:
    if not isinstance(plan.get("steps"), list) or not plan["steps"]:
        raise ValueError("plan needs a non-empty 'steps' list")
    display = plan.get("vm", {}).get("display", "virtio")
    if display not in DISPLAYS:
        raise ValueError(f"vm.display must be one of {sorted(DISPLAYS)}, not {display!r}")
    names = set()
    for n, step in enumerate(plan["steps"], 1):
        action = step.get("action")
        if action not in ACTIONS:
            raise ValueError(f"step {n}: unknown action {action!r}")
        if action == "screenshot":
            name = step.get("name")
            if not name or not re.fullmatch(r"[A-Za-z0-9._-]+", name):
                raise ValueError(f"step {n}: screenshot needs a file-safe 'name'")
            if name in names:
                raise ValueError(f"step {n}: duplicate screenshot name {name}")
            names.add(name)
        if action == "key":
            keys.parse_combo(step.get("keys", []))
        if action == "type":
            keys.text_to_combos(step.get("text", ""))
        if action == "wait_serial":
            re.compile(step["pattern"])
            if "fail_pattern" in step:
                re.compile(step["fail_pattern"])
        if action == "sleep" and not isinstance(step.get("seconds"), (int, float)):
            raise ValueError(f"step {n}: sleep needs 'seconds'")
        if action == "click":
            at = step.get("at")
            if not (isinstance(at, list) and len(at) == 2 and all(isinstance(v, (int, float)) for v in at)):
                raise ValueError(f"step {n}: click needs 'at': [x, y] in screenshot pixels")


# ---------------------------------------------------------------------------------------------------
# QEMU
# ---------------------------------------------------------------------------------------------------
def find_ovmf(kind: str) -> tuple[str, str] | None:
    for code, varsf in OVMF_SETS[kind]:
        for d in OVMF_DIRS:
            c, v = os.path.join(d, code), os.path.join(d, varsf)
            if os.path.exists(c) and os.path.exists(v):
                return c, v
    return None


def kvm_usable() -> bool:
    return os.access("/dev/kvm", os.R_OK | os.W_OK)


def display_args(display: str, xres: int, yres: int) -> list[str]:
    if display == "virtio":
        return ["-vga", "none", "-device", f"virtio-vga,xres={xres},yres={yres}"]
    return ["-vga", display]        # vmware, std: the guest picks its mode


def qemu_command(args: argparse.Namespace, plan: dict, out: pathlib.Path, vars_copy: str | None,
                 code: str | None, disk: str | None = None) -> list[str]:
    vm = plan.get("vm", {})
    if args.accel == "auto":
        # /dev/kvm can be accessible and still fail to initialise (nested virtualisation off):
        # "kvm:tcg" falls back instead of aborting; main() asks QEMU which one it got (query-kvm).
        accel = "kvm:tcg" if kvm_usable() else "tcg"
    else:
        accel = args.accel
    xres, yres = vm.get("resolution", [1440, 900])
    machine = "q35" + (",smm=on" if args.firmware == "uefi-sb" else "")
    cmd = [args.qemu, "-name", "sos-vm-test", "-machine", f"{machine},accel={accel}",
           # "host" needs KVM; "max" is the host model under KVM and everything TCG can emulate otherwise
           "-cpu", "host" if accel == "kvm" else "max",
           "-smp", str(args.smp or vm.get("smp", 4)), "-m", str(args.memory or vm.get("memory_mib", 6144)),
           "-smbios", f"type=1,manufacturer=SOS,product={vm.get('smbios_product', 'sos-vm-test')}",
           *display_args(vm.get("display", "virtio"), xres, yres),
           "-display", "none",
           "-drive", f"file={args.iso},media=cdrom,if=none,id=cd0,readonly=on",
           "-device", "ide-cd,drive=cd0,bus=ide.0,bootindex=0,id=cdrom",
           "-device", "qemu-xhci", "-device", "usb-tablet",
           "-nic", "user,model=virtio-net-pci",
           "-serial", f"file:{out / 'serial.log'}",
           "-qmp", f"unix:{out / 'qmp.sock'},server=on,wait=off"]
    if disk:
        # an empty NVMe disk to install onto; it boots once the ISO is ejected ("eject", "reset")
        cmd += ["-drive", f"file={disk},if=none,id=hd0,format=qcow2,cache=unsafe",
                "-device", "nvme,drive=hd0,serial=SOS-VM-TEST,bootindex=1"]
    if not vm.get("reboot"):
        cmd += ["-no-reboot"]           # a reboot ends the test run, unless the plan expects one
    if args.firmware in ("uefi", "uefi-sb"):
        cmd += ["-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={code}",
                "-drive", f"if=pflash,format=raw,unit=1,file={vars_copy}"]
        if args.firmware == "uefi-sb":
            cmd += ["-global", "driver=cfi.pflash01,property=secure,value=on"]
    return cmd


# ---------------------------------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------------------------------
class Runner:
    def __init__(self, qmp: QMPClient, out: pathlib.Path, scale: float, proc: subprocess.Popen | None,
                 resolution: tuple[int, int] = (1440, 900)):
        self.qmp = qmp
        self.out = out
        self.scale = scale
        self.proc = proc
        self.resolution = resolution
        self.shots: dict[str, image.Image] = {}
        self.results: list[dict] = []
        (out / "screens").mkdir(parents=True, exist_ok=True)

    def serial(self) -> str:
        try:
            return (self.out / "serial.log").read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ""

    def grab(self) -> image.Image:
        ppm = self.out / "screen.ppm"
        self.qmp.screendump(str(ppm))
        for _ in range(50):  # QEMU writes the file asynchronously on some versions
            if ppm.exists() and ppm.stat().st_size > 0:
                break
            time.sleep(0.1)
        img = image.parse_ppm(ppm.read_bytes())
        ppm.unlink(missing_ok=True)
        return img

    def poll_interval(self) -> float:
        return min(1.0, max(0.05, self.scale))

    def alive(self) -> None:
        if self.proc is not None and self.proc.poll() is not None:
            raise StepFailed(f"QEMU exited with code {self.proc.returncode}")

    # -- actions ----------------------------------------------------------------------------------
    def do_sleep(self, step: dict) -> str:
        time.sleep(step["seconds"] * (self.scale if step.get("scale", True) else 1))
        return f"slept {step['seconds']}s"

    def do_screenshot(self, step: dict) -> str:
        img = self.grab()
        name = step["name"]
        path = self.out / "screens" / f"{name}.png"
        how = image.write_png(img, str(path))
        self.shots[name] = img
        note = f"{img.width}x{img.height} ({how})"
        if step.get("assert") == "not_blank" and image.is_blank(img):
            raise StepFailed(f"{name}: the screen is blank")
        ref = step.get("expect_change_from")
        if ref and ref in self.shots:
            d = image.difference(self.shots[ref], img)
            note += f", {d:.1%} changed vs {ref}"
            if d < step.get("min_change", 0.005):
                msg = f"{name}: screen did not change after the key press (vs {ref})"
                if step.get("strict", False):
                    raise StepFailed(msg)
                note += " — WARNING: " + msg
        return note

    def do_wait_screen(self, step: dict) -> str:
        time.sleep(step.get("min_delay_s", 0) * self.scale)
        deadline = time.monotonic() + step.get("timeout_s", 60) * self.scale
        while time.monotonic() < deadline:
            self.alive()
            img = self.grab()
            if not image.is_blank(img):
                return f"screen has content ({1 - image.dominant_fraction(img):.1%} non-background)"
            time.sleep(self.poll_interval())
        raise StepFailed("timed out waiting for the screen to show something")

    def do_wait_serial(self, step: dict) -> str:
        """Wait for a line on the serial log. "count": N waits for the Nth match (a pattern that
        repeats, e.g. one journal line per Jackson answer); "fail_pattern" counts the same way."""
        pat = re.compile(step["pattern"])
        fail = re.compile(step["fail_pattern"]) if step.get("fail_pattern") else None
        want = int(step.get("count", 1))
        deadline = time.monotonic() + step.get("timeout_s", 300) * self.scale
        while time.monotonic() < deadline:
            self.alive()
            text = self.serial()
            # every success and failure in order of appearance; the Nth one decides
            events = sorted([(m.start(), True) for m in pat.finditer(text)]
                            + ([(m.start(), False) for m in fail.finditer(text)] if fail else []))
            if len(events) >= want:
                at, ok = events[want - 1]
                end = text.find("\n", at)
                line = text[text.rfind("\n", 0, at) + 1:end if end >= 0 else None].strip()[:200]
                if not ok:
                    raise StepFailed(f"serial reported failure: {line!r}")
                return f"matched {line!r}" + (f" (#{want})" if want > 1 else "")
            time.sleep(self.poll_interval())
        raise StepFailed(f"timed out waiting for serial pattern {pat.pattern!r}" + (f" (#{want})" if want > 1 else ""))

    def do_key(self, step: dict) -> str:
        combo = keys.parse_combo(step["keys"])
        self.qmp.send_key(combo, step.get("hold_ms", 100))
        return "+".join(combo)

    def do_click(self, step: dict) -> str:
        """Click at [x, y] of the screenshots (the last one's size; the plan's resolution before any)."""
        x, y = step["at"]
        last = next(reversed(self.shots.values()), None)
        w, h = (last.width, last.height) if last else tuple(self.resolution)
        self.qmp.pointer(x, y, w, h, step.get("button", "left"))
        return f"clicked {x},{y} of {w}x{h}"

    def do_eject(self, step: dict) -> str:
        self.qmp.eject("cdrom")
        return "ejected the ISO"

    def do_reset(self, step: dict) -> str:
        self.qmp.reset()
        return "reset"

    def do_type(self, step: dict) -> str:
        for combo in keys.text_to_combos(step["text"]):
            self.qmp.send_key(combo, 50)
            time.sleep(0.05)
        return f"typed {len(step['text'])} characters"

    def run(self, steps: list[dict]) -> bool:
        ok = True
        for n, step in enumerate(steps, 1):
            action = step["action"]
            started = time.monotonic()
            entry = {"n": n, "id": step.get("id", action), "action": action, "optional": bool(step.get("optional"))}
            try:
                self.alive()
                entry["detail"] = getattr(self, f"do_{action}")(step)
                entry["status"] = "ok"
            except (StepFailed, QMPError, QMPTimeout, ConnectionError, ValueError, OSError) as exc:
                entry["status"] = "skipped" if step.get("optional") else "failed"
                entry["detail"] = str(exc)
                if not step.get("optional"):
                    ok = False
                    self.evidence(f"fail-{n:02d}-{entry['id']}")
            entry["seconds"] = round(time.monotonic() - started, 1)
            self.results.append(entry)
            print(f"[{entry['status']:>7}] {n:2d} {entry['id']:<12} {action:<11} {entry['detail']}", flush=True)
            # stop at a failed step unless it says to go on (earlier failures do not stop later steps)
            if entry["status"] == "failed" and not step.get("continue_on_failure"):
                break
        return ok

    def evidence(self, name: str) -> None:
        try:
            image.write_png(self.grab(), str(self.out / "screens" / f"{name}.png"))
        except Exception as exc:  # noqa: BLE001 - best effort, the VM may be gone
            print(f"(no failure screenshot: {exc})", file=sys.stderr)


def write_reports(out: pathlib.Path, meta: dict, results: list[dict], ok: bool) -> None:
    (out / "report.json").write_text(json.dumps({**meta, "ok": ok, "steps": results}, indent=1) + "\n")
    lines = [f"### VM test: {meta['plan']} ({meta['firmware']}, {meta['accel']}) — {'passed' if ok else 'FAILED'}",
             "", "| # | step | action | status | time | detail |", "|---|---|---|---|---|---|"]
    for r in results:
        detail = str(r.get("detail", "")).replace("|", "\\|")[:160]
        lines.append(f"| {r['n']} | {r['id']} | {r['action']} | {r['status']} | {r['seconds']}s | {detail} |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Boot the SOS ISO in QEMU and run a screenshot plan.")
    ap.add_argument("--iso", required=True)
    ap.add_argument("--plan", default=str(HERE / "plan.json"))
    ap.add_argument("--firmware", choices=("uefi", "uefi-sb", "bios"), default="uefi")
    ap.add_argument("--out", default="dist/vm")
    ap.add_argument("--accel", choices=("auto", "kvm", "tcg"), default="auto")
    ap.add_argument("--memory", type=int)
    ap.add_argument("--smp", type=int)
    ap.add_argument("--qemu", default="qemu-system-x86_64")
    ap.add_argument("--timeout-scale", type=float, default=None,
                    help="multiply waits/timeouts (default 1 with KVM, 4 with TCG)")
    ap.add_argument("--dry-run", action="store_true", help="validate the plan and print the QEMU command")
    args = ap.parse_args(argv)

    plan_path = pathlib.Path(args.plan)
    plan = load_plan(plan_path)
    out = pathlib.Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    code = vars_copy = None
    if args.firmware != "bios":
        found = find_ovmf(args.firmware)
        if found is None and not args.dry_run:
            print(f"OVMF firmware for {args.firmware} not found (apt install ovmf)", file=sys.stderr)
            return 2
        code, varsf = found or ("OVMF_CODE.fd", "OVMF_VARS.fd")
        vars_copy = str(out / "OVMF_VARS.fd")
        if found:
            shutil.copyfile(varsf, vars_copy)
    disk = None
    if plan.get("vm", {}).get("disk_gib"):
        disk = str(out / "disk.qcow2")
        if not args.dry_run:
            subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", disk, f"{int(plan['vm']['disk_gib'])}G"],
                           check=True)
    cmd = qemu_command(args, plan, out, vars_copy, code, disk)
    accel = "kvm" if "accel=kvm" in " ".join(cmd) else "tcg"
    scale = args.timeout_scale or (1.0 if accel == "kvm" else 4.0)
    if args.dry_run:
        print(" ".join(cmd))
        print(f"plan {plan_path.name}: {len(plan['steps'])} steps ok; timeout scale {scale}")
        return 0
    if not os.path.exists(args.iso):
        print(f"ISO not found: {args.iso}", file=sys.stderr)
        return 2

    (out / "serial.log").write_text("")
    (out / "qemu-command.txt").write_text(" ".join(cmd) + "\n")
    qemu_log = open(out / "qemu.log", "w")
    proc = subprocess.Popen(cmd, stdout=qemu_log, stderr=subprocess.STDOUT)
    ok = False
    runner = None
    try:
        qmp = QMPClient.connect_unix(str(out / "qmp.sock"), timeout=30, wait=30)
        qmp.negotiate()
        if accel == "kvm":
            try:
                kvm_enabled = bool((qmp.execute("query-kvm") or {}).get("enabled"))
            except QMPError:
                kvm_enabled = True  # cannot tell; keep the KVM timing
            if not kvm_enabled:
                accel = "tcg"
                if args.timeout_scale is None:
                    scale = 4.0
                print(f"KVM did not initialise; running under TCG (timeout scale {scale})", flush=True)
        runner = Runner(qmp, out, scale, proc, tuple(plan.get("vm", {}).get("resolution", [1440, 900])))
        ok = runner.run(plan["steps"])
        qmp.quit()
    finally:
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        qemu_log.close()
        meta = {"plan": plan.get("name", plan_path.stem), "firmware": args.firmware, "accel": accel,
                "iso": os.path.basename(args.iso)}
        write_reports(out, meta, runner.results if runner else [], ok)
    print(f"{'PASSED' if ok else 'FAILED'} — screenshots in {out / 'screens'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
