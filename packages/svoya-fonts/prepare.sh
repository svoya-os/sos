#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Fetch the pinned font releases by git (packages/versions.env) and stage them.
set -euo pipefail
: "${SVOYA_SRC:?}" "${PKG_DIR:?}"
# shellcheck source=packages/lib/common.sh
. "$SVOYA_SRC/packages/lib/common.sh"
# shellcheck source=packages/versions.env
. "$SVOYA_SRC/packages/versions.env"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
git_fetch_commit "$PLEX_REPO" "$PLEX_COMMIT" "$work/plex" \
    '/packages/plex-sans/fonts/complete/ttf/*' '/packages/plex-mono/fonts/complete/ttf/*' '/LICENSE.txt'
git_fetch_commit "$DEPARTURE_MONO_REPO" "$DEPARTURE_MONO_COMMIT" "$work/departure" \
    '/public/assets/DepartureMono-Regular.otf' '/public/assets/LICENSE'

f=$PKG_DIR/files
install -d "$f/usr/share/fonts/truetype/svoya-plex" "$f/usr/share/fonts/opentype/svoya-departure" \
    "$f/usr/share/doc/svoya-fonts"
install -m0644 "$work"/plex/packages/plex-sans/fonts/complete/ttf/IBMPlexSans-*.ttf "$f/usr/share/fonts/truetype/svoya-plex/"
install -m0644 "$work"/plex/packages/plex-mono/fonts/complete/ttf/IBMPlexMono-*.ttf "$f/usr/share/fonts/truetype/svoya-plex/"
install -m0644 "$work/departure/public/assets/DepartureMono-Regular.otf" "$f/usr/share/fonts/opentype/svoya-departure/"
install -m0644 "$work/plex/LICENSE.txt" "$f/usr/share/doc/svoya-fonts/OFL-IBM-Plex.txt"
install -m0644 "$work/departure/public/assets/LICENSE" "$f/usr/share/doc/svoya-fonts/OFL-Departure-Mono.txt"
n=$(find "$f/usr/share/fonts" -type f | wc -l)
[ "$n" -ge 10 ] || die "svoya-fonts: expected at least 10 font files, found $n"
echo "    $n font files staged" >&2
