#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# bootloader-packages.sh ROOT efi|bios : install the boot loader platform packages.
# UEFI uses Canonical's signed shim and GRUB unmodified, so Secure Boot works without key enrollment.
set -euo pipefail
# shellcheck source=installer/scripts/lib.sh
. /usr/lib/svoya/installer/lib.sh
need_root_arg "${1:-}"
fw=${2:-}

case $fw in
    efi) pkgs=(grub-efi-amd64-signed shim-signed grub-efi-amd64) ;;
    bios) pkgs=(grub-pc) ;;
    *) die "firmware type must be efi or bios, got '$fw'" ;;
esac

if [ -s "$ROOT$POOL_LIST" ] && pool_apt install "${pkgs[@]}"; then
    log "boot loader packages installed from the medium: ${pkgs[*]}"
elif online; then
    warn "pool install failed; trying the Ubuntu archive"
    in_target apt-get -q update
    in_target apt-get -y -q -o Dpkg::Options::=--force-confold install "${pkgs[@]}"
else
    die "cannot install ${pkgs[*]}: not on the medium and no network"
fi
