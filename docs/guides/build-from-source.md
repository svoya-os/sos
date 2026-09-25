# Building SOS from source

Everything in SOS builds from this repository: the `svoya-*` packages, the ISO, the installer,
and the tests CI runs on every push. Each component's README has the details; this page is the
map.

## Get the source

```sh
git clone https://github.com/svoya-os/sos.git
cd sos
```

## What you need

- **Linux with Docker**, or **Windows 11 with WSL2 and Docker** (see [below](#on-windows)). The
  packages and the ISO are built inside disposable `ubuntu:26.04` containers, so your own
  distribution does not matter.
- About **40 GB of free disk space**, 8 GB of memory and an internet connection (the Ubuntu
  archive is pinned to a snapshot, so builds are reproducible).
- **Python 3.12 or newer** for the tools and the tests. The runtime code uses the standard library
  only; nothing needs to be installed from PyPI.
- Optional: [`just`](https://github.com/casey/just) for the short recipes below, `qemu-system-x86`
  and `ovmf` for VM tests, Playwright for rendering the design mockups, `reuse` for license
  checks.

## Build the packages and the ISO

```sh
packages/build-all.sh      # every .deb (svoya-*, quickshell, uv, grub-btrfs, upsil) → dist/repo
image/docker-build.sh      # the ISO → dist/iso/sos-26.10-amd64.iso
# or: just all
```

The first package build takes 30–60 minutes (Quickshell is compiled), the ISO another 40–70.
UpsiL (the `upsil` package) comes from the commit of [svoya-os/upsil](https://github.com/svoya-os/upsil)
pinned in `packages/versions.env`; it is optional, so if that commit cannot be fetched the build warns
and the ISO goes without it. `UPSIL_SRC_DIR=../upsil packages/build-all.sh --only upsil` packages a
local checkout instead.
`image/README.md` explains the pipeline, the build switches (archive snapshot, NVIDIA driver pool,
compression) and the offline driver pool; `packages/` has one directory per package.

Checks that need neither root nor network:

```sh
packages/build-all.sh --dry-run
image/build-iso.sh --dry-run    # validates the package lists, hooks and boot menu
```

### On Windows

Install Ubuntu from the Microsoft Store (WSL2), enable Docker Desktop's WSL integration (or install
`docker.io` inside WSL) and clone the repository **inside the WSL file system** (`~/sos`, not
`/mnt/c/...`: NTFS breaks permissions and is slow). Then run the same commands.

## Boot the ISO in a virtual machine

```sh
just test-vm uefi              # or uefi-sb, bios
python3 tests/vm/run.py --iso dist/iso/sos-26.10-amd64.iso --firmware uefi --out dist/vm-uefi
```

This is what CI does for every build: QEMU with KVM, driven over QMP, with screenshots of the boot
menu, the boot splash, the live desktop, the launcher and Jackson in `dist/vm-*/`. Plans live in
`tests/vm/`: `plan.json` is the smoke test, `journeys.json` walks through the system like a new
user (cheat sheet, search, terminal with `sos` commands, accent change and undo, Jackson, control
center, Doctor, lock screen).

For hands-on testing without a local VM, the **Live VM** workflow (Actions → Live VM) boots the ISO
of an earlier run and shows its screen in the browser through noVNC; `tests/vm/live.py` explains
how the link is kept private.

To try the ISO yourself, see the [install guide](install.md).

## Run parts of SOS from a checkout

### The `sos` command

The installed command is `sos` (with `svoya` as an alias). In a checkout, its entry point is
`cli/bin/sos`: it finds the code next to it and reads `themes/` and `modules/` from the
repository.

```sh
cli/bin/sos --help
cli/bin/sos status --json      # what the bar shows
cli/bin/sos gpu                # GPU Doctor
cli/bin/sos models suggest     # which local model fits this machine
cli/bin/sos theme list
```

To experiment without touching your real system, point the system paths somewhere else:

```sh
export SVOYA_ROOT=/tmp/sos-root          # /etc/svoya, /var/lib/svoya… resolve under this
export SVOYA_AI_ROOT=/tmp/sos-root/ai    # instead of /srv/ai
```

### Jackson

```sh
jackson/bin/jacksond &                    # the background service
jackson/bin/j "what can you do?"          # ask from the terminal
jackson/bin/j route "summarize this repo" # which model would answer, and why
```

Without a local model or a cloud key, Jackson says so and how to get one (`sos models suggest`).
[`jackson/README.md`](../../jackson/README.md) covers the protocol, routing, permissions,
personas and the audit log.

### Svoya Shell

Inside a Hyprland session with Quickshell 0.3 installed:

```sh
cli/bin/sos theme apply graphite               # writes ~/.local/state/svoya/theme.json
SVOYA_SHELL_DEV=1 quickshell -p shell/         # live reload on file changes
quickshell -p shell/setup                      # the first-run wizard
```

`shell/shell.qml` is the entry point; the login screen lives in `shell/greeter/` and runs under
greetd; `shell/CHECKLIST.md` records what has been verified and how.

## Tests

Unit tests use `unittest`, never touch the network, and live next to each component. From the
repository root:

```sh
(cd cli && python3 -m unittest discover -s tests -t .)
(cd jackson && python3 -m unittest discover -s tests -t .)
python3 -m unittest discover -s tests/vm
python3 -m unittest discover -s installer/tests
python3 -m unittest discover -s image/tests
scripts/lint.sh                 # shell syntax, YAML, JSON, QML (shell/tools/qmlcheck.py), Python
```

`shell/tools/qmlcheck.py` checks the QML statically against the Quickshell 0.3.1 / Qt 6.10 API,
including the names QML refuses (a property or signal called like a JavaScript global, two
members with one name): one such mistake keeps the whole shell from starting. Run it after every
QML change. `reuse lint` checks the license headers. [CONTRIBUTING.md](../../CONTRIBUTING.md) has
the full coding standards.

## Design mockups

`design/mockups/*.html` are the reference for every screen. Render them to PNG with Playwright:

```sh
python3 design/render_all.py            # every screen in every theme → design/out/
python3 design/render_all.py greeter    # one page
```

## Next

- [CONTRIBUTING.md](../../CONTRIBUTING.md): how to send changes.
- [ARCHITECTURE.md](../ARCHITECTURE.md): how the parts fit together.
- [Roadmap](../ROADMAP.md): what is being built now.
