#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# dracut-swap.sh ROOT : replace the live initramfs stack (casper + initramfs-tools) with dracut,
# the Ubuntu 26.04 default, and build the initramfs of the installed system.
set -euo pipefail
# shellcheck source=installer/scripts/lib.sh
. /usr/lib/svoya/installer/lib.sh
need_root_arg "${1:-}"

remove=()
for p in casper initramfs-tools initramfs-tools-core initramfs-tools-bin busybox-initramfs; do
    if target_installed "$p"; then remove+=("$p-"); fi
done

if ! target_installed dracut; then
    if [ -s "$ROOT$POOL_LIST" ] && pool_apt install dracut dracut-core "${remove[@]}"; then
        log "dracut installed from the medium"
    elif online; then
        in_target apt-get -q update
        in_target apt-get -y -q install dracut dracut-core "${remove[@]}"
    else
        die "dracut is not on the medium and there is no network"
    fi
elif [ "${#remove[@]}" -gt 0 ]; then
    in_target apt-get -y -q purge "${remove[@]%-}"
fi

mkdir -p "$ROOT/etc/dracut.conf.d"
cat >"$ROOT/etc/dracut.conf.d/10-sos.conf" <<'EOF'
# SOS (installer): host-only images (sloppy = keep common storage drivers), zstd, boot splash.
hostonly="yes"
hostonly_mode="sloppy"
compress="zstd"
add_dracutmodules+=" plymouth btrfs "
EOF
if [ -s "$ROOT/etc/crypttab" ]; then
    echo 'add_dracutmodules+=" crypt "' >>"$ROOT/etc/dracut.conf.d/10-sos.conf"
fi
regen_initramfs
