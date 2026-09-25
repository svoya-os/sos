# Installing SOS

> **Status: pre-alpha.** There is no official release yet. But every change on `main` is built
> into an ISO and boot-tested in a virtual machine (BIOS, UEFI and UEFI with Secure Boot), so a
> fresh test build can be tried today. Start with a virtual machine: nothing on your computer
> changes.
>
> По-русски: [docs/ru/install.md](../ru/install.md).

**In short:**

1. [Download the image](#1-download-the-image): a release or a fresh test build.
2. [Join the parts and verify](#2-join-the-parts-and-verify-the-image): two commands.
3. [Run it in a virtual machine](#3-try-it-in-a-virtual-machine) or
   [write it to a USB stick](#4-write-the-image-to-a-usb-stick).
4. In the live session, press [«Install SOS»](#6-install-sos).

## What you need

| | Minimum | Recommended |
|---|---|---|
| Computer | 64-bit PC (amd64), UEFI or BIOS | UEFI |
| Memory | 8 GB (6 GB for a VM) | 16 GB or more for local AI |
| Disk | SSD, 64 GB free | 256 GB or more: models take space (a small language model needs about 5 GB, image and video models 10–30 GB each) |
| GPU | none | see the [hardware table](../../README.md#hardware) |
| USB stick | 8 GB | |
| Internet | not needed to install | needed later to download models and apps |

## 1. Download the image

The image is about 3 GB. GitHub does not take files over 2 GB, so it comes in **parts**:
`sos-26.10-amd64.iso.part00`, `.part01` and a checksum file, `SHA256SUMS`. Put them all in one
folder.

### Option A: a release

Open [GitHub Releases](https://github.com/svoya-os/sos/releases) and download every `.iso.part*`,
`SHA256SUMS` and `SHA256SUMS.asc` (the signature) from the latest release. The first release comes
with v0.1 «Первый сигнал» (First Signal); until then the page may be empty, so use option B.

### Option B: a fresh test build

1. Sign in to GitHub: build artifacts can only be downloaded with an account (a free one is fine).
2. Open [Actions → ISO](https://github.com/svoya-os/sos/actions/workflows/iso.yml).
3. Pick the top run with a green check ✓ (branch `main`).
4. At the bottom of the page, under **Artifacts**, click **sos-iso**: a zip file downloads.
5. Unzip it: inside are the image parts, `SHA256SUMS` and a short README.

Test builds are kept for 7 days. If a run has no artifact, take a newer one.

## 2. Join the parts and verify the image

If the image came as a single `.iso` file, there is nothing to join: just check the sum.

**Windows.** Open the folder, Shift + right-click an empty spot → *Open PowerShell window here*
(or *Open in Terminal*) and run:

```powershell
cmd /c copy /b sos-26.10-amd64.iso.part00 + sos-26.10-amd64.iso.part01 sos-26.10-amd64.iso
Get-FileHash sos-26.10-amd64.iso -Algorithm SHA256
```

With more than two parts, list them all with `+`, in order. Compare the hash with the
`sos-26.10-amd64.iso` line in `SHA256SUMS` (open it in Notepad; letter case does not matter). If
they match, the image is intact.

**Linux:**

```sh
cat sos-26.10-amd64.iso.part* > sos-26.10-amd64.iso
sha256sum --check --ignore-missing SHA256SUMS
```

**macOS:** `cat sos-26.10-amd64.iso.part* > sos-26.10-amd64.iso`, then
`shasum -a 256 sos-26.10-amd64.iso` and compare with `SHA256SUMS`.

A mismatch means a file did not download completely. Download it again.

Releases are signed: `gpg --verify SHA256SUMS.asc SHA256SUMS` confirms the files come from us.
The key fingerprint will be published in this repository with the first release.

## 3. Try it in a virtual machine

The calmest way to get to know SOS: a live session in a VM touches nothing on your computer.
Without 3D, a VM draws the desktop on the CPU, so give it 4 cores.

### VirtualBox 7 (Windows, Linux, Intel Macs)

1. **Machine → New.** Name: `SOS`. ISO image: pick `sos-26.10-amd64.iso`. Type: *Linux*,
   version: *Ubuntu (64-bit)*. Check **Skip Unattended Installation**.
2. **Hardware:** 8192 MB of memory (at least 6144), 4 processors, check **Enable EFI**.
3. **Hard disk:** 64 GB if you want to try installing. The live session needs no disk.
4. Once the machine exists: **Settings → Display**: 128 MB of video memory, graphics controller
   **VMSVGA**, **3D acceleration** off. In VirtualBox SOS draws on the CPU anyway: with 3D the
   Hyprland compositor does not start there, so the system switches to software rendering by
   itself.
5. **Start.** Press Enter in the boot menu. The desktop appears in 20–60 seconds.

Screen stays black (or shows "Hyprland has crashed" instead of a desktop)? Restart the VM and pick
**SOS (safe graphics)** in the menu.

### Hyper-V (Windows 10/11 Pro)

Create a **Generation 2** machine, choose the Secure Boot template **Microsoft UEFI Certificate
Authority**, give it 8 GB and **turn dynamic memory off** (it gets in the live session's way),
and attach the ISO as a DVD.

### Linux: GNOME Boxes, virt-manager, QEMU

GNOME Boxes: "+" → *Install from file* → the ISO, 8 GB of memory. virt-manager: a new machine
from the ISO, OS *Ubuntu 26.04*, firmware *UEFI*. Or straight from a terminal, the way CI runs
SOS:

```sh
cp /usr/share/OVMF/OVMF_VARS_4M.fd /tmp/sos-vars.fd
qemu-system-x86_64 -machine q35,accel=kvm -cpu host -smp 4 -m 8G \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive if=pflash,format=raw,file=/tmp/sos-vars.fd \
  -vga none -device virtio-vga -cdrom sos-26.10-amd64.iso
```

## 4. Write the image to a USB stick

Everything on the stick will be erased.

- **Windows:** [Rufus](https://rufus.ie). Pick the stick and the ISO, press *Start*. If Rufus asks
  how to write the image, choose **Write in DD Image mode**.
- **Windows, macOS, Linux:** [balenaEtcher](https://etcher.balena.io): *Flash from file* → the
  stick → *Flash*.
- **Linux:** GNOME Disks → *Restore Disk Image*. Or in a terminal; find the stick with `lsblk`
  first and double-check the device name, because `dd` overwrites whatever you point it at:

  ```sh
  sudo dd if=sos-26.10-amd64.iso of=/dev/sdX bs=4M status=progress oflag=sync
  ```

- **Ventoy** works too: copy the ISO onto a Ventoy stick.

## 5. Boot from the stick

**Back up your data first.** The live session does not touch the disk, the installer does.

1. Plug in the stick and open the boot menu while the computer starts. The key depends on the
   manufacturer: often F12, F11, F8 or Esc.
2. Choose the stick. **Secure Boot can stay on**: SOS boots through a signed chain, and its
   NVIDIA drivers are signed too.
3. In the SOS menu:
   - **SOS 26.10**: the normal start;
   - **safe graphics**: when the screen is black or garbled;
   - **test in RAM**: loads the whole system into memory, after which the stick can be
     removed (needs 8 GB of memory or more);
   - **Language · Язык**: the language of the live session.

You land on the desktop as user `svoya`, with no password. Jackson says hello and offers an
**«Install SOS»** button. Nothing you do in the live session survives a reboot, so try anything:

| Keys | What they do |
|---|---|
| `Super+Space` | search: apps, files, settings |
| `Super+Enter` | terminal |
| `Super+J` | Jackson |
| `Super+K` | every shortcut |
| `Super+A` | control center |
| `Super+Esc` | Doctor: system check |
| `Super+Alt+A` | accessibility (larger text, contrast) |

Check the GPU before installing: open a terminal and run `sos gpu`.

## 6. Install SOS

Press **«Install SOS»** in Jackson's greeting, or find the installer with `Super+Space`
("install"). It asks for:

1. **Language, time zone and keyboard.**
2. **Disk:**
   - *Erase disk* is the simplest choice. SOS sets up Btrfs with snapshots, which undo relies on.
   - *Install alongside* keeps your other system (dual boot).
   - *Manual partitioning*: keep Btrfs for the system partition, or snapshots and undo will not
     work.
   - **Encryption** is optional and recommended for laptops. You will type the passphrase at
     every start; keep it somewhere safe, because without it the data cannot be recovered.
3. **Your account:** name and password. There is no online account, now or later.

Installing takes 10–20 minutes and needs no internet: drivers come from the pool on the image.
When it is done, restart and remove the stick.

**Dual boot with Windows:** turn off *Fast Startup* in Windows first, and make space by shrinking
the Windows partition from Windows (Disk Management). If Windows uses BitLocker, have your recovery
key at hand: changing boot settings can make Windows ask for it.

## 7. First start

The login screen appears: Jackson stands on the line and waits for your password. After you log
in, the first-run wizard opens: up to 7 steps, each one can be skipped, and everything can be
changed later in Settings:

1. Accessibility (always at hand with `Super+Alt+A`).
2. Language and keyboard.
3. Look: Graphite, Paper, Auto (Graphite at night, Paper by day) or Phosphor, and the accent color.
4. Window layout: floating windows, a classic taskbar, or tiling.
5. Profile: Newcomer, Creator, ML Engineer, Agent Builder or Hacker, optionally "offline only".
6. Jackson: his look and his humor, and **one local model** that fits your GPU and memory. It
   downloads only when you press the button, not before.
7. Privacy, the first system snapshot and the shortcut cheat sheet.

Next: [first steps](first-steps.md) · [FAQ](faq.md).

## Updates and rollback

- **Update the system:** `sos update` (a snapshot is taken first).
- **Undo the last change:** `Super+Z` or `sos undo`.
- **Something broke after an update:** the boot menu has "yesterday's system", a snapshot you
  can boot and roll back to.
- **Test builds** are updated only by reinstalling for now: download a fresh image and install it
  again (back up `/home` first).

## Troubleshooting

- **Black screen with an NVIDIA card:** start with *safe graphics*, log in, run `sos gpu`, then
  `sos fix`.
- **"Secure Boot violation" at start:** some computers trust only Windows by default. In the
  firmware settings, allow the *Microsoft third-party UEFI CA* (the exact name varies by
  manufacturer), then try again.
- **The VM is slow:** give it 4 cores and 8 GB of memory. In VirtualBox and VMware the desktop is
  drawn on the CPU (3D acceleration does not help there), so SOS is much faster on real hardware.
- **The installer does not see the SSD:** if the firmware settings show the storage controller in
  Intel RST or RAID mode, switch it to AHCI. Windows needs preparation first, so look up how to do
  it for your machine.
- **No Wi-Fi:** use a cable or USB tethering from your phone, and send us a
  [hardware report](https://github.com/svoya-os/sos/issues/new?template=hardware.yml).
- **Something else:** [open a bug report](https://github.com/svoya-os/sos/issues/new?template=bug.yml)
  and attach the output of `sos doctor`: it shows the state of the system at a glance.

Building the image yourself: [build-from-source.md](build-from-source.md).
