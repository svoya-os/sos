#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Generate the identity files of svoya-base (os-release, lsb-release, issue) into $PKG_DIR/files.
# Templates come from branding/os/<name>[.in] when the branding component provides them;
# @VERSION@, @VERSION_ID@, @CODENAME_RU@, @CODENAME_EN@, @UBUNTU_CODENAME@ are substituted.
set -euo pipefail
: "${SVOYA_SRC:?}" "${PKG_DIR:?}"
# shellcheck source=image/config.env
. "$SVOYA_SRC/image/config.env"

files=$PKG_DIR/files
mkdir -p "$files/usr/lib" "$files/etc"

render() { # NAME DEST DEFAULT-CONTENT
    local name=$1 dest=$2 default=$3 tpl=""
    for cand in "$SVOYA_SRC/branding/os/$name.in" "$SVOYA_SRC/branding/os/$name"; do
        if [ -f "$cand" ]; then tpl=$cand; break; fi
    done
    if [ -n "$tpl" ]; then
        echo "    using $tpl" >&2
        sed -e "s|@VERSION@|$SOS_VERSION «$SOS_CODENAME_RU»|g" \
            -e "s|@VERSION_ID@|$SOS_VERSION|g" \
            -e "s|@CODENAME_RU@|$SOS_CODENAME_RU|g" \
            -e "s|@CODENAME_EN@|$SOS_CODENAME_EN|g" \
            -e "s|@UBUNTU_CODENAME@|$SUITE|g" "$tpl" >"$dest"
    else
        printf '%s\n' "$default" >"$dest"
    fi
}

render os-release "$files/usr/lib/os-release" "NAME=\"SOS\"
PRETTY_NAME=\"SOS $SOS_VERSION «$SOS_CODENAME_RU»\"
VERSION=\"$SOS_VERSION «$SOS_CODENAME_RU»\"
VERSION_ID=\"$SOS_VERSION\"
VERSION_CODENAME=$SUITE
ID=sos
ID_LIKE=\"ubuntu debian\"
UBUNTU_CODENAME=$SUITE
HOME_URL=\"https://github.com/svoya-os/sos\"
SUPPORT_URL=\"https://github.com/svoya-os/sos/discussions\"
BUG_REPORT_URL=\"https://github.com/svoya-os/sos/issues\"
PRIVACY_POLICY_URL=\"https://github.com/svoya-os/sos/blob/main/docs/VISION.md\"
LOGO=sos"

render lsb-release "$files/etc/lsb-release" "DISTRIB_ID=SOS
DISTRIB_RELEASE=$SOS_VERSION
DISTRIB_CODENAME=$SUITE
DISTRIB_DESCRIPTION=\"SOS $SOS_VERSION «$SOS_CODENAME_RU»\""

render issue "$files/etc/issue" "SOS $SOS_VERSION \\n \\l
"
render issue.net "$files/etc/issue.net" "SOS $SOS_VERSION"

# The engine underneath, for tools that need to know (same convention as other Ubuntu derivatives).
mkdir -p "$files/etc/upstream-release"
cat >"$files/etc/upstream-release/lsb-release" <<EOF
DISTRIB_ID=Ubuntu
DISTRIB_RELEASE=26.04
DISTRIB_CODENAME=$SUITE
DISTRIB_DESCRIPTION="Ubuntu 26.04 LTS"
EOF

grep -q '^ID=' "$files/usr/lib/os-release" || { echo "os-release template has no ID=" >&2; exit 1; }
