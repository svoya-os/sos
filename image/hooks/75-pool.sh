#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Offline package pool for the installer (becomes /pool and /dists on the ISO):
#   main          boot loader platform packages (grub-efi-amd64-signed + shim-signed, grub-pc) and
#                 dracut (the installed system uses dracut; the live initrd needs casper/initramfs-tools)
#   nvidia-<br>   NVIDIA driver sets without DKMS: Canonical-signed prebuilt kernel modules
#                 (linux-modules-nvidia-*-generic) + userspace, one component per branch
# Dependencies are resolved against the finished rootfs, so the pool holds exactly what the target
# is missing. The pool then proves itself: every install the installer will do is simulated
# offline against the pool alone. pool/svoya-gpu.json maps PCI modaliases to branches.
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

pool=$SVOYA_WORK/pool
cache=/var/cache/svoya-pool
rm -rf "$pool"
mkdir -p "$pool/pool" "$pool/dists/$SUITE"
chroot_dns "$root"

download() { # COMPONENT APT-ARGS...
    local comp=$1
    shift
    rm -rf "${root:?}$cache"
    mkdir -p "$root$cache/partial"
    if ! in_chroot "$root" apt-get "${APT_OPTS[@]}" --download-only -o Dir::Cache::archives="$cache" install "$@"; then
        rm -rf "${root:?}$cache"
        return 1
    fi
    mkdir -p "$pool/pool/$comp"
    find "$root$cache" -maxdepth 1 -name '*.deb' -exec mv -f -t "$pool/pool/$comp/" {} +
    rm -rf "${root:?}$cache"
}

nvidia_meta() { # BRANCH -> nvidia-driver-595-open / nvidia-driver-580
    local v=${1%-open}
    if [ "$v" != "$1" ]; then echo "nvidia-driver-$v-open"; else echo "nvidia-driver-$v"; fi
}
nvidia_set() { # BRANCH -> DKMS-free desktop driver set (like `ubuntu-drivers` with signed modules)
    local v=${1%-open} o=""
    [ "$v" != "$1" ] && o=-open
    echo "linux-modules-nvidia-$v$o-generic nvidia-headless-no-dkms-$v$o libnvidia-gl-$v" \
        "libnvidia-extra-$v libnvidia-decode-$v libnvidia-encode-$v libnvidia-fbc1-$v nvidia-utils-$v"
}

# The installer swaps the live initramfs stack for dracut in the target.
swap=()
for p in casper initramfs-tools initramfs-tools-core initramfs-tools-bin busybox-initramfs; do
    if installed "$root" "$p"; then swap+=("$p-"); fi
done

log "Pool: boot loaders and dracut"
download main grub-efi-amd64 grub-efi-amd64-signed grub-efi-amd64-bin shim-signed || die "EFI boot packages unavailable"
download main grub-pc grub-pc-bin || die "BIOS boot packages unavailable"
download main dracut dracut-core "${swap[@]}" || die "dracut unavailable"
components=(main)

specs=()
for b in $NVIDIA_BRANCHES; do
    comp=nvidia-$b
    read -r -a pkgs <<<"$(nvidia_set "$b")"
    meta=$(nvidia_meta "$b")
    log "Pool: NVIDIA $b"
    if ! download "$comp" "${pkgs[@]}"; then
        [ "$POOL_STRICT" = 1 ] && die "NVIDIA $b driver set is not installable from the archive"
        warn "NVIDIA $b skipped"
        continue
    fi
    if find "$pool/pool/$comp" -name 'dkms_*' -o -name 'nvidia-dkms-*' | grep -q .; then
        die "NVIDIA $b pulled DKMS; the pool must only carry signed prebuilt modules"
    fi
    in_chroot "$root" apt-cache show --no-all-versions "$meta" >"$SVOYA_WORK/$meta.show"
    specs+=("$b:$comp:$meta:$SVOYA_WORK/$meta.show:$(IFS=,; echo "${pkgs[*]}")")
    components+=("$comp")
done

log "Pool: indexing"
(
    cd "$pool"
    for comp in "${components[@]}"; do
        d=dists/$SUITE/$comp/binary-$ARCH
        mkdir -p "$d"
        apt-ftparchive packages "pool/$comp" >"$d/Packages"
        gzip -9nkf "$d/Packages"
    done
    apt-ftparchive \
        -o APT::FTPArchive::Release::Origin=SOS \
        -o APT::FTPArchive::Release::Label="SOS medium" \
        -o APT::FTPArchive::Release::Suite="$SUITE" \
        -o APT::FTPArchive::Release::Codename="$SUITE" \
        -o APT::FTPArchive::Release::Architectures="$ARCH" \
        -o APT::FTPArchive::Release::Components="${components[*]}" \
        release "dists/$SUITE" >"$SVOYA_WORK/pool-Release"
    mv "$SVOYA_WORK/pool-Release" "dists/$SUITE/Release"
)
python3 "$SVOYA_IMAGE/lib/pool_meta.py" "$pool/pool/svoya-gpu.json" "${specs[@]}"

log "Pool: offline self-test"
mnt=$root/tmp/svoya-pool
mkdir -p "$mnt" "$root/tmp/svoya-pool-lists/partial" "$root/tmp/svoya-pool-parts"
mount --bind "$pool" "$mnt"
cleanup_pool_mount() {
    umount "$mnt" 2>/dev/null || umount -l "$mnt" 2>/dev/null || true
    # Never rm -rf through a bind mount that is still there: it would delete the pool itself.
    if ! mountpoint -q "$mnt"; then rm -rf "${root:?}/tmp/svoya-pool"; fi
    rm -rf "${root:?}/tmp/svoya-pool-lists" "${root:?}/tmp/svoya-pool-parts" "${root:?}/tmp/svoya-pool.list"
}
trap cleanup_pool_mount EXIT
echo "deb [trusted=yes] file:/tmp/svoya-pool $SUITE ${components[*]}" >"$root/tmp/svoya-pool.list"
popts=(-o Dir::Etc::SourceList=/tmp/svoya-pool.list -o Dir::Etc::SourceParts=/tmp/svoya-pool-parts
       -o Dir::State::Lists=/tmp/svoya-pool-lists -o Dir::Cache::pkgcache= -o Dir::Cache::srcpkgcache=)
in_chroot "$root" apt-get "${popts[@]}" -q update

simulate() { # NAME APT-ARGS...
    local name=$1 out=$SVOYA_WORK/pool-sim-$1.txt
    shift
    if ! in_chroot "$root" apt-get "${popts[@]}" "${APT_OPTS[@]}" -s install "$@" >"$out" 2>&1; then
        cat "$out" >&2
        die "offline install '$name' does not resolve from the pool"
    fi
    if grep -q '^Inst dkms ' "$out"; then die "offline install '$name' would pull DKMS"; fi
    info "$name: $(grep -c '^Inst ' "$out") packages from the pool"
}
simulate dracut dracut "${swap[@]}"
simulate efi grub-efi-amd64-signed shim-signed grub-efi-amd64
simulate bios grub-pc
for b in $NVIDIA_BRANCHES; do
    [ -d "$pool/pool/nvidia-$b" ] || continue
    read -r -a pkgs <<<"$(nvidia_set "$b")"
    simulate "nvidia-$b" "${pkgs[@]}"
done

du -sh "$pool"/pool/* >&2
