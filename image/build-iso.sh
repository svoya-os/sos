#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Build the SOS live/install ISO: mmdebstrap (Ubuntu 26.04, frozen snapshot) -> hooks -> squashfs
# -> casper layout -> offline pool -> BIOS (GRUB eltorito) + UEFI (Canonical-signed shim/GRUB)
# -> hybrid ISO (xorriso). Runs as root inside a privileged ubuntu:26.04 container:
#
#   docker run --rm --privileged -v "$PWD":/src -v /var/tmp/sos-work:/work ubuntu:26.04 \
#       bash /src/image/build-iso.sh --work /work --out /src/dist/iso
#
# (image/docker-build.sh does exactly that). Needs dist/repo from packages/build-all.sh.
#   --dry-run    validate lists/hooks/boot config and print the plan (no root, no network)
#   --no-setup   do not apt-get install the build tools (container already prepared)
#   --no-pool    skip the offline pool (faster test builds; the installer then needs internet)
#   --keep       keep the work directory (rootfs, iso tree) after a successful build
set -euo pipefail

IMAGE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(dirname "$IMAGE_DIR")
# shellcheck source=image/lib/common.sh
. "$IMAGE_DIR/lib/common.sh"
set -a
# shellcheck source=image/config.env
. "$IMAGE_DIR/config.env"
set +a

WORK=${SVOYA_WORK_DIR:-/var/tmp/sos-iso-work}
OUT=$ROOT/dist/iso
REPO=$ROOT/dist/repo
DRY_RUN=0
SETUP=1
KEEP=0
NO_POOL=0

while [ "$#" -gt 0 ]; do
    case $1 in
        --work) WORK=$2; shift 2 ;;
        --out) OUT=$2; shift 2 ;;
        --repo) REPO=$2; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --no-setup) SETUP=0; shift ;;
        --no-pool) NO_POOL=1; shift ;;
        --keep) KEEP=1; shift ;;
        -h|--help) sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) die "unknown option: $1" ;;
    esac
done

ROOTFS=$WORK/rootfs
ISO=$WORK/iso
POOL=$WORK/pool
HOOKS=("$IMAGE_DIR"/hooks/[0-9][0-9]-*.sh)
[ "$NO_POOL" = 1 ] && HOOKS=("${HOOKS[@]/*75-pool.sh/}")

source_date_epoch() {
    if [ -n "${SOURCE_DATE_EPOCH:-}" ]; then
        echo "$SOURCE_DATE_EPOCH"
    elif git -C "$ROOT" rev-parse -q --verify HEAD >/dev/null 2>&1; then
        git -C "$ROOT" log -1 --format=%ct
    elif [ "$SNAPSHOT" != none ]; then
        date -u -d "$(echo "$SNAPSHOT" | sed -E 's/^([0-9]{4})([0-9]{2})([0-9]{2})T([0-9]{2})([0-9]{2})([0-9]{2})Z$/\1-\2-\3 \4:\5:\6/')" +%s
    else
        date +%s
    fi
}

archive_url() { # the archive the build installs from
    if [ "$SNAPSHOT" = none ]; then echo "${TARGET_MIRROR%/}"; else echo "${SNAPSHOT_MIRROR%/}/$SNAPSHOT"; fi
}

write_sources() {
    local url sec kr=/usr/share/keyrings/ubuntu-archive-keyring.gpg
    url=$(archive_url)
    sec=$url
    [ "$SNAPSHOT" = none ] && sec=${TARGET_SECURITY_MIRROR%/}
    cat >"$WORK/sources.list" <<EOF
deb [signed-by=$kr] $url $SUITE $COMPONENTS
deb [signed-by=$kr] $url $SUITE-updates $COMPONENTS
deb [signed-by=$kr] $sec $SUITE-security $COMPONENTS
EOF
}

mmdebstrap_args() {
    # shellcheck disable=SC2054  # --include takes a comma-separated list
    MMDEBSTRAP_ARGS=(--mode=root --variant=minbase --arch="$ARCH" --format=directory
        --include=ca-certificates,gpgv,ubuntu-keyring
        --aptopt='Acquire::Retries "5"')
    if [ "$SNAPSHOT" != none ]; then
        MMDEBSTRAP_ARGS+=(--aptopt='Acquire::Check-Valid-Until "false"')
    fi
    local h
    for h in "${HOOKS[@]}"; do
        [ -n "$h" ] || continue
        MMDEBSTRAP_ARGS+=("--customize-hook=$h \"\$1\"")
    done
}

render() { # TEMPLATE DEST
    sed -e "s|@DISK_ID@|$DISK_ID|g" -e "s|@LIVE_USER@|$LIVE_USER|g" \
        -e "s|@LIVE_HOSTNAME@|$LIVE_HOSTNAME|g" -e "s|@VERSION@|$SOS_VERSION|g" "$1" >"$2"
}

xorriso_args() {
    XORRISO_ARGS=(-as mkisofs
        -iso-level 3 -full-iso9660-filenames -joliet -joliet-long -rational-rock
        -volid "$ISO_LABEL" -appid "SOS $SOS_VERSION" -publisher "SOS (github.com/svoya-os/sos)"
        -preparer "image/build-iso.sh"
        -partition_offset 16
        --grub2-mbr "$WORK/boot/boot_hybrid.img"
        --mbr-force-bootable
        -append_partition 2 0xef "$WORK/efi.img"
        -appended_part_as_gpt
        -iso_mbr_part_type a2a0d0ebe5b9334487c068b6b72699c7
        -c /boot.catalog
        -b /boot/grub/i386-pc/eltorito.img -no-emul-boot -boot-load-size 4 -boot-info-table --grub2-boot-info
        -eltorito-alt-boot
        -e '--interval:appended_partition_2:all::' -no-emul-boot
        --modification-date="$(date -u -d "@$SOURCE_DATE_EPOCH" +%Y%m%d%H%M%S00)"
        -o "$OUT/$ISO_NAME" "$ISO")
}

# ------------------------------------------------------------------------------------------------
dry_run() {
    log "Dry run: validating image inputs"
    local l
    for l in base desktop ai-core live remove; do
        info "$l.list: $(read_list "$IMAGE_DIR/packages/$l.list" | wc -l) entries"
    done
    local h
    for h in "${HOOKS[@]}"; do
        [ -n "$h" ] || continue
        [ -x "$h" ] || die "hook not executable: $h"
        bash -n "$h" || die "syntax error in $h"
    done
    info "${#HOOKS[@]} hooks ok"
    [ -x "$IMAGE_DIR/overlay-live/usr/lib/svoya/vm-test-agent" ] || die "vm-test-agent not executable"
    mkdir -p "$WORK/dry"
    DISK_ID=sos-dryrun
    render "$IMAGE_DIR/boot/grub.cfg" "$WORK/dry/grub.cfg"
    grep -q '@[A-Z_]*@' "$WORK/dry/grub.cfg" && die "unrendered placeholder in grub.cfg"
    SOURCE_DATE_EPOCH=$(source_date_epoch)
    write_sources
    mmdebstrap_args
    xorriso_args
    log "Plan"
    info "archive:  $(archive_url)"
    info "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH"
    printf '    mmdebstrap'; printf ' %q' "${MMDEBSTRAP_ARGS[@]}" "$SUITE" "$ROOTFS" "$WORK/sources.list"; echo
    printf '    xorriso'; printf ' %q' "${XORRISO_ARGS[@]}"; echo
    info "grub.cfg rendered to $WORK/dry/grub.cfg"
}

setup_container() {
    # shellcheck source=scripts/lib/apt-snapshot.sh
    . "$ROOT/scripts/lib/apt-snapshot.sh"
    log "Preparing build tools (snapshot: $SNAPSHOT)"
    container_apt_setup "$SUITE" "$SNAPSHOT"
    # resolute: grub-mkimage and /usr/share/grub/unicode.pf2 are in grub2-common (grub-common is a
    # dummy package depending on it; packages.ubuntu.com/resolute/grub-common).
    apt-get install -y -q mmdebstrap squashfs-tools xorriso mtools dosfstools grub-common grub2-common \
        apt-utils ca-certificates gpg gpgv curl python3 zstd cpio file rsync ubuntu-keyring
}

build_rootfs() {
    log "Bootstrapping $SUITE into $ROOTFS"
    rm -rf "$ROOTFS"
    mkdir -p "$WORK"
    write_sources
    mmdebstrap_args
    export SVOYA_SRC=$ROOT SVOYA_IMAGE=$IMAGE_DIR SVOYA_WORK=$WORK SVOYA_REPO=$REPO
    mmdebstrap "${MMDEBSTRAP_ARGS[@]}" "$SUITE" "$ROOTFS" "$WORK/sources.list"
    # mmdebstrap may drop files it copied from the host; make the final state explicit.
    echo "$LIVE_HOSTNAME" >"$ROOTFS/etc/hostname"
    rm -f "$ROOTFS/etc/resolv.conf"
    ln -s ../run/systemd/resolve/stub-resolv.conf "$ROOTFS/etc/resolv.conf"
    : >"$ROOTFS/etc/machine-id"
}

assemble_live() {
    log "Assembling the casper layout"
    rm -rf "$ISO"
    mkdir -p "$ISO/casper" "$ISO/.disk" "$ISO/boot/grub"
    local kver
    kver=$(find "$ROOTFS/boot" -maxdepth 1 -name 'vmlinuz-*' -printf '%f\n' | sed 's/^vmlinuz-//' | sort -V | tail -n1)
    [ -n "$kver" ] || die "no kernel in the rootfs"
    cp "$ROOTFS/boot/vmlinuz-$kver" "$ISO/casper/vmlinuz"
    cp "$ROOTFS/boot/initrd.img-$kver" "$ISO/casper/initrd"
    chroot "$ROOTFS" dpkg-query -W --showformat='${Package}\t${Version}\n' >"$ISO/casper/filesystem.manifest"
    cp "$ROOTFS/usr/share/svoya/live-packages.list" "$ISO/casper/filesystem.manifest-remove"
    du -sx --block-size=1 "$ROOTFS" | cut -f1 >"$ISO/casper/filesystem.size"

    local comp=(-comp "$SQUASHFS_COMP")
    case $SQUASHFS_COMP in
        zstd|gzip) comp+=(-Xcompression-level "$SQUASHFS_LEVEL") ;;
        xz) comp+=(-Xbcj x86) ;;
    esac
    log "Compressing the root filesystem ($SQUASHFS_COMP)"
    mksquashfs "$ROOTFS" "$ISO/casper/filesystem.squashfs" -noappend -no-progress \
        "${comp[@]}" -b "$SQUASHFS_BLOCK" -wildcards \
        -e 'proc/*' 'sys/*' 'dev/*' 'run/*' 'tmp/*' 'var/tmp/*'
    info "kernel $kver, squashfs $(du -h "$ISO/casper/filesystem.squashfs" | cut -f1)"

    DISK_ID="sos-$SOS_VERSION-$SOURCE_DATE_EPOCH"
    printf 'SOS %s «%s» - %s (%s)\n' "$SOS_VERSION" "$SOS_CODENAME_RU" "$ARCH" \
        "$(date -u -d "@$SOURCE_DATE_EPOCH" +%Y%m%d)" >"$ISO/.disk/info"
    echo "$DISK_ID" >"$ISO/.disk/$DISK_ID"
    if [ -d "$POOL/pool" ]; then
        cp -a "$POOL/pool" "$POOL/dists" "$ISO/"
    fi
}

# Extract the boot binaries from the same packages the installer uses (pool), or download them.
# resolute file lists: shim-signed has /usr/lib/shim/{shimx64.efi.dualsigned,shimx64.efi.signed.latest,
# mmx64.efi}; grub-efi-amd64-signed has /usr/lib/grub/x86_64-efi-signed/gcdx64.efi.signed;
# grub-pc-bin has /usr/lib/grub/i386-pc/{*.mod,*.lst,boot_hybrid.img}. (The "shim" package itself
# only ships docs there.)
boot_files() {
    local dest=$WORK/bootfiles pkg deb
    rm -rf "$dest" "$WORK/debs"
    mkdir -p "$dest" "$WORK/debs"
    for pkg in shim-signed grub-efi-amd64-signed grub-pc-bin; do
        deb=$(find "$POOL/pool/main" -name "${pkg}_*.deb" 2>/dev/null | sort -V | tail -n1)
        if [ -z "$deb" ]; then
            (cd "$WORK/debs" && apt-get download -q "$pkg")
            deb=$(find "$WORK/debs" -name "${pkg}_*.deb" | sort -V | tail -n1)
        fi
        [ -n "$deb" ] || die "cannot find $pkg for the boot files"
        info "boot files from $(basename "$deb")"
        dpkg-deb -x "$deb" "$dest"
    done
    BOOTFILES=$dest
}

assemble_boot() {
    log "Boot loaders"
    boot_files
    local b=$BOOTFILES shim="" f
    for f in shimx64.efi.dualsigned shimx64.efi.signed.latest shimx64.efi.signed; do
        if [ -f "$b/usr/lib/shim/$f" ]; then shim=$b/usr/lib/shim/$f; break; fi
    done
    [ -n "$shim" ] || die "no signed shim found"
    info "shim: $(basename "$shim")"
    local gcd=$b/usr/lib/grub/x86_64-efi-signed/gcdx64.efi.signed
    local mm=$b/usr/lib/shim/mmx64.efi
    [ -f "$gcd" ] || die "gcdx64.efi.signed missing"
    [ -f "$mm" ] || die "mmx64.efi missing"

    # --- UEFI: shim as BOOTX64.EFI, Canonical-signed CD GRUB as grubx64.efi, MOK manager -------
    local stage=$WORK/efi-stage
    rm -rf "$stage" "$WORK/efi.img"
    mkdir -p "$stage/EFI/BOOT"
    cp "$shim" "$stage/EFI/BOOT/BOOTX64.EFI"
    cp "$gcd" "$stage/EFI/BOOT/grubx64.efi"
    cp "$mm" "$stage/EFI/BOOT/mmx64.efi"
    find "$stage" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
    local kb
    kb=$(( $(du -sk "$stage" | cut -f1) + 2048 ))
    [ "$kb" -lt 8192 ] && kb=8192
    local invariant=()
    mkfs.vfat --help 2>&1 | grep -q -- '--invariant' && invariant=(--invariant)
    mkfs.vfat -C "${invariant[@]}" -i 534f5332 -n SOS_EFI "$WORK/efi.img" "$kb" >/dev/null
    MTOOLS_SKIP_CHECK=1 mcopy -s -m -i "$WORK/efi.img" "$stage/EFI" ::/
    cp -a "$stage/EFI" "$ISO/"

    # --- BIOS: GRUB El Torito core + modules, hybrid MBR -------------------------------------------
    mkdir -p "$ISO/boot/grub/i386-pc" "$ISO/boot/grub/fonts" "$WORK/boot"
    cp "$b"/usr/lib/grub/i386-pc/*.mod "$b"/usr/lib/grub/i386-pc/*.lst "$ISO/boot/grub/i386-pc/"
    cp "$b/usr/lib/grub/i386-pc/boot_hybrid.img" "$WORK/boot/boot_hybrid.img"
    render "$IMAGE_DIR/boot/bios-embed.cfg" "$WORK/boot/bios-embed.cfg"
    grub-mkimage -O i386-pc-eltorito -d "$b/usr/lib/grub/i386-pc" -p /boot/grub \
        -c "$WORK/boot/bios-embed.cfg" -o "$ISO/boot/grub/i386-pc/eltorito.img" \
        biosdisk iso9660 part_msdos part_gpt search search_fs_file configfile normal echo test

    # --- menu, font, theme ------------------------------------------------------------------------
    render "$IMAGE_DIR/boot/grub.cfg" "$ISO/boot/grub/grub.cfg"
    cp "$IMAGE_DIR/boot/loopback.cfg" "$ISO/boot/grub/loopback.cfg"
    cp /usr/share/grub/unicode.pf2 "$ISO/boot/grub/fonts/unicode.pf2"
    if [ -f "$ROOTFS/usr/share/grub/themes/svoya/theme.txt" ]; then
        mkdir -p "$ISO/boot/grub/themes"
        cp -a "$ROOTFS/usr/share/grub/themes/svoya" "$ISO/boot/grub/themes/"
    fi
}

make_iso() {
    log "Writing $ISO_NAME"
    mkdir -p "$OUT"
    (cd "$ISO" && find . -type f ! -name md5sum.txt ! -path './boot/grub/i386-pc/eltorito.img' -print0 |
        sort -z | xargs -0 md5sum >md5sum.txt)
    find "$ISO" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
    rm -f "$OUT/$ISO_NAME"
    xorriso_args
    xorriso "${XORRISO_ARGS[@]}"
    (cd "$OUT" && sha256sum "$ISO_NAME" >"$ISO_NAME.sha256")
    cp "$ISO/casper/filesystem.manifest" "$OUT/$ISO_NAME.manifest"
    xorriso -indev "$OUT/$ISO_NAME" -report_el_torito plain -report_system_area plain 2>/dev/null |
        sed 's/^/    /' >&2 || true
    python3 - "$OUT" "$ISO_NAME" "$ISO" "$POOL" <<'PY'
import json, os, sys, pathlib
out, name, iso, pool = sys.argv[1:5]
def size(p):
    p = pathlib.Path(p)
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0
info = {
    "iso": name,
    "isoBytes": size(os.path.join(out, name)),
    "squashfsBytes": size(os.path.join(iso, "casper", "filesystem.squashfs")),
    "poolBytes": size(os.path.join(iso, "pool")),
    "sourceDateEpoch": int(os.environ["SOURCE_DATE_EPOCH"]),
    "snapshot": os.environ.get("SNAPSHOT"),
    "version": os.environ.get("SOS_VERSION"),
}
pathlib.Path(out, name + ".json").write_text(json.dumps(info, indent=1) + "\n")
for k, v in info.items():
    if k.endswith("Bytes"):
        print(f"    {k[:-5]}: {v / 2**30:.2f} GiB", file=sys.stderr)
PY
}

main() {
    if [ "$DRY_RUN" = 1 ]; then
        WORK=${SVOYA_WORK_DIR:-$(mktemp -d)}
        dry_run
        return
    fi
    [ "$(id -u)" = 0 ] || die "run as root inside the build container (see image/README.md)"
    [ -f "$REPO/Packages" ] || die "no package repository at $REPO; run packages/build-all.sh first"
    export SOURCE_DATE_EPOCH
    SOURCE_DATE_EPOCH=$(source_date_epoch)
    [ "$SETUP" = 1 ] && setup_container
    command -v mmdebstrap >/dev/null || die "mmdebstrap missing (use the container or drop --no-setup)"
    local started=$SECONDS
    build_rootfs
    assemble_live
    assemble_boot
    make_iso
    if [ -n "${HOST_UID:-}" ]; then chown -R "$HOST_UID:${HOST_GID:-$HOST_UID}" "$OUT"; fi
    [ "$KEEP" = 1 ] || rm -rf "$ROOTFS" "$ISO" "$POOL" "$WORK/bootfiles" "$WORK/efi-stage"
    log "Done in $(( (SECONDS - started) / 60 )) min: $OUT/$ISO_NAME"
}

main "$@"
