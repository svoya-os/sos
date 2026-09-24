# Installing SOS

> **There is no ISO to download yet.** SOS is pre-alpha, and the first image comes with v0.1
> «Первый сигнал». This guide describes how installation will work, so you can prepare. It will
> be updated with the first release. To try parts of SOS today, see
> [build-from-source.md](build-from-source.md).
>
> По-русски: [docs/ru/install.md](../ru/install.md).

## What you need

| | Minimum | Recommended |
|---|---|---|
| Computer | 64-bit PC (amd64) with UEFI | |
| Memory | 8 GB | 16 GB or more for local AI |
| Disk | SSD, 64 GB free | 256 GB or more: models take space (a small language model needs about 5 GB, image and video models 10–30 GB each) |
| GPU | none | see the [hardware table](../../README.md#hardware) |
| USB stick | 8 GB | |
| Internet | not needed to install | needed later to download models and apps |

These numbers are provisional and will be confirmed with v0.1.

## 1. Download and verify the image

When the first release is out, download the ISO file, `SHA256SUMS` and `SHA256SUMS.sig` from
[GitHub Releases](https://github.com/svoya-os/sos/releases). Then check that the files are
complete and really come from us:

```sh
sha256sum --check --ignore-missing SHA256SUMS
gpg --verify SHA256SUMS.sig SHA256SUMS
```

The fingerprint of the signing key will be published in this repository and on the website.

## 2. Write it to a USB stick

Everything on the stick will be erased.

- **Linux:** GNOME Disks → *Restore Disk Image*. Or in a terminal, after finding the stick with
  `lsblk` (double-check the device name, `dd` overwrites whatever you point it at):

  ```sh
  sudo dd if=<file>.iso of=/dev/sdX bs=4M status=progress oflag=sync
  ```

- **Windows:** [Rufus](https://rufus.ie). If it asks, choose *DD image* mode.
- **macOS:** [balenaEtcher](https://etcher.balena.io).

## 3. Prepare the computer

- **Back up your data.**
- **Secure Boot can stay on.** SOS boots through a signed chain, and its NVIDIA drivers are signed.
- **Dual boot with Windows:** turn off *Fast Startup* in Windows, and make space by shrinking
  the Windows partition from Windows (Disk Management) first. If Windows uses BitLocker, have
  your recovery key at hand: changing boot settings can make Windows ask for it.
- **Disk not visible later?** If the firmware settings show the storage controller in Intel RST
  or RAID mode, the installer may not see your SSD. Switching to AHCI fixes that, but Windows
  needs preparation first, so look up how to do it for your machine before switching.

## 4. Start the live system

1. Plug in the stick and open the boot menu while the computer starts. The key depends on the
   manufacturer: often F12, F11, F8 or Esc.
2. Choose the USB stick. SOS starts as a live system: you can try it without changing anything
   on the disk.
3. Open a terminal (`Super+Enter`) and run `sos gpu`. It shows whether your graphics card and
   its driver are ready before you install.

## 5. Install

Start the installer from the desktop. It asks for:

1. **Language, time zone and keyboard.**
2. **Disk:**
   - *Erase disk* is the simplest choice. SOS sets up Btrfs with snapshots, which undo relies on.
   - *Install alongside* keeps your other system (dual boot).
   - *Manual partitioning*: keep Btrfs for the system partition. Without it, snapshots and undo
     do not work.
   - **Encryption** is optional and recommended for laptops. You will type the passphrase at
     every start, so keep it somewhere safe: without it, the data cannot be recovered.
3. **Your account:** name and password. There is no online account, now or later.

Drivers come from the pool on the image, so no internet connection is needed. When the
installer is done, restart and remove the stick.

## 6. First start

After you log in, the first-run wizard opens. Every step can be skipped, and every choice can be
changed later:

1. Accessibility (always available with `Super+Alt+A`)
2. Language and keyboard
3. Look: Graphite, Paper, Auto (Graphite at night, Paper by day) or Phosphor
4. Layout: clean floating windows, a classic taskbar, or tiling
5. Profile: Newcomer, Creator, ML Engineer, Agent Builder or Hacker, optionally "offline only"
6. AI: the wizard shows the GPU it found and suggests **one local model** that fits your GPU and
   memory. One click installs it; this is the moment it is downloaded, and not before. Here you
   can also install [Obsidian](https://obsidian.md) from Flathub with one click and let Jackson
   keep his memory in your Obsidian vault, and add cloud API keys. All of it is optional.
7. Privacy summary, the first snapshot and the keyboard shortcut cheat sheet.

Next: [first steps](first-steps.md).

## Troubleshooting

- **Black screen with an NVIDIA card:** start again and pick the safe graphics option in the
  boot menu. Once you are in, run `sos gpu`, then `sos fix`.
- **"Secure Boot violation" at start:** some computers trust only Windows by default. In the
  firmware settings, allow the *Microsoft third-party UEFI CA* (the exact name varies by
  manufacturer), then try again.
- **No Wi-Fi:** use a cable or USB tethering from your phone for now, and send us a
  [hardware report](https://github.com/svoya-os/sos/issues/new?template=hardware.yml).
- **Something else:** [open a bug report](https://github.com/svoya-os/sos/issues/new?template=bug.yml).
  Hardware reports help even when everything works.
