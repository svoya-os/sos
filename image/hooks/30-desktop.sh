#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SOS desktop: Hyprland 0.53 + hyprbars from the archive, SOS Shell (Quickshell), greetd, PipeWire.
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

chroot_dns "$root"
install_list "$root" "$SVOYA_IMAGE/packages/desktop.list"

# The shell (Quickshell 0.3) watches the applications folders that exist when it starts. A folder
# made later is never watched: `sos install steam` wrote «Steam» over Debian's «Install Steam» into a
# new /usr/local/share/applications, and the launcher and the top bar kept «Install Steam» until the
# next login (the games bot, ISO #18). The folder is there from the start now.
install -d -m 0755 "$root/usr/local/share/applications"

# The build runs without Recommends; the shell's QML modules are Recommends of svoya-shell
# (computed from the imports in shell/), so install the ones that exist explicitly.
recs=$(in_chroot "$root" dpkg-query -W -f='${Recommends}' svoya-shell | tr ',' '\n' |
    sed -e 's/([^)]*)//g' -e 's/|.*//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' | sed '/^$/d')
want=()
for p in $recs; do
    if available "$root" "$p"; then want+=("$p"); else warn "svoya-shell recommends $p, not in the archive"; fi
done
if [ "${#want[@]}" -gt 0 ]; then
    apt_install "$root" "${want[@]}"
fi

hypr=$(in_chroot "$root" dpkg-query -W -f='${Version}' hyprland)
case $hypr in
    0.53.*) info "hyprland $hypr" ;;
    *) die "hyprland $hypr is not the 0.53 series the SOS Shell targets" ;;
esac
[ -f "$root/usr/lib/x86_64-linux-gnu/hyprland/plugins/libhyprbars.so" ] ||
    warn "libhyprbars.so not at the expected path; check shell/hypr plugin= line"
