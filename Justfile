# SOS — common tasks. SPDX-License-Identifier: Apache-2.0
# Install `just` (https://github.com/casey/just), then run `just` to list the recipes.

set shell := ["bash", "-euo", "pipefail", "-c"]

iso_file := "dist/iso/sos-26.10-amd64.iso"

# List the recipes
default:
    @just --list

# Build every .deb (svoya-*, quickshell, uv, grub-btrfs) in ubuntu:26.04 into dist/repo
packages *args:
    packages/build-all.sh {{args}}

# Build the ISO in a privileged ubuntu:26.04 container (needs dist/repo; ~40 GB free in SVOYA_WORK_DIR)
iso *args:
    image/docker-build.sh {{args}}

# Packages + ISO in one go
all: packages iso

# Boot the ISO in QEMU and take the milestone screenshots (firmware: uefi, uefi-sb or bios)
test-vm firmware="uefi" iso=iso_file:
    python3 tests/vm/run.py --iso {{iso}} --firmware {{firmware}} --out dist/vm-{{firmware}}

# Unit tests of the build side (VM harness, installer helpers, image/packaging helpers)
test:
    python3 -m unittest discover -s tests/vm
    python3 -m unittest discover -s installer/tests
    python3 -m unittest discover -s image/tests

# Static checks (shellcheck, YAML, JSON) and dry runs of the builds
lint:
    scripts/lint.sh
    packages/build-all.sh --dry-run
    image/build-iso.sh --dry-run

# Render the design mockups (needs Playwright)
mockups:
    python3 design/render.py

# Remove build output (the ISO work directory lives in SVOYA_WORK_DIR, default /var/tmp/sos-iso-work)
clean:
    rm -rf dist build
    @echo "ISO scratch space: ${SVOYA_WORK_DIR:-/var/tmp/sos-iso-work} (remove it with sudo if needed)"
