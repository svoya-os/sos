# shellcheck shell=bash
# SPDX-License-Identifier: Apache-2.0
# Shared by the SOS installer steps (/usr/lib/svoya/installer/*.sh). They run on the live system
# (Calamares "dontChroot: true") and operate on the target mounted at $ROOT.
# shellcheck disable=SC2034  # constants used by the scripts that source this file

MEDIUM=/run/sos-installer/medium          # bind of the live medium (see launch)
TARGET_MEDIUM=/media/sos-medium           # the same, inside the target
POOL_LIST=/etc/apt/sos-installer.list     # private APT config: the medium's pool only
POOL_PARTS=/etc/apt/sos-installer.parts.d
POOL_LISTS=/var/lib/sos-installer/lists

log()  { printf '[sos-installer] %s\n' "$*"; }
warn() { printf '[sos-installer] warning: %s\n' "$*" >&2; }
die()  { printf '[sos-installer] error: %s\n' "$*" >&2; exit 1; }

need_root_arg() {
    ROOT=${1:-}
    [ -n "$ROOT" ] && [ -d "$ROOT" ] || die "usage: $(basename "$0") TARGET_ROOT ..."
    [ "$ROOT" != / ] || die "refusing to operate on the live system's /"
}

in_target() {
    chroot "$ROOT" /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/root \
        LANG=C.UTF-8 DEBIAN_FRONTEND=noninteractive DEBCONF_NONINTERACTIVE_SEEN=true "$@"
}

POOL_OPTS=(-o "Dir::Etc::SourceList=$POOL_LIST" -o "Dir::Etc::SourceParts=$POOL_PARTS"
           -o "Dir::State::Lists=$POOL_LISTS" -o Dir::Cache::pkgcache= -o Dir::Cache::srcpkgcache=
           -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold
           -o APT::Install-Recommends=false)

# pool_apt ARGS... : apt-get in the target, with the medium's pool as the only source
pool_apt() { in_target apt-get "${POOL_OPTS[@]}" -y -q "$@"; }

target_installed() {
    [ "$(in_target dpkg-query -W -f='${db:Status-Abbrev}' "$1" 2>/dev/null)" = "ii " ]
}

# online: the Ubuntu archive is reachable (used only as a fallback while installing)
online() {
    timeout 6 bash -c 'exec 3<>/dev/tcp/archive.ubuntu.com/80' 2>/dev/null
}

# regen_initramfs: dracut for every installed kernel, named like Ubuntu expects
regen_initramfs() {
    local d k
    for d in "$ROOT"/usr/lib/modules/*; do
        k=${d##*/}
        [ -e "$ROOT/boot/vmlinuz-$k" ] || continue
        log "dracut for $k"
        in_target dracut --force --kver "$k" "/boot/initrd.img-$k"
    done
}
