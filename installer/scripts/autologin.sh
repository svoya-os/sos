#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# autologin.sh ROOT USER : the user asked to be logged in automatically (greetd initial_session).
set -euo pipefail
# shellcheck source=installer/scripts/lib.sh
. /usr/lib/svoya/installer/lib.sh
need_root_arg "${1:-}"
user=${2:-}
[[ "$user" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "invalid user name '$user'"

conf=$ROOT/etc/svoya/greetd.toml
[ -f "$conf" ] || die "$conf missing (svoya-session not installed?)"
if ! grep -q '^\[initial_session\]' "$conf"; then
    cat >>"$conf" <<EOF

# Added by the installer: log $user in automatically at boot.
[initial_session]
command = "/usr/bin/svoya-session"
user = "$user"
EOF
fi
log "automatic login for $user"
