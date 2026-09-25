#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Download the pinned uv release and verify its checksum.
#   UV_SHA256_X86_64 set   -> must match (reproducible, recommended)
#   UV_SHA256_X86_64 empty -> checked against the .sha256 published next to the release (TOFU)
set -euo pipefail
: "${SVOYA_SRC:?}" "${PKG_DIR:?}"
# shellcheck source=packages/lib/common.sh
. "$SVOYA_SRC/packages/lib/common.sh"
# shellcheck source=packages/versions.env
. "$SVOYA_SRC/packages/versions.env"

asset=uv-x86_64-unknown-linux-gnu.tar.gz
base=https://github.com/astral-sh/uv/releases/download/$UV_VERSION
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
download "$base/$asset" "$work/$asset"
got=$(sha256_of "$work/$asset")
if [ -n "${UV_SHA256_X86_64:-}" ]; then
    [ "$got" = "$UV_SHA256_X86_64" ] || die "uv: sha256 mismatch ($got != $UV_SHA256_X86_64)"
else
    download "$base/$asset.sha256" "$work/$asset.sha256"
    want=$(cut -d' ' -f1 <"$work/$asset.sha256")
    [ "$got" = "$want" ] || die "uv: sha256 mismatch against published checksum"
    warn "uv: UV_SHA256_X86_64 is not pinned; verified against the published checksum: $got"
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
        echo "uv $UV_VERSION sha256: \`$got\` (pin UV_SHA256_X86_64 in packages/versions.env)" >>"$GITHUB_STEP_SUMMARY"
    fi
fi
tar -C "$work" -xzf "$work/$asset"
mkdir -p "$PKG_DIR/prebuilt"
install -m0755 "$work/uv-x86_64-unknown-linux-gnu/uv" "$work/uv-x86_64-unknown-linux-gnu/uvx" "$PKG_DIR/prebuilt/"
"$PKG_DIR/prebuilt/uv" --version >&2
