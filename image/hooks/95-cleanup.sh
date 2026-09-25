#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Remove everything that only served the build; make the image generic (machine-id, logs, keys).
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

in_chroot "$root" apt-get -q clean
rm -rf "$root/var/lib/svoya-build-repo"
rm -f "$root"/etc/apt/apt.conf.d/00svoya-build "$root"/etc/apt/apt.conf.d/99mmdebstrap \
      "$root"/etc/apt/preferences.d/00svoya-build.pref "$root"/etc/apt/preferences.d/00svoya-build-local.pref \
      "$root"/etc/apt/sources.list.d/svoya-build.list "$root"/etc/dpkg/dpkg.cfg.d/99mmdebstrap
rm -rf "$root"/var/lib/apt/lists/* "$root"/var/cache/apt/*.bin
find "$root/var/cache/apt/archives" -maxdepth 1 -type f -name '*.deb' -delete 2>/dev/null || true

# Generic identity: systemd creates a machine-id on first boot (casper also does for the live system).
: >"$root/etc/machine-id"
rm -f "$root/var/lib/dbus/machine-id"
rm -f "$root"/etc/ssh/ssh_host_*
rm -f "$root/var/lib/systemd/random-seed" "$root/var/lib/systemd/credential.secret"

# DNS as systemd-resolved expects it.
rm -f "$root/etc/resolv.conf"
ln -s ../run/systemd/resolve/stub-resolv.conf "$root/etc/resolv.conf"

# Logs, caches, histories, backups of dpkg state.
find "$root/var/log" -type f -delete
rm -rf "$root"/tmp/* "$root"/var/tmp/* "$root"/root/.cache "$root"/root/.bash_history
rm -f "$root"/var/cache/debconf/*-old "$root"/var/lib/dpkg/*-old
rm -f "$root"/var/cache/ldconfig/aux-cache

# Sanity: nothing of the build may leak into the image.
[ ! -e "$root/etc/apt/sources.list.d/svoya-build.list" ] || die "build repository left in the image"
grep -rqs "snapshot.ubuntu.com" "$root/etc/apt" && die "snapshot URL left in /etc/apt" || true
