#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Lean AI core (python, uv, git-lfs, podman, Vulkan tools). Models, runtimes and CUDA are modules.
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

chroot_dns "$root"
install_list "$root" "$SVOYA_IMAGE/packages/ai-core.list"

# The shared model store must exist and be group-writable for "ai" (svoya-base tmpfiles).
in_chroot "$root" systemd-tmpfiles --create /usr/lib/tmpfiles.d/svoya.conf || true
[ "$(in_chroot "$root" stat -c '%G %a' /srv/ai)" = "ai 2775" ] || die "/srv/ai is not root:ai 2775"
