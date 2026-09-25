#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Fetch the pinned Quickshell source next to debian/.
set -euo pipefail
: "${SVOYA_SRC:?}" "${PKG_DIR:?}"
# shellcheck source=packages/lib/common.sh
. "$SVOYA_SRC/packages/lib/common.sh"
# shellcheck source=packages/versions.env
. "$SVOYA_SRC/packages/versions.env"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
git_fetch_commit "$QUICKSHELL_REPO" "$QUICKSHELL_COMMIT" "$work/src"
grep -q "VERSION \"$QUICKSHELL_VERSION\"" "$work/src/CMakeLists.txt" ||
    die "quickshell: CMakeLists.txt does not declare version $QUICKSHELL_VERSION"
cp -a "$work/src/." "$PKG_DIR/"
