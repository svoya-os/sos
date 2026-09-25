#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Live session: casper, Calamares + svoya-installer, autologin of the live user into SOS,
# and the live-only files the installer must not copy to the installed system.
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

before=$(mktemp)
after=$(mktemp)
trap 'rm -f "$before" "$after"' EXIT
in_chroot "$root" dpkg-query -W -f='${Package}\n' | sort >"$before"

chroot_dns "$root"
install_list "$root" "$SVOYA_IMAGE/packages/live.list"

in_chroot "$root" dpkg-query -W -f='${Package}\n' | sort >"$after"
install -d "$root/usr/share/svoya"
comm -13 "$before" "$after" >"$root/usr/share/svoya/live-packages.list"
info "live-only packages: $(wc -l <"$root/usr/share/svoya/live-packages.list")"

# --- casper: live user "svoya", host "sos" --------------------------------------------------------
write_file "$root/etc/casper.conf" 0644 <<EOF
# SOS live session (image/hooks/50-live.sh)
export USERNAME="${LIVE_USER}"
export USERFULLNAME="SOS live session"
export HOST="${LIVE_HOSTNAME}"
export BUILD_SYSTEM="Ubuntu"
# A non-empty FLAVOUR makes casper honour USERNAME and HOST above.
export FLAVOUR="SOS"
EOF

# --- greetd: log the live user straight into SOS --------------------------------------------------
write_file "$root/etc/svoya/greetd-live.toml" 0644 <<EOF
# SOS live session: autologin (live image only; not copied to installed systems).
[terminal]
vt = 7

[default_session]
command = "/usr/lib/svoya/greeter-session"
user = "svoya-greeter"

[initial_session]
command = "/usr/bin/svoya-session"
user = "${LIVE_USER}"
EOF
# 90- sorts after svoya-session's 50-svoya.conf, so this ExecStart wins.
write_file "$root/etc/systemd/system/greetd.service.d/90-svoya-live.conf" 0644 <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/sbin/greetd --config /etc/svoya/greetd-live.toml
EOF

# --- live markers and permissions ------------------------------------------------------------------
write_file "$root/etc/svoya/live" 0644 <<'EOF'
# This is the SOS live session. `sos session-start` skips the first-run wizard and Jackson offers
# «Установить СОС» while this file exists (cli/svoya_cli/live.py); the installer removes it.
EOF
write_file "$root/etc/polkit-1/rules.d/49-svoya-live.rules" 0644 <<EOF
// SOS live session only: the live user may administer the machine without a password.
polkit.addRule(function (action, subject) {
    if (subject.user == "${LIVE_USER}") { return polkit.Result.YES; }
    return polkit.Result.NOT_HANDLED;
});
EOF

# --- live-only units: VM test agent (inert unless the SMBIOS product is sos-vm-test), user groups -----
# Not `cp -a overlay/. root/`: that re-applies the checkout's owner (the CI runner's uid) and modes to
# existing directories, including / and /usr. Files are root-owned; existing directories keep theirs.
tar -C "$SVOYA_IMAGE/overlay-live" --owner=0 --group=0 --numeric-owner -cf - . |
    tar -C "$root" --no-overwrite-dir -xf -
in_chroot "$root" systemctl enable sos-vm-test.service sos-live-user.service

# --- what the installer must not copy (Calamares unpackfs excludeFile, rsync syntax) ---------------
write_file "$root/usr/share/svoya/live-exclude.rsync" 0644 <<'EOF'
/etc/svoya/live
/etc/svoya/greetd-live.toml
/etc/systemd/system/greetd.service.d/90-svoya-live.conf
/etc/polkit-1/rules.d/49-svoya-live.rules
/usr/lib/svoya/vm-test-agent
/usr/lib/svoya/live-user-groups
/usr/lib/systemd/system/sos-vm-test.service
/etc/systemd/system/multi-user.target.wants/sos-vm-test.service
/usr/lib/systemd/system/sos-live-user.service
/etc/systemd/system/multi-user.target.wants/sos-live-user.service
/usr/share/svoya/live-exclude.rsync
/usr/share/svoya/live-packages.list
EOF
