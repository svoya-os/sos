#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Engine: kernel, firmware, systemd, networking, storage tools, svoya-base.
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

chroot_dns "$root"
apt_update "$root"
# Kernel postinst hooks would build an initramfs for every intermediate state; 90-initramfs.sh
# builds the final one once.
install_list "$root" "$SVOYA_IMAGE/packages/base.list"
in_chroot "$root" dpkg-query -W -f='${Package} ${Version}\n' linux-image-generic svoya-base >&2
