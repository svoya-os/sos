#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Stage the Hyprland configuration written by the shell team (shell/hypr) into the package.
set -euo pipefail
: "${SVOYA_SRC:?}" "${PKG_DIR:?}"
dest=$PKG_DIR/files/usr/share/svoya/hypr
mkdir -p "$dest"
if [ -d "$SVOYA_SRC/shell/hypr" ]; then
    cp -a "$SVOYA_SRC/shell/hypr/." "$dest/"
    find "$dest" \( -name '__pycache__' -o -name '*.pyc' -o -name '*.md' \) -prune -exec rm -rf {} +
fi
if [ ! -f "$dest/hyprland.conf" ]; then
    echo "warning: shell/hypr/hyprland.conf missing; the session falls back to Hyprland's example config" >&2
fi
