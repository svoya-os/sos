# shellcheck shell=bash
# SPDX-License-Identifier: Apache-2.0
# Helpers for image/build-iso.sh and image/hooks/*.sh.
#
# Hooks run as mmdebstrap customize hooks: "$1" is the rootfs; mmdebstrap has mounted /proc, /sys
# and /dev inside it and installed a policy-rc.d, so services never start during the build.

log()  { printf '\033[1;33m==>\033[0m %s\n' "$*" >&2; }
info() { printf '    %s\n' "$*" >&2; }
warn() { printf '\033[1;35mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# read_list FILE... -> package names, one per line (comments "#" and blank lines ignored)
read_list() {
    local f
    for f in "$@"; do
        [ -f "$f" ] || die "package list not found: $f"
        sed -e 's/#.*//' -e 's/[[:space:]]\+/\n/g' "$f" | sed '/^$/d'
    done
}

# in_chroot ROOTFS CMD... (clean, predictable environment)
in_chroot() {
    local root=$1
    shift
    chroot "$root" /usr/bin/env -i \
        PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/root LANG=C.UTF-8 LC_ALL=C.UTF-8 \
        DEBIAN_FRONTEND=noninteractive DEBCONF_NONINTERACTIVE_SEEN=true \
        SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-}" TERM=dumb "$@"
}

APT_OPTS=(-y -q -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold
          -o APT::Install-Recommends=false -o APT::Install-Suggests=false)

apt_update()  { in_chroot "$1" apt-get -q update; }
apt_install() { local r=$1; shift; in_chroot "$r" apt-get "${APT_OPTS[@]}" install "$@"; }
apt_purge()   { local r=$1; shift; in_chroot "$r" apt-get "${APT_OPTS[@]}" purge --autoremove "$@"; }

# installed ROOTFS PKG -> 0 if the package is installed
installed() {
    [ "$(in_chroot "$1" dpkg-query -W -f='${db:Status-Abbrev}' "$2" 2>/dev/null)" = "ii " ]
}

# available ROOTFS PKG -> 0 if APT knows a candidate for PKG
available() {
    local cand
    cand=$(in_chroot "$1" apt-cache policy "$2" 2>/dev/null | sed -n 's/^ *Candidate: *//p')
    [ -n "$cand" ] && [ "$cand" != "(none)" ]
}

# install_list ROOTFS LIST... : install every package of the lists in one transaction.
# "?pkg" entries are installed only when APT has a candidate (skips are logged).
install_list() {
    local root=$1 name
    shift
    local -a want=()
    while IFS= read -r name; do
        case $name in
            \?*)
                name=${name#\?}
                if available "$root" "$name"; then
                    want+=("$name")
                else
                    warn "optional package not in the archive, skipped: $name"
                fi
                ;;
            *) want+=("$name") ;;
        esac
    done < <(read_list "$@")
    [ "${#want[@]}" -gt 0 ] || return 0
    info "installing ${#want[@]} packages from $(basename -a "$@" | xargs)"
    apt_install "$root" "${want[@]}"
    # Everything listed is wanted for its own sake: never autoremove it later.
    in_chroot "$root" apt-mark manual "${want[@]}" >/dev/null
}

# Keep DNS working inside the chroot even after systemd-resolved turns /etc/resolv.conf into a
# symlink to a file that only exists at runtime. Restored by hooks/95-cleanup.sh.
chroot_dns() {
    local root=$1
    if [ -L "$root/etc/resolv.conf" ] || [ ! -s "$root/etc/resolv.conf" ]; then
        rm -f "$root/etc/resolv.conf"
        cp /etc/resolv.conf "$root/etc/resolv.conf"
    fi
}

# write_file PATH MODE  (content from stdin; creates parent dirs)
write_file() {
    install -d "$(dirname "$1")"
    cat >"$1"
    chmod "$2" "$1"
}
