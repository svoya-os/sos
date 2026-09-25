#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Make our own packages (svoya-*, quickshell, uv, grub-btrfs from packages/build-all.sh) installable.
# The repository is copied into the rootfs for the build and removed again by 85/95.
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

[ -f "$SVOYA_REPO/Packages" ] || die "no package repository at $SVOYA_REPO (run packages/build-all.sh first)"
rm -rf "$root/var/lib/svoya-build-repo"
mkdir -p "$root/var/lib/svoya-build-repo"
cp -a "$SVOYA_REPO/." "$root/var/lib/svoya-build-repo/"

write_file "$root/etc/apt/sources.list.d/svoya-build.list" 0644 <<'EOF'
deb [trusted=yes] file:/var/lib/svoya-build-repo ./
EOF
# Our builds win over same-named archive packages (quickshell, uv, grub-btrfs could appear there).
write_file "$root/etc/apt/preferences.d/00svoya-build-local.pref" 0644 <<'EOF'
Package: *
Pin: release o=SOS
Pin-Priority: 900
EOF
apt_update "$root"
info "local packages: $(grep -c '^Package: ' "$SVOYA_REPO/Packages")"
