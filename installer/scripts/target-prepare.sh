#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# target-prepare.sh ROOT : bind the medium into the target and configure a private APT source
# that contains only the medium's pool (offline installs never touch the network).
set -euo pipefail
# shellcheck source=installer/scripts/lib.sh
. /usr/lib/svoya/installer/lib.sh
need_root_arg "${1:-}"

[ -f "$MEDIUM/casper/filesystem.squashfs" ] || die "installation medium not mounted at $MEDIUM"
mkdir -p "$ROOT$TARGET_MEDIUM"
mountpoint -q "$ROOT$TARGET_MEDIUM" || mount --bind "$MEDIUM" "$ROOT$TARGET_MEDIUM"

mkdir -p "$ROOT$POOL_PARTS" "$ROOT$POOL_LISTS/partial"
if [ -d "$MEDIUM/dists" ]; then
    suite=$(find "$MEDIUM/dists" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | head -n1)
    comps=$(sed -n 's/^Components: *//p' "$MEDIUM/dists/$suite/Release")
    echo "deb [trusted=yes] file:$TARGET_MEDIUM $suite $comps" >"$ROOT$POOL_LIST"
    log "pool: $suite ($comps)"
    in_target apt-get "${POOL_OPTS[@]}" -q update
else
    warn "the medium has no package pool; boot loader and drivers need the internet"
    : >"$ROOT$POOL_LIST"
fi

# Answers for packages installed later from the pool.
in_target debconf-set-selections <<'EOF'
grub-pc grub-pc/install_devices_empty boolean true
grub-pc grub-pc/install_devices_failed_upgrade boolean true
EOF
