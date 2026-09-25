#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Services: apply SOS presets (svoya-base) explicitly, boot into the graphical target.
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

preset=$root/usr/lib/systemd/system-preset/40-svoya.preset
[ -f "$preset" ] || die "svoya-base presets missing"
while read -r action unit; do
    case $action in enable|disable) ;; *) continue ;; esac
    if ! in_chroot "$root" systemctl cat "$unit" >/dev/null 2>&1; then
        continue
    fi
    in_chroot "$root" systemctl "$action" "$unit" >/dev/null 2>&1 || warn "systemctl $action $unit failed"
    info "$action $unit"
done < <(sed -e 's/#.*//' "$preset")

in_chroot "$root" systemctl set-default graphical.target
# graphical.target wants display-manager.service; make it greetd whether or not greetd.service
# carries an [Install] alias.
ln -sfn /usr/lib/systemd/system/greetd.service "$root/etc/systemd/system/display-manager.service"
[ -e "$root/usr/lib/systemd/system/greetd.service" ] || die "greetd.service not installed"
info "display-manager.service -> greetd.service"
