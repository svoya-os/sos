#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# after-bootloader.sh ROOT efi|bios
# UEFI: - a Secure Boot capable removable-media fallback (\EFI\BOOT\BOOTX64.EFI = shim, not GRUB)
#       - BOOTX64.CSV labelled "SOS" (shim's fallback recreates the entry from it)
#       - the firmware boot entry is called "SOS" instead of "ubuntu" (the directory stays
#         \EFI\ubuntu because Canonical's signed GRUB looks for its configuration there)
# BIOS: remember the boot disk so future grub-pc upgrades reinstall GRUB there.
set -euo pipefail
# shellcheck source=installer/scripts/lib.sh
. /usr/lib/svoya/installer/lib.sh
need_root_arg "${1:-}"
fw=${2:-}

efi_setup() {
    local esp=$ROOT/boot/efi dir=$ROOT/boot/efi/EFI/ubuntu
    [ -f "$dir/shimx64.efi" ] || { warn "no shim in $dir; leaving the firmware entries alone"; return 0; }

    mkdir -p "$esp/EFI/BOOT"
    cp -f "$dir/shimx64.efi" "$esp/EFI/BOOT/BOOTX64.EFI"
    cp -f "$dir/grubx64.efi" "$esp/EFI/BOOT/grubx64.efi"
    [ -f "$dir/mmx64.efi" ] && cp -f "$dir/mmx64.efi" "$esp/EFI/BOOT/mmx64.efi"
    [ -f "$ROOT/usr/lib/shim/fbx64.efi" ] && cp -f "$ROOT/usr/lib/shim/fbx64.efi" "$esp/EFI/BOOT/fbx64.efi"
    printf 'shimx64.efi,SOS,,This is the boot entry for SOS\n' | iconv -f UTF-8 -t UTF-16 >"$dir/BOOTX64.CSV"
    log "fallback boot path installed"

    [ -d /sys/firmware/efi/efivars ] && command -v efibootmgr >/dev/null || return 0
    local dev disk part partuuid
    dev=$(findmnt -no SOURCE "$esp")
    disk=/dev/$(lsblk -no PKNAME "$dev" | head -n1)
    part=$(cat "/sys/class/block/$(basename "$dev")/partition")
    partuuid=$(blkid -s PARTUUID -o value "$dev")
    [ -n "$partuuid" ] && [ -n "$part" ] || { warn "cannot identify the EFI partition"; return 0; }
    efibootmgr --create --disk "$disk" --part "$part" --label "SOS" \
        --loader '\EFI\ubuntu\shimx64.efi' >/dev/null
    for num in $(efibootmgr -v | python3 /usr/lib/svoya/installer/efi_entries.py --partuuid "$partuuid"); do
        efibootmgr --bootnum "$num" --delete-bootnum >/dev/null && log "removed firmware entry Boot$num (ubuntu)"
    done
    log "firmware boot entry: SOS"
}

bios_setup() {
    local src disk
    src=$(findmnt -no SOURCE "$ROOT/boot" 2>/dev/null || findmnt -no SOURCE "$ROOT")
    src=${src%%[*}   # btrfs sources look like /dev/sda2[/@]
    disk=$(lsblk -lnso NAME,TYPE "$src" | awk '$2 == "disk" {print $1; exit}')
    [ -n "$disk" ] || { warn "cannot find the boot disk"; return 0; }
    local byid
    byid=$(find /dev/disk/by-id -lname "*/$disk" 2>/dev/null | grep -v -- '-part' | sort | head -n1)
    echo "grub-pc grub-pc/install_devices multiselect ${byid:-/dev/$disk}" | in_target debconf-set-selections
    log "grub-pc will be kept on ${byid:-/dev/$disk}"
}

case $fw in
    efi) efi_setup ;;
    bios) bios_setup ;;
    *) die "firmware type must be efi or bios" ;;
esac
