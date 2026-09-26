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

# The system says SOS everywhere: svoya-base's identity files replace base-files' (diversions).
# ISO #8 lost /etc/lsb-release, /etc/issue and the motd help text to dpkg's conffile takeover (the
# console welcome read «Welcome to  (GNU/Linux …)»); never again without the build noticing.
for f in /usr/lib/os-release /etc/lsb-release /etc/issue /etc/issue.net /etc/update-motd.d/10-help-text; do
    [ -s "$root$f" ] || die "identity file missing: $f (svoya-base)"
done
grep -q '^ID=sos$' "$root/usr/lib/os-release" || die "/usr/lib/os-release is not SOS's"
grep -q '^DISTRIB_ID=SOS$' "$root/etc/lsb-release" || die "/etc/lsb-release is not SOS's"
info "identity: $(sh "$root/etc/update-motd.d/00-header" 2>/dev/null | head -n 1 || true)"

