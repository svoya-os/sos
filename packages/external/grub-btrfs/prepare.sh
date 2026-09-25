#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Fetch the pinned grub-btrfs source next to debian/.
set -euo pipefail
: "${SVOYA_SRC:?}" "${PKG_DIR:?}"
# shellcheck source=packages/lib/common.sh
. "$SVOYA_SRC/packages/lib/common.sh"
# shellcheck source=packages/versions.env
. "$SVOYA_SRC/packages/versions.env"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
git_fetch_commit "$GRUB_BTRFS_REPO" "$GRUB_BTRFS_COMMIT" "$work/src"
cp -a "$work/src/." "$PKG_DIR/"
