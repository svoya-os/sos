#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# The live initrd: initramfs-tools with casper's scripts and the SOS boot splash.
# (Ubuntu 26.04's casper 26.04.x still depends on initramfs-tools and ships no dracut module; the
# installed system is switched to dracut by the installer.)
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

installed "$root" casper || die "casper is not installed"
installed "$root" initramfs-tools || die "initramfs-tools is not installed (casper needs it)"
# Compress with zstd: smaller than the default and fast to unpack.
write_file "$root/etc/initramfs-tools/conf.d/svoya.conf" 0644 <<'EOF'
COMPRESS=zstd
COMPRESSLEVEL=19
EOF
in_chroot "$root" update-initramfs -c -k all 2>&1 | tail -n 20 >&2 || true
in_chroot "$root" update-initramfs -u -k all >&2

kver=$(in_chroot "$root" linux-version list | sort -V | tail -n1)
initrd=/boot/initrd.img-$kver
[ -s "$root$initrd" ] || die "no initrd for $kver"
listing=$(in_chroot "$root" lsinitramfs "$initrd")
grep -q 'scripts/casper$' <<<"$listing" || die "casper scripts missing from $initrd"
grep -q 'plymouth' <<<"$listing" || warn "plymouth is not in $initrd (no boot splash)"
grep -q 'svoya-signal' <<<"$listing" || warn "svoya-signal theme is not in $initrd"
info "kernel $kver, initrd $(du -h "$root$initrd" | cut -f1)"
