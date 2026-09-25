#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Stage installer/ (Calamares settings, modules, branding, helper scripts).
set -euo pipefail
: "${SVOYA_SRC:?}" "${PKG_DIR:?}"
src=$SVOYA_SRC/installer
f=$PKG_DIR/files
install -d "$f/etc/calamares/modules" "$f/etc/calamares/branding" "$f/usr/lib/svoya/installer" \
    "$f/usr/bin" "$f/usr/share/applications"
install -m0644 "$src/settings.conf" "$f/etc/calamares/settings.conf"
install -m0644 "$src"/modules/*.conf "$f/etc/calamares/modules/"
cp -a "$src/branding/svoya" "$f/etc/calamares/branding/"
cp -a "$src/scripts/." "$f/usr/lib/svoya/installer/"
find "$f/usr/lib/svoya/installer" -name '__pycache__' -prune -exec rm -rf {} +
install -m0755 "$src/sos-install" "$f/usr/bin/sos-install"
install -m0644 "$src/sos-install.desktop" "$f/usr/share/applications/sos-install.desktop"
# Prefer the branding team's lockup for the welcome page when it exists (branding/out/logo/).
lockup=$SVOYA_SRC/branding/out/logo/sos-lockup-stacked-en-on-dark.png
if [ -f "$lockup" ]; then
    install -m0644 "$lockup" "$f/etc/calamares/branding/svoya/welcome.png"
fi
# Every image branding.desc names must exist (Calamares refuses to start without them).
for img in $(sed -n 's/^ *product\(Logo\|Icon\|Welcome\): *"\(.*\)".*/\2/p' "$src/branding/svoya/branding.desc"); do
    [ -f "$f/etc/calamares/branding/svoya/$img" ] || { echo "branding.desc names missing $img" >&2; exit 1; }
done
