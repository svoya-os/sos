# Building SOS from source

> **Status (2026-09-24):** the ISO build (`image/`), the Debian packaging (`packages/`), the
> installer (`installer/`) and the VM tests (`tests/`) are not in the repository yet. This
> guide describes what already runs from a checkout, and the planned build process. It will be
> completed as those parts land; each component's README will have the exact commands.

## Get the source

```sh
git clone https://github.com/svoya-os/sos.git
cd sos
```

## What you need

- **Linux**, ideally Ubuntu 26.04, the engine SOS is built on.
- **Python 3.12 or newer.** The runtime code uses the standard library only; nothing needs to be
  installed from PyPI.
- For **Svoya Shell**: a Hyprland session with Quickshell.
- For **packages**: `dpkg-dev` and `debhelper` (planned).
- For **the ISO**: `mmdebstrap`, `squashfs-tools` and `xorriso`, about 20 GB of free disk space
  and access to the Ubuntu archive (planned).
- For **VM tests**: `qemu-system-x86` and `ovmf`.
- For **license checks**: the `reuse` tool.

## Run parts of SOS from a checkout

### The `sos` command

The installed command is `sos` (with `svoya` as an alias). In a checkout, its entry point is
`cli/bin/svoya`: it finds the code next to it and reads `themes/` and `modules/` from the
repository.

```sh
python3 cli/bin/svoya --help
python3 cli/bin/svoya status --json      # what the bar shows
python3 cli/bin/svoya doctor --gpu       # GPU Doctor
python3 cli/bin/svoya theme list
```

To experiment without touching your real system, point the system paths somewhere else:

```sh
export SVOYA_ROOT=/tmp/sos-root          # /etc/svoya, /var/lib/svoya… resolve under this
export SVOYA_AI_ROOT=/tmp/sos-root/ai    # instead of /srv/ai
```

### Jackson

Jackson's code lives in `jackson/`. His entry points, the background service and the `j`
command, are being written; instructions will follow in `jackson/`.

### Svoya Shell

Inside a Hyprland session with Quickshell installed, start the shell from the checkout once its
entry file lands:

```sh
quickshell -p shell/
```

The shell reads the theme from `~/.local/state/svoya/theme.json`. Write one with
`python3 cli/bin/svoya theme apply graphite`.

## Tests

Unit tests use `unittest`, never touch the network, and live next to each component:

```sh
cd cli && python3 -m unittest discover -s tests -v
```

Also run `shellcheck` on shell scripts, `qmllint` on QML, and `reuse lint` from the repository
root. [CONTRIBUTING.md](../../CONTRIBUTING.md) has the full coding standards.

## Build the Debian packages (planned)

Every `svoya-*` package has its packaging in `packages/<name>/debian/`. On Ubuntu 26.04, or in
a clean build chroot:

```sh
cd packages/<name>
dpkg-buildpackage -us -uc -b
```

The `sos` command ships in `svoya-cli`, Jackson in `svoya-jackson`, the shell in `svoya-shell`.

## Build the ISO (planned)

The image is built in `image/`, in four stages:

1. `mmdebstrap` creates a minimal Ubuntu 26.04 root file system from the archive.
2. Our packages, the driver pool (NVIDIA current and 580 legacy branches) and the default
   configuration are added. CUDA, cuDNN and model weights are never put on the image, for
   license reasons.
3. The root file system is compressed into a squashfs image.
4. `xorriso` writes a hybrid ISO that boots through the engine's signed boot chain, so it works
   with Secure Boot on. Checksums are written next to it.

## Try the ISO in a virtual machine

UEFI firmware for QEMU comes from the `ovmf` package. Use a writable copy of the variable store:

```sh
cp /usr/share/OVMF/OVMF_VARS_4M.fd /tmp/sos-vars.fd
qemu-system-x86_64 -enable-kvm -machine q35 -m 8G -smp 4 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive if=pflash,format=raw,file=/tmp/sos-vars.fd \
  -cdrom <file>.iso
```

CI does the same for every build: it boots the image in QEMU, drives it over QMP and takes
screenshots.

## Next

- [CONTRIBUTING.md](../../CONTRIBUTING.md): how to send changes.
- [ARCHITECTURE.md](../ARCHITECTURE.md): how the parts fit together.
- [Roadmap](../ROADMAP.md): what is being built now.
