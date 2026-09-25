#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A live SOS VM for hands-on testing: boot the ISO in QEMU (KVM), show its screen through noVNC
and a Cloudflare quick tunnel, and keep it up for a while. Used by .github/workflows/live-vm.yml.

    python3 tests/vm/live.py --iso sos.iso --out dist/live --minutes 150 --pubkey-b64 <DER, base64>

The tunnel link is never printed: it is encrypted (RSA-OAEP-SHA256) with the public key given by
whoever started the run, so only they can open the VM. The run writes
    <out>/session.txt   run facts + the encrypted link (safe to publish)
    <out>/serial.log    the VM's serial console (SOS-MARK milestones, SOS-DIAG blocks)
    <out>/screens/      a QMP screenshot every few minutes
An empty 48 GB disk is attached (virtio) so the installer can be tried end to end.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import image  # noqa: E402
import run as vmrun  # noqa: E402
from qmp import QMPClient  # noqa: E402

TUNNEL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
NOVNC_DIRS = ["/usr/share/novnc", "/usr/share/webapps/novnc"]


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def encrypt_link(link: str, pubkey_b64: str) -> str:
    """RSA-OAEP(SHA-256) with the given SubjectPublicKeyInfo (DER, base64) → base64 ciphertext."""
    with tempfile.TemporaryDirectory() as tmp:
        der = pathlib.Path(tmp, "pub.der")
        der.write_bytes(base64.b64decode(pubkey_b64.strip(), validate=True))
        pem = pathlib.Path(tmp, "pub.pem")
        subprocess.run(["openssl", "pkey", "-pubin", "-inform", "DER", "-in", str(der), "-out", str(pem)],
                       check=True, capture_output=True)
        out = subprocess.run(["openssl", "pkeyutl", "-encrypt", "-pubin", "-inkey", str(pem),
                              "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256",
                              "-pkeyopt", "rsa_mgf1_md:sha256"],
                             input=link.encode(), check=True, capture_output=True)
        return base64.b64encode(out.stdout).decode()


def qemu_argv(args: argparse.Namespace, out: pathlib.Path) -> list[str]:
    plan = {"vm": {"memory_mib": args.memory, "smp": args.smp, "resolution": [1440, 900],
                   "smbios_product": "sos-vm-test"}}
    code = vars_copy = None
    if args.firmware != "bios":
        found = vmrun.find_ovmf(args.firmware)
        if found is None:
            raise SystemExit(f"OVMF for {args.firmware} not found (apt install ovmf)")
        code, varsf = found
        vars_copy = str(out / "OVMF_VARS.fd")
        shutil.copyfile(varsf, vars_copy)
    ns = argparse.Namespace(iso=args.iso, firmware=args.firmware, accel="auto", qemu=args.qemu,
                            memory=args.memory, smp=args.smp)
    cmd = vmrun.qemu_command(ns, plan, out, vars_copy, code)
    # a person drives this VM: let it reboot (installer), show the screen on local VNC only
    cmd = [c for c in cmd if c != "-no-reboot"]
    cmd += ["-vnc", "127.0.0.1:0"]
    if args.disk_gb > 0:
        disk = out / "disk.qcow2"
        subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", str(disk), f"{args.disk_gb}G"], check=True)
        cmd += ["-drive", f"file={disk},if=none,id=hd0,format=qcow2",
                "-device", "virtio-blk-pci,drive=hd0,bootindex=1"]
    return cmd


def start_tunnel(port: int, out: pathlib.Path, cloudflared: str, timeout: float = 90) -> tuple[subprocess.Popen, str]:
    log = open(out / "tunnel.log", "w")
    proc = subprocess.Popen([cloudflared, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
                            stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        m = TUNNEL_RE.search((out / "tunnel.log").read_text(errors="replace"))
        if m:
            return proc, m.group(0)
        if proc.poll() is not None:
            break
        time.sleep(1)
    raise SystemExit("the tunnel did not come up (see tunnel.log)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--out", default="dist/live")
    ap.add_argument("--minutes", type=int, default=150)
    ap.add_argument("--pubkey-b64", required=True, help="RSA public key (SubjectPublicKeyInfo DER, base64)")
    ap.add_argument("--firmware", choices=("uefi", "bios"), default="uefi")
    ap.add_argument("--memory", type=int, default=10240)
    ap.add_argument("--smp", type=int, default=4)
    ap.add_argument("--disk-gb", type=int, default=48)
    ap.add_argument("--qemu", default="qemu-system-x86_64")
    ap.add_argument("--cloudflared", default="cloudflared")
    ap.add_argument("--port", type=int, default=6080)
    ap.add_argument("--shot-every", type=int, default=300, help="seconds between screenshots")
    args = ap.parse_args(argv)

    out = pathlib.Path(args.out).resolve()
    (out / "screens").mkdir(parents=True, exist_ok=True)
    novnc = next((d for d in NOVNC_DIRS if os.path.exists(os.path.join(d, "vnc.html"))), None)
    if novnc is None:
        raise SystemExit("noVNC not found (apt install novnc websockify)")

    # the link is encrypted before anything starts: a bad key fails fast
    encrypt_link("https://check.invalid", args.pubkey_b64)

    (out / "serial.log").write_text("")
    cmd = qemu_argv(args, out)
    (out / "qemu-command.txt").write_text(" ".join(cmd) + "\n")
    procs: list[subprocess.Popen] = []
    qemu = subprocess.Popen(cmd, stdout=open(out / "qemu.log", "w"), stderr=subprocess.STDOUT)
    procs.append(qemu)
    try:
        qmp = QMPClient.connect_unix(str(out / "qmp.sock"), timeout=30, wait=30)
        qmp.negotiate()
        procs.append(subprocess.Popen(["websockify", "--web", novnc, f"127.0.0.1:{args.port}", "127.0.0.1:5900"],
                                      stdout=open(out / "websockify.log", "w"), stderr=subprocess.STDOUT))
        tunnel, link = start_tunnel(args.port, out, args.cloudflared)
        procs.append(tunnel)
        page = link + "/vnc.html?autoconnect=1&resize=scale&reconnect=1&path=websockify"
        until = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=args.minutes)
        (out / "session.txt").write_text(
            f"run: {os.environ.get('GITHUB_RUN_ID', 'local')}\nstarted: {utc()}\n"
            f"until: {until.strftime('%Y-%m-%dT%H:%M:%SZ')}\nfirmware: {args.firmware}\n"
            f"link-rsa-oaep-sha256: {encrypt_link(page, args.pubkey_b64)}\n")
        print(f"live VM up; encrypted link in {out / 'session.txt'}; until {until:%H:%M} UTC", flush=True)

        seen = 0
        next_shot = time.monotonic() + 30
        end = time.monotonic() + args.minutes * 60
        n = 0
        while time.monotonic() < end and qemu.poll() is None:
            text = (out / "serial.log").read_text(errors="replace")
            for line in text[seen:].splitlines():
                if "SOS-MARK" in line:
                    print(line.strip(), flush=True)
            seen = len(text)
            if time.monotonic() >= next_shot:
                n += 1
                try:
                    ppm = out / "screen.ppm"
                    qmp.screendump(str(ppm))
                    time.sleep(0.5)
                    image.write_png(image.parse_ppm(ppm.read_bytes()), str(out / "screens" / f"{n:03d}.png"))
                    ppm.unlink(missing_ok=True)
                except Exception as exc:  # noqa: BLE001 - screenshots are best effort
                    print(f"(screenshot {n}: {exc})", flush=True)
                next_shot = time.monotonic() + args.shot_every
            time.sleep(5)
        print("VM stopped" if qemu.poll() is not None else "time is up", flush=True)
        return 0
    finally:
        for p in reversed(procs):
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
                try:
                    p.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    p.kill()


if __name__ == "__main__":
    sys.exit(main())
