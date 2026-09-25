#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# No Ubuntu branding, nags, telemetry or snaps; the SOS boot splash is the default.
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

mapfile -t unwanted < <(read_list "$SVOYA_IMAGE/packages/remove.list")
present=()
for p in "${unwanted[@]}"; do
    if installed "$root" "$p"; then present+=("$p"); fi
done
if [ "${#present[@]}" -gt 0 ]; then
    warn "purging: ${present[*]}"
    apt_purge "$root" "${present[@]}"
fi
rm -rf "$root/snap" "$root/var/snap" "$root/var/lib/snapd" "$root/var/cache/snapd"

left=()
for p in "${unwanted[@]}"; do
    if installed "$root" "$p"; then left+=("$p"); fi
done
[ "${#left[@]}" -eq 0 ] || die "still installed after purge: ${left[*]}"

# Plymouth: svoya-signal (svoya-branding) must be the default, no Ubuntu theme may remain.
theme=/usr/share/plymouth/themes/svoya-signal/svoya-signal.plymouth
if [ -f "$root$theme" ]; then
    in_chroot "$root" update-alternatives --set default.plymouth "$theme" || true
    info "plymouth: $(in_chroot "$root" readlink -f /usr/share/plymouth/themes/default.plymouth)"
else
    warn "svoya-signal plymouth theme not found (branding/plymouth missing?)"
fi
if find "$root/usr/share/plymouth/themes" -maxdepth 1 -iname '*ubuntu*' | grep -q .; then
    die "an Ubuntu plymouth theme is still installed"
fi
