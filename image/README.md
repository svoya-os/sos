# SOS image: how the ISO is built

`image/` turns Ubuntu 26.04 LTS packages (the engine) and our own `svoya-*` packages into
`sos-26.10-amd64.iso`: a hybrid BIOS/UEFI live medium with Secure Boot, the SOS live session and
the Calamares installer. The whole build runs as root inside a disposable, privileged `ubuntu:26.04`
container, so the tools (mmdebstrap, GRUB, squashfs-tools, xorriso) match the target release.

## Pipeline

```
packages/build-all.sh ──► dist/repo (flat APT repo: svoya-*, quickshell, uv, grub-btrfs, upsil)
                               │
image/build-iso.sh             ▼
  mmdebstrap --variant=minbase resolute   (snapshot.ubuntu.com/ubuntu/$SNAPSHOT, SOURCE_DATE_EPOCH)
    └─ hooks/NN-*.sh (customize hooks, in order)
         00 apt policy (no recommends, no snapd, Hyprland pinned to 0.53.*, no docs)
         02 local repo (dist/repo)        05 debconf (us,ru Alt+Shift, locales, live groups incl. "ai")
         10 packages/base.list            15 locales en_US+ru_RU, keyboard, hostname, os-release check
         20 Firefox from packages.mozilla.org (fingerprint-checked key; Ubuntu's snap package pinned away)
         30 packages/desktop.list         35 Flathub remote (system-wide, nothing installed)
         40 packages/ai-core.list         50 packages/live.list (casper, calamares, svoya-installer),
                                             live autologin, live-only files list
         70 remove Ubuntu branding/nags/snap (packages/remove.list), SOS boot splash
         75 offline pool (/pool + /dists) + self-test   80 services   85 final APT sources
         90 live initrd (initramfs-tools + casper)       95 cleanup (machine-id, logs, build config)
  → casper/filesystem.squashfs (zstd -19), vmlinuz, initrd, filesystem.{manifest,manifest-remove,size}
  → UEFI: shim (BOOTX64.EFI) + Canonical-signed gcdx64 (grubx64.efi) + mmx64.efi, on an ESP image
          made with mkfs.vfat -C + mtools (no loop devices), appended as GPT partition 2
  → BIOS: GRUB i386-pc El Torito core (grub-mkimage) + boot_hybrid.img MBR
  → xorriso -as mkisofs  →  dist/iso/sos-26.10-amd64.iso (+ .sha256, .manifest, .json)
```

Boot menu (`boot/grub.cfg`, English + Russian once the Unicode font is loaded):
**SOS 26.10**, **SOS (safe graphics · безопасная графика)** (`nomodeset`),
**SOS — test in RAM · проверка в памяти (toram)**, a *Language · Язык* switch for the live
session, UEFI firmware settings, reboot, power off.

The live user is `svoya` (passwordless, in `sudo` and `ai`), host `sos`; greetd logs it straight
into the SOS session. `/etc/svoya/live` marks the live session (the shell shows "Install SOS"
and skips the first-run wizard). Live-only files are listed in `/usr/share/svoya/live-exclude.rsync`
and never copied by the installer; live-only packages (`/usr/share/svoya/live-packages.list`, also
`casper/filesystem.manifest-remove`) are purged from the installed system.

## Build it yourself

Needs Linux with Docker (or Windows 11 with WSL2 + Docker), about 40 GB free, 8 GB RAM, internet.

```sh
git clone https://github.com/svoya-os/sos && cd sos
packages/build-all.sh                 # ~30–60 min the first time (quickshell is compiled)
image/docker-build.sh                 # ~40–70 min; ISO in dist/iso/
# or simply: just packages iso
```

`image/docker-build.sh` runs exactly this (use it directly if you prefer):

```sh
docker run --rm --privileged -v "$PWD":/src -v /var/tmp/sos-iso-work:/work -w /src \
    ubuntu:26.04 bash /src/image/build-iso.sh --work /work --out /src/dist/iso
```

`--privileged` is needed because mmdebstrap (root mode) mounts `/proc`, `/sys` and `/dev` inside the
rootfs and the pool self-test bind-mounts the pool; no loop devices are used.

**Windows (WSL2):** install Ubuntu from the Microsoft Store, enable Docker Desktop's WSL integration
(or install `docker.io` inside WSL), clone the repository **inside the WSL file system**
(`~/sos`, not `/mnt/c/...`; NTFS breaks permissions and is slow) and run the same commands.

Useful switches (environment variables, see `config.env`):

| Variable | Default | Meaning |
|---|---|---|
| `SNAPSHOT` | `20260920T000000Z` | archive snapshot the build is frozen to; `none` = live archive |
| `NVIDIA_BRANCHES` | `595-open 580` | offline driver pool; empty = no pool (`POOL_STRICT=0`) |
| `SQUASHFS_LEVEL` | `19` | zstd level; 15 builds faster, the ISO gets ~5–8 % bigger |
| `SVOYA_WORK_DIR` | `/var/tmp/sos-iso-work` | scratch space (rootfs, ISO tree, pool) |
| `SOS_APT_URL`, `SOS_APT_KEY_FILE` | unset | SOS APT repository for updates of `svoya-*` (when it exists) |

`image/build-iso.sh --dry-run` validates the lists, hooks and boot menu and prints the exact
mmdebstrap and xorriso command lines without root or network.

## Boot the ISO

**QEMU** (the CI way, with screenshots): `just test-vm uefi` / `uefi-sb` / `bios`, or by hand:

```sh
cp /usr/share/OVMF/OVMF_VARS_4M.fd /tmp/vars.fd
qemu-system-x86_64 -machine q35,accel=kvm -cpu host -smp 4 -m 6144 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive if=pflash,format=raw,file=/tmp/vars.fd \
  -vga none -device virtio-vga -cdrom dist/iso/sos-26.10-amd64.iso
```

Hyprland renders with Mesa's software renderer in VMs without 3D; give the VM 4 CPUs and ≥ 6 GB.

**VirtualBox 7:** new VM, type *Linux / Ubuntu (64-bit)*, 6 GB RAM, 4 CPUs, *Enable EFI*, graphics
*VMSVGA* with 3D acceleration on, attach the ISO. Secure Boot can stay on (shim is signed by Microsoft).

**Hyper-V (Windows):** Generation 2 VM, Secure Boot template *Microsoft UEFI Certificate Authority*,
6 GB RAM (disable dynamic memory for the live session), attach the ISO as DVD.

**USB stick:** `sudo dd if=sos-26.10-amd64.iso of=/dev/sdX bs=4M conv=fsync status=progress`
(or Ventoy, balenaEtcher, Rufus in *DD image* mode). The ISO boots from USB on BIOS and UEFI.

Release assets over 2 GiB are split: `cat sos-26.10-amd64.iso.part* > sos-26.10-amd64.iso &&
sha256sum -c --ignore-missing SHA256SUMS`.

## Size

Expected: squashfs ≈ 1.9–2.4 GB, NVIDIA pool ≈ 0.7–0.9 GB (two branches), ISO ≈ 2.7–3.3 GB.
The base stays lean: no CUDA/cuDNN (licenses; `cuda-toolkit-13` is installed later from multiverse),
no llama.cpp/ROCm/models (modules), no documentation except copyright files. `NVIDIA_BRANCHES=595-open`
saves ≈ 0.4 GB; `NVIDIA_BRANCHES=` drops the pool (the installer then needs internet for NVIDIA).
Every build writes the real numbers to `dist/iso/*.iso.json` and the CI summary.

## Offline driver pool

`/pool/<component>/*.deb` + `/dists/resolute/…` on the ISO, used by the installer through a private
APT configuration (the pool is the only source, so nothing touches the network):

* `main`: `grub-efi-amd64-signed` + `shim-signed` (UEFI) or `grub-pc` (BIOS), and `dracut`.
* `nvidia-595-open`: Turing / RTX 20 and newer (incl. Blackwell) — `linux-modules-nvidia-595-open-generic`
  (prebuilt, Canonical-signed: works with Secure Boot, no MOK enrollment) + `nvidia-headless-no-dkms-595-open`
  + GL/decode/encode/FBC libraries + `nvidia-utils-595`. **No DKMS**: `nvidia-driver-595-open` itself
  depends on `nvidia-dkms-595-open`, which would pull a compiler and build unsigned modules.
* `nvidia-580`: the same for Maxwell/Pascal/Volta with the closed 580 modules.
* `pool/svoya-gpu.json`: the PCI modalias patterns of each branch (from the `nvidia-driver-*`
  metapackages' `Modaliases`, the data `ubuntu-drivers` uses); the installer matches the machine
  against them. Without a match and with internet, the installer falls back to `ubuntu-drivers install`.

Hook 75 resolves the pool against the finished rootfs and then simulates every install the installer
will do, offline, against the pool alone — a broken pool fails the build, not the user's install.

## Reproducibility

The archive is frozen with `snapshot.ubuntu.com` (`SNAPSHOT`), `SOURCE_DATE_EPOCH` comes from the last
commit (mmdebstrap, mksquashfs and xorriso honour it) and every third-party input is pinned
(`packages/versions.env`). Not frozen yet: Firefox (packages.mozilla.org has no snapshots) and the
Flathub remote file; FAT timestamps inside the ESP image depend on mtools.

## Decisions (with evidence)

* **casper still needs initramfs-tools on 26.04.** `casper 26.04.2` depends on `initramfs-tools` and ships
  only `/usr/share/initramfs-tools/{hooks,scripts}/casper*`, no dracut module (packages.ubuntu.com,
  resolute file list). The live initrd therefore uses initramfs-tools; the installer swaps the installed
  system to `dracut` (110, the 26.04 default) from the pool.
* **Hyprland comes from the archive.** resolute has `hyprland 0.53.3+ds-4`, `hyprland-dev` and
  `hyprland-plugin-hyprbars 0.53.0-1`, which depends on the virtual `hyprland-abi-6d24081` provided by
  that exact Hyprland build, so the plugin is ABI-matched by the archive (upstream `hyprpm.toml` maps
  all of 0.53.0–0.53.3 to the same hyprland-plugins commit). `svoya-base` pins `hyprland*` to `0.53.*`.
  The SOS Shell's Hyprland config must use 0.53 syntax and load
  `/usr/lib/x86_64-linux-gnu/hyprland/plugins/libhyprbars.so`.
* **Quickshell is built from source** (not in the archive): tag v0.3.1 from the GitHub mirror of
  git.outfoxxed.me, against the archive's Qt 6.10, with a strict dependency on that Qt release
  (private Qt API). `CRASH_HANDLER=OFF` because cpptrace is not packaged.
* **llama.cpp is not built**: resolute has `llama.cpp 8681` and `libggml0-backend-vulkan`; modules install it.
* **uv** is repackaged from the checksum-verified upstream release (not in the archive).
