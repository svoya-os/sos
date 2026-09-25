#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Run image/build-iso.sh in a privileged ubuntu:26.04 container (any Linux with Docker, or WSL2).
#   image/docker-build.sh [build-iso.sh options...]
# Environment: SVOYA_WORK_DIR (scratch, >= 30 GB free; default /var/tmp/sos-iso-work),
#              BUILD_IMAGE (default ubuntu:26.04), SNAPSHOT, NVIDIA_BRANCHES, POOL_STRICT, ...
# --privileged is needed because mmdebstrap (root mode) mounts /proc, /sys and /dev in the rootfs
# and the pool self-test bind-mounts the pool; no loop devices are used.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WORK=${SVOYA_WORK_DIR:-/var/tmp/sos-iso-work}
BUILD_IMAGE=${BUILD_IMAGE:-ubuntu:26.04}
command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }
mkdir -p "$WORK"
# Reproducible timestamps come from the last commit; the container has no git.
if [ -z "${SOURCE_DATE_EPOCH:-}" ] && git -C "$ROOT" rev-parse -q --verify HEAD >/dev/null 2>&1; then
    SOURCE_DATE_EPOCH=$(git -C "$ROOT" log -1 --format=%ct)
    export SOURCE_DATE_EPOCH
fi

tty=()
[ -t 1 ] && tty=(-t)
env_args=()
for v in SNAPSHOT SOURCE_DATE_EPOCH NVIDIA_BRANCHES POOL_STRICT SQUASHFS_COMP SQUASHFS_LEVEL \
         SOS_VERSION ISO_LABEL ISO_NAME SOS_APT_URL; do
    if [ -n "${!v:-}" ]; then env_args+=(-e "$v"); fi
done

exec docker run --rm "${tty[@]}" --privileged \
    -v "$ROOT:/src" -v "$WORK:/work" -w /src \
    -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" "${env_args[@]}" \
    "$BUILD_IMAGE" bash /src/image/build-iso.sh --work /work --out /src/dist/iso "$@"
