#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Stage shell/ (without shell/hypr, which ships in svoya-session) and compute QML dependencies.
set -euo pipefail
: "${SVOYA_SRC:?}" "${PKG_DIR:?}"
src=$SVOYA_SRC/shell
dest=$PKG_DIR/files/usr/share/svoya/shell
mkdir -p "$dest"
if [ -d "$src" ]; then
    tar -C "$src" \
        --exclude=./hypr --exclude=./tests --exclude=./tools \
        --exclude='__pycache__' --exclude='*.pyc' --exclude='*.md' \
        -cf - . | tar -C "$dest" -xf -
    # PAM services the shell needs (e.g. the lock screen) ship with it.
    if [ -d "$src/assets/pam.d" ] && [ -n "$(ls -A "$src/assets/pam.d")" ]; then
        mkdir -p "$PKG_DIR/files/etc/pam.d"
        cp -a "$src/assets/pam.d/." "$PKG_DIR/files/etc/pam.d/"
    fi
else
    echo "warning: shell/ not found; building an empty svoya-shell" >&2
fi
python3 "$SVOYA_SRC/packages/lib/qml_deps.py" "$src" >"$PKG_DIR/debian/qml-deps"
echo "    QML dependencies: $(cat "$PKG_DIR/debian/qml-deps")" >&2
