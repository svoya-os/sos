#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Build-time APT/dpkg policy. Build-only files are named *svoya-build* and removed by 95-cleanup.sh;
# the permanent policy ships in svoya-base (/etc/apt/preferences.d/svoya.pref).
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

chroot_dns "$root"

write_file "$root/etc/apt/apt.conf.d/00svoya-build" 0644 <<EOF
APT::Install-Recommends "false";
APT::Install-Suggests "false";
Acquire::Retries "5";
Acquire::http::Timeout "60";
Dpkg::Use-Pty "false";
$( [ "${SNAPSHOT:-none}" != none ] && echo 'Acquire::Check-Valid-Until "false";' )
EOF

# Same pins as svoya-base, active before svoya-base is installed.
cp "$SVOYA_SRC/packages/svoya-base/files/etc/apt/preferences.d/svoya.pref" \
    "$root/etc/apt/preferences.d/00svoya-build.pref"

# Lean image: no documentation except copyright files (kept for license compliance).
# This rule stays on the installed system, like Ubuntu's minimized images.
write_file "$root/etc/dpkg/dpkg.cfg.d/01svoya-nodoc" 0644 <<'EOF'
# SOS: documentation is online; copyright files are always kept.
path-exclude=/usr/share/doc/*
path-include=/usr/share/doc/*/copyright
path-include=/usr/share/doc/svoya-*/*
path-exclude=/usr/share/lintian/*
EOF
