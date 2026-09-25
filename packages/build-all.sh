#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Build every SOS .deb inside an ubuntu:26.04 container and index them into a flat APT repo.
#
#   packages/build-all.sh                         # all packages -> dist/repo (uses docker)
#   packages/build-all.sh --only svoya-shell,quickshell
#   packages/build-all.sh --dry-run               # validate packaging only (no docker, no network)
#   packages/build-all.sh --no-container          # build on this host (must be Ubuntu 26.04, root)
#
# The repo is flat:  deb [trusted=yes] file:/path/to/dist/repo ./
# If SVOYA_REPO_SIGNING_KEY (ASCII-armoured private key) is set, Release is signed (InRelease).
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=packages/lib/common.sh
. "$ROOT/packages/lib/common.sh"
# shellcheck source=packages/versions.env
. "$ROOT/packages/versions.env"
# shellcheck source=image/config.env
. "$ROOT/image/config.env"

# Build order only matters for humans reading logs; there are no build-time deps between them.
ALL_PACKAGES=(
    svoya-base svoya-fonts svoya-branding svoya-cli svoya-jackson
    svoya-shell svoya-session svoya-installer
    quickshell uv grub-btrfs upsil
)
# A failed optional package is reported and skipped; the image lists it as ?name.
OPTIONAL_PACKAGES=(upsil)

OUT="$ROOT/dist/repo"
ONLY=""
MODE=auto          # auto | container | host
DRY_RUN=0
KEEP=0
JOBS=${JOBS:-$(nproc 2>/dev/null || echo 2)}
BUILD_IMAGE=${BUILD_IMAGE:-ubuntu:26.04}
BUILD_ROOT=${BUILD_ROOT:-/tmp/svoya-pkgbuild}

usage() {
    sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    cat <<EOF

Options:
  --only A,B       build only these packages (see --list)
  --out DIR        repository directory (default: dist/repo)
  --list           print the package names and exit
  --dry-run        validate packaging (control/rules/prepare scripts) and exit
  --no-container   build directly on this host
  --keep           keep the build tree in \$BUILD_ROOT
  --jobs N         parallel jobs for compiled packages (default: nproc)
  --image IMG      container image (default: $BUILD_IMAGE)
EOF
}

while [ "$#" -gt 0 ]; do
    case $1 in
        --only) ONLY=$2; shift 2 ;;
        --only=*) ONLY=${1#*=}; shift ;;
        --out) OUT=$2; shift 2 ;;
        --list) printf '%s\n' "${ALL_PACKAGES[@]}"; exit 0 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --no-container) MODE=host; shift ;;
        --in-container) MODE=container; shift ;;
        --keep) KEEP=1; shift ;;
        --jobs) JOBS=$2; shift 2 ;;
        --image) BUILD_IMAGE=$2; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1 (see --help)" ;;
    esac
done

pkg_dir() {
    if [ -d "$ROOT/packages/$1/debian" ]; then
        printf '%s' "$ROOT/packages/$1"
    elif [ -d "$ROOT/packages/external/$1/debian" ]; then
        printf '%s' "$ROOT/packages/external/$1"
    else
        return 1
    fi
}

is_optional() {
    local o
    for o in "${OPTIONAL_PACKAGES[@]}"; do [ "$o" = "$1" ] && return 0; done
    return 1
}

selected_packages() {
    if [ -z "$ONLY" ]; then
        printf '%s\n' "${ALL_PACKAGES[@]}"
        return
    fi
    local p known
    for p in ${ONLY//,/ }; do
        known=0
        for k in "${ALL_PACKAGES[@]}"; do [ "$k" = "$p" ] && known=1; done
        [ "$known" = 1 ] || die "unknown package '$p' (see --list)"
        printf '%s\n' "$p"
    done
}

# ---------------------------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------------------------
source_date_epoch() {
    if [ -n "${SOURCE_DATE_EPOCH:-}" ]; then
        printf '%s' "$SOURCE_DATE_EPOCH"
    elif git -C "$ROOT" rev-parse -q --verify HEAD >/dev/null 2>&1; then
        git -C "$ROOT" log -1 --format=%ct
    else
        date +%s
    fi
}

svoya_version() {
    local tag sha day
    if git -C "$ROOT" rev-parse -q --verify HEAD >/dev/null 2>&1; then
        tag=$(git -C "$ROOT" describe --tags --exact-match 2>/dev/null || true)
        if [ -n "$tag" ] && [ "${tag#v}" = "$SVOYA_PKG_VERSION" ]; then
            printf '%s' "$SVOYA_PKG_VERSION"
            return
        fi
        sha=$(git -C "$ROOT" rev-parse --short=8 HEAD)
        day=$(date -u -d "@$(git -C "$ROOT" log -1 --format=%ct)" +%Y%m%d)
        printf '%s~git%s.%s' "$SVOYA_PKG_VERSION" "$day" "$sha"
    else
        day=$(date -u -d "@$SDE" +%Y%m%d%H%M)
        printf '%s~dev%s' "$SVOYA_PKG_VERSION" "$day"
    fi
}

pkg_version() {
    case $1 in
        quickshell) printf '%s-0svoya1' "$QUICKSHELL_VERSION" ;;
        uv) printf '%s-0svoya1' "$UV_VERSION" ;;
        grub-btrfs) printf '%s-0svoya1' "$GRUB_BTRFS_VERSION" ;;
        upsil) printf '%s-0svoya1' "$UPSIL_VERSION" ;;
        *) printf '%s' "$SVOYA_VERSION_STR" ;;
    esac
}

write_changelog() { # DIR SOURCE VERSION
    local dir=$1 src=$2 ver=$3 ref
    ref=$(git -C "$ROOT" rev-parse --short=12 HEAD 2>/dev/null || echo "working tree")
    cat >"$dir/debian/changelog" <<EOF
$src ($ver) $SUITE; urgency=medium

  * Automated build from $SVOYA_HOMEPAGE ($ref).

 -- $SVOYA_MAINTAINER  $(date -u -R -d "@$SDE")
EOF
}

# ---------------------------------------------------------------------------------------------
# Dry run: static validation that works anywhere (used by CI and locally).
# ---------------------------------------------------------------------------------------------
validate_one() {
    local name=$1 dir
    dir=$(pkg_dir "$name") || die "$name: no packaging found under packages/"
    [ -f "$dir/debian/control" ] || die "$name: debian/control missing"
    [ -x "$dir/debian/rules" ] || die "$name: debian/rules missing or not executable"
    grep -q '^Source: ' "$dir/debian/control" || die "$name: control has no Source field"
    grep -q '^Package: ' "$dir/debian/control" || die "$name: control has no Package paragraph"
    grep -q 'debhelper-compat' "$dir/debian/control" || die "$name: Build-Depends lacks debhelper-compat"
    if [ -f "$dir/prepare.sh" ]; then
        bash -n "$dir/prepare.sh" || die "$name: prepare.sh has syntax errors"
    fi
    local s
    for s in "$dir"/debian/*.preinst "$dir"/debian/*.postinst "$dir"/debian/*.prerm "$dir"/debian/*.postrm \
             "$dir"/debian/preinst "$dir"/debian/postinst "$dir"/debian/prerm "$dir"/debian/postrm; do
        [ -f "$s" ] || continue
        sh -n "$s" || die "$name: $(basename "$s") has syntax errors"
    done
    python3 "$ROOT/packages/lib/check_control.py" "$dir/debian/control" || die "$name: invalid debian/control"
    info "$name: ok ($(pkg_version "$name"))"
}

# ---------------------------------------------------------------------------------------------
# Real build (inside ubuntu:26.04)
# ---------------------------------------------------------------------------------------------
setup_build_host() {
    # shellcheck source=scripts/lib/apt-snapshot.sh
    . "$ROOT/scripts/lib/apt-snapshot.sh"
    if [ "$MODE" = container ]; then
        log "Preparing build environment ($SUITE, snapshot: $SNAPSHOT)"
        container_apt_setup "$SUITE" "$SNAPSHOT"
    else
        # Never rewrite the APT sources of a real machine (container_apt_setup deletes them).
        warn "--no-container: using this host's APT sources as they are (snapshot $SNAPSHOT not applied)"
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -q
    fi
    apt-get install -y -q --no-install-recommends build-essential debhelper dh-python dpkg-dev fakeroot \
        git ca-certificates curl apt-utils python3 xz-utils zstd gnupg
    git config --global --add safe.directory "$ROOT"
}

build_one() {
    local name=$1 src ver dir bdir
    src=$(pkg_dir "$name")
    ver=$(pkg_version "$name")
    dir="$BUILD_ROOT/$name"
    bdir="$dir/$name-${ver%%-*}"
    log "Building $name $ver"
    rm -rf "$dir"
    mkdir -p "$bdir"
    cp -a "$src/debian" "$bdir/debian"
    if [ -d "$src/files" ]; then
        cp -a "$src/files" "$bdir/files"
    fi
    write_changelog "$bdir" "$(sed -n 's/^Source: *//p' "$bdir/debian/control")" "$ver"
    # Build dependencies first: some prepare.sh steps use them (svoya-branding: grub-mkfont).
    apt-get build-dep -y -q "$bdir"
    if [ -f "$src/prepare.sh" ]; then
        info "prepare.sh"
        SVOYA_SRC=$ROOT PKG_DIR=$bdir PKG_VERSION=$ver SOURCE_DATE_EPOCH=$SDE \
            bash "$src/prepare.sh"
    fi
    (
        cd "$bdir"
        SOURCE_DATE_EPOCH=$SDE DEB_BUILD_OPTIONS="parallel=$JOBS nocheck" \
            dpkg-buildpackage -b -us -uc
    )
    local deb bin arch
    for deb in "$dir"/*.deb "$dir"/*.ddeb; do
        [ -f "$deb" ] || continue
        bin=$(dpkg-deb -f "$deb" Package)
        arch=$(dpkg-deb -f "$deb" Architecture)
        # drop older builds of the same binary package so the index has exactly one version
        if [ "${deb##*.}" = ddeb ]; then
            mkdir -p "$OUT/dbgsym"
            rm -f "$OUT/dbgsym/${bin}_"*"_${arch}.ddeb"
            mv "$deb" "$OUT/dbgsym/"
        else
            rm -f "$OUT/pool/${bin}_"*"_${arch}.deb"
            mv "$deb" "$OUT/pool/"
        fi
    done
    [ "$KEEP" = 1 ] || rm -rf "$dir"
}

index_repo() {
    log "Indexing $OUT"
    (
        cd "$OUT"
        apt-ftparchive packages pool >Packages
        gzip -9nkf Packages
        apt-ftparchive \
            -o APT::FTPArchive::Release::Origin=SOS \
            -o APT::FTPArchive::Release::Label=SOS \
            -o APT::FTPArchive::Release::Suite=sos \
            -o APT::FTPArchive::Release::Codename="$SUITE" \
            -o APT::FTPArchive::Release::Architectures="amd64 all" \
            -o APT::FTPArchive::Release::Description="SOS packages (svoya-*)" \
            release . >Release
    )
    if [ -n "${SVOYA_REPO_SIGNING_KEY:-}" ]; then
        log "Signing Release"
        local gnupghome
        gnupghome=$(mktemp -d)
        printf '%s\n' "$SVOYA_REPO_SIGNING_KEY" | GNUPGHOME=$gnupghome gpg --batch --import
        GNUPGHOME=$gnupghome gpg --batch --yes --clearsign -o "$OUT/InRelease" "$OUT/Release"
        GNUPGHOME=$gnupghome gpg --batch --yes -abs -o "$OUT/Release.gpg" "$OUT/Release"
        rm -rf "$gnupghome"
    else
        info "SVOYA_REPO_SIGNING_KEY not set: repository is unsigned (use [trusted=yes] locally)"
    fi
    (cd "$OUT" && find pool -name '*.deb' -printf '%f\n' | sort) >&2
}

run_in_docker() {
    command -v docker >/dev/null || die "docker not found; use --no-container on an Ubuntu 26.04 host or --dry-run"
    local tty=()
    [ -t 1 ] && tty=(-t)
    local args=(--in-container --out "/src/${OUT#"$ROOT"/}" --jobs "$JOBS")
    [ -n "$ONLY" ] && args+=(--only "$ONLY")
    [ "$KEEP" = 1 ] && args+=(--keep)
    case $OUT in "$ROOT"/*) ;; *) die "--out must be inside the repository when using docker" ;; esac
    # a local UpsiL checkout is mounted read-only where the container can see it
    local upsil=()
    if [ -n "${UPSIL_SRC_DIR:-}" ]; then
        [ -d "$UPSIL_SRC_DIR" ] || die "UPSIL_SRC_DIR=$UPSIL_SRC_DIR is not a directory"
        upsil=(-v "$(cd "$UPSIL_SRC_DIR" && pwd):/upsil-src:ro" -e UPSIL_SRC_DIR=/upsil-src)
    fi
    log "Running in $BUILD_IMAGE"
    docker run --rm "${tty[@]}" \
        -v "$ROOT:/src" -w /src "${upsil[@]}" \
        -e SOURCE_DATE_EPOCH="$SDE" -e SVOYA_VERSION_STR="$SVOYA_VERSION_STR" \
        -e SNAPSHOT -e SVOYA_PKG_VERSION -e UV_SHA256_X86_64 -e GITHUB_ACTIONS \
        -e UPSIL_COMMIT \
        -e SVOYA_REPO_SIGNING_KEY -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
        "$BUILD_IMAGE" bash /src/packages/build-all.sh "${args[@]}"
}

main() {
    # Computed on the host (which has the git checkout) and handed to the container unchanged.
    SDE=$(source_date_epoch)
    SVOYA_VERSION_STR=${SVOYA_VERSION_STR:-$(svoya_version)}
    mapfile -t PKGS < <(selected_packages)

    if [ "$DRY_RUN" = 1 ]; then
        log "Validating packaging (${#PKGS[@]} packages, svoya version $SVOYA_VERSION_STR)"
        for p in "${PKGS[@]}"; do validate_one "$p"; done
        return 0
    fi

    if [ "$MODE" = auto ]; then
        run_in_docker
        return
    fi

    [ "$(id -u)" = 0 ] || die "the build needs root (it installs build dependencies with apt)"
    grep -q "VERSION_CODENAME=$SUITE" /etc/os-release || warn "host is not Ubuntu $SUITE; results may differ from CI"
    # The stock ubuntu:26.04 image has no python3 (check_control.py) and no git: install the build
    # tools first, then validate.
    setup_build_host
    for p in "${PKGS[@]}"; do validate_one "$p"; done
    mkdir -p "$OUT/pool"
    local rc
    for p in "${PKGS[@]}"; do
        if is_optional "$p"; then
            # errexit is switched back on inside the subshell (a subshell started under `set +e`,
            # or as part of `||`, would otherwise run past a failed step)
            set +e
            (set -e; build_one "$p")
            rc=$?
            set -e
            if [ "$rc" != 0 ]; then
                warn "optional package $p was not built (exit $rc); the image goes without it"
                [ -n "${GITHUB_ACTIONS:-}" ] && echo "::warning::optional package $p was not built (exit $rc)"
                rm -rf "${BUILD_ROOT:?}/$p"
            fi
        else
            build_one "$p"
        fi
    done
    index_repo
    if [ -n "${HOST_UID:-}" ]; then
        chown -R "$HOST_UID:${HOST_GID:-$HOST_UID}" "$OUT"
    fi
    log "Done: $(find "$OUT/pool" -name '*.deb' | wc -l) packages in $OUT"
}

main "$@"
