#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# APT sources of the installed system: the live Ubuntu archive (not the build snapshot), Mozilla,
# and optionally the SOS repository. No `apt update` here: the image ships without package lists.
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

rm -f "$root/etc/apt/sources.list"
find "$root/etc/apt/sources.list.d" -maxdepth 1 \( -name '*.list' -o -name '*.sources' \) \
    ! -name 'mozilla.sources' -delete
write_file "$root/etc/apt/sources.list.d/ubuntu.sources" 0644 <<EOF
# The engine underneath SOS: Ubuntu ${SUITE} (26.04 LTS).
Types: deb
URIs: ${TARGET_MIRROR}
Suites: ${SUITE} ${SUITE}-updates ${SUITE}-backports
Components: ${COMPONENTS}
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: ${TARGET_SECURITY_MIRROR}
Suites: ${SUITE}-security
Components: ${COMPONENTS}
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF

# The SOS package repository for updates of svoya-* (only when it exists; see image/README.md).
if [ -n "${SOS_APT_URL:-}" ] && [ -n "${SOS_APT_KEY_FILE:-}" ] && [ -f "$SOS_APT_KEY_FILE" ]; then
    install -Dm0644 "$SOS_APT_KEY_FILE" "$root/usr/share/keyrings/sos-archive-keyring.asc"
    write_file "$root/etc/apt/sources.list.d/sos.sources" 0644 <<EOF
Types: deb
URIs: ${SOS_APT_URL}
Suites: ./
Signed-By: /usr/share/keyrings/sos-archive-keyring.asc
EOF
else
    info "no SOS_APT_URL/SOS_APT_KEY_FILE: svoya-* updates come with new images for now"
fi
rm -f "$root/etc/apt/preferences.d/00svoya-build-local.pref"
