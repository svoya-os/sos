#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Firefox from Mozilla's APT repository (packages.mozilla.org), not the Ubuntu snap.
# The signing key is fetched at build time and must match the pinned fingerprint.
# Note: packages.mozilla.org is not snapshotted, so the Firefox version follows the build date.
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

key=$root/etc/apt/keyrings/packages.mozilla.org.asc
install -d -m 0755 "$root/etc/apt/keyrings"
curl --fail --location --silent --show-error --retry 5 -o "$key" "$MOZILLA_KEY_URL"
fpr=$(gpg --show-keys --with-colons "$key" 2>/dev/null | awk -F: '/^fpr:/ {print $10; exit}')
[ "$fpr" = "$MOZILLA_KEY_FPR" ] || die "Mozilla APT key fingerprint mismatch: got '$fpr'"
chmod 0644 "$key"

write_file "$root/etc/apt/sources.list.d/mozilla.sources" 0644 <<EOF
Types: deb
URIs: ${MOZILLA_APT_URL}
Suites: mozilla
Components: main
Signed-By: /etc/apt/keyrings/packages.mozilla.org.asc
EOF
write_file "$root/etc/apt/preferences.d/mozilla.pref" 0644 <<'EOF'
# SOS: Firefox and its language packs come from Mozilla's repository.
Package: *
Pin: origin packages.mozilla.org
Pin-Priority: 1000
EOF

chroot_dns "$root"
apt_update "$root"
pkgs=(firefox)
if available "$root" firefox-l10n-ru; then pkgs+=(firefox-l10n-ru); fi
apt_install "$root" "${pkgs[@]}"
in_chroot "$root" apt-mark manual "${pkgs[@]}" >/dev/null
in_chroot "$root" dpkg-query -W -f='firefox ${Version}\n' firefox >&2
case $(in_chroot "$root" dpkg-query -W -f='${Version}' firefox) in
    *snap*) die "Ubuntu's snap transitional firefox package was installed instead of Mozilla's" ;;
esac
