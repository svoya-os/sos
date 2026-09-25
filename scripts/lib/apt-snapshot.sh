# shellcheck shell=bash
# SPDX-License-Identifier: Apache-2.0
# Point the APT of a disposable ubuntu:26.04 build container at a frozen archive snapshot, so that
# packages/ (build dependencies, e.g. Qt for quickshell) and image/ (the ISO rootfs) see the same archive.
#
#   SNAPSHOT=20260920T000000Z   -> https://snapshot.ubuntu.com/ubuntu/20260920T000000Z
#   SNAPSHOT=none               -> keep the live archive (not reproducible)

snapshot_url() {
    printf '%s/%s' "${SNAPSHOT_MIRROR:-https://snapshot.ubuntu.com/ubuntu}" "$1"
}

# container_apt_setup SUITE SNAPSHOT
container_apt_setup() {
    local suite=$1 snapshot=$2
    export DEBIAN_FRONTEND=noninteractive
    cat >/etc/apt/apt.conf.d/90svoya-build <<'EOF'
APT::Install-Recommends "false";
APT::Install-Suggests "false";
Acquire::Retries "5";
Acquire::http::Timeout "60";
Dpkg::Use-Pty "false";
EOF
    if [ -z "$snapshot" ] || [ "$snapshot" = none ]; then
        apt-get update -q
        return 0
    fi
    # Phase 1: the stock image has no CA bundle; fetch ca-certificates from its default sources.
    if [ ! -s /etc/ssl/certs/ca-certificates.crt ]; then
        apt-get update -q
        apt-get install -y -q ca-certificates
    fi
    # Phase 2: switch every source to the snapshot. Release files of a snapshot are old by design.
    rm -f /etc/apt/sources.list
    find /etc/apt/sources.list.d -maxdepth 1 \( -name '*.list' -o -name '*.sources' \) -delete
    cat >/etc/apt/sources.list.d/ubuntu-snapshot.sources <<EOF
Types: deb
URIs: $(snapshot_url "$snapshot")
Suites: ${suite} ${suite}-updates ${suite}-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF
    echo 'Acquire::Check-Valid-Until "false";' >/etc/apt/apt.conf.d/91svoya-snapshot
    apt-get update -q
}
