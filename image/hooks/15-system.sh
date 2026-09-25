#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Locales (en_US + ru_RU), keyboard us,ru with Alt+Shift, console font with Cyrillic, timezone,
# hostname and the identity check (os-release comes from svoya-base).
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

# --- locales -------------------------------------------------------------------------------------
if [ -f "$root/etc/locale.gen" ]; then
    sed -i -E 's/^# *(en_US\.UTF-8 UTF-8)/\1/; s/^# *(ru_RU\.UTF-8 UTF-8)/\1/' "$root/etc/locale.gen"
    grep -q '^en_US.UTF-8 UTF-8' "$root/etc/locale.gen" || echo 'en_US.UTF-8 UTF-8' >>"$root/etc/locale.gen"
    grep -q '^ru_RU.UTF-8 UTF-8' "$root/etc/locale.gen" || echo 'ru_RU.UTF-8 UTF-8' >>"$root/etc/locale.gen"
fi
# Ubuntu's locale-gen takes locale names; plain Debian behaviour reads /etc/locale.gen.
in_chroot "$root" locale-gen en_US.UTF-8 ru_RU.UTF-8 || in_chroot "$root" locale-gen
write_file "$root/etc/default/locale" 0644 <<EOF
LANG=${LIVE_LOCALE}
EOF

# --- keyboard and console ------------------------------------------------------------------------
write_file "$root/etc/default/keyboard" 0644 <<'EOF'
# SOS default: English + Russian, Alt+Shift switches (the installer rewrites this file).
XKBMODEL="pc105"
XKBLAYOUT="us,ru"
XKBVARIANT=","
XKBOPTIONS="grp:alt_shift_toggle"
BACKSPACE="guess"
EOF
if [ -f "$root/etc/default/console-setup" ]; then
    sed -i -e 's/^CHARMAP=.*/CHARMAP="UTF-8"/' -e 's/^CODESET=.*/CODESET="CyrSlav"/' \
        -e 's/^FONTFACE=.*/FONTFACE="Terminus"/' -e 's/^FONTSIZE=.*/FONTSIZE="8x16"/' \
        "$root/etc/default/console-setup"
fi

# --- time, host ----------------------------------------------------------------------------------
ln -sf "/usr/share/zoneinfo/${LIVE_TIMEZONE}" "$root/etc/localtime"
echo "${LIVE_TIMEZONE}" >"$root/etc/timezone"
echo "${LIVE_HOSTNAME}" >"$root/etc/hostname"
write_file "$root/etc/hosts" 0644 <<EOF
127.0.0.1	localhost
127.0.1.1	${LIVE_HOSTNAME}
::1	localhost ip6-localhost ip6-loopback
ff02::1	ip6-allnodes
ff02::2	ip6-allrouters
EOF

# --- identity (svoya-base diverts Ubuntu's files) ------------------------------------------------
grep -q '^ID=sos$' "$root/usr/lib/os-release" || die "os-release is not SOS's (is svoya-base installed?)"
grep -q '^ID_LIKE="ubuntu debian"$' "$root/usr/lib/os-release" || warn "os-release lacks ID_LIKE=\"ubuntu debian\""
info "$(grep '^PRETTY_NAME=' "$root/usr/lib/os-release")"
