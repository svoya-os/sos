#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Flathub, configured system-wide so the first-run wizard can offer one-click apps (e.g. Obsidian,
# md.obsidian.Obsidian). Nothing is installed from Flathub, and nothing contacts it until the user
# installs an app.
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

repo=$root/tmp/flathub.flatpakrepo
curl --fail --location --silent --show-error --retry 5 -o "$repo" "$FLATHUB_REPO_URL"
grep -q '^Url=https://dl.flathub.org/repo/' "$repo" || die "unexpected Flathub .flatpakrepo (no Url=)"
grep -q '^GPGKey=' "$repo" || die "Flathub .flatpakrepo has no GPGKey"
info "flathub.flatpakrepo sha256 $(sha256sum "$repo" | cut -d' ' -f1)"

in_chroot "$root" flatpak remote-add --system --if-not-exists flathub /tmp/flathub.flatpakrepo
rm -f "$repo"
in_chroot "$root" flatpak remotes --system --columns=name,url >&2
[ -z "$(in_chroot "$root" flatpak list --system --columns=application 2>/dev/null)" ] ||
    die "something was installed from Flathub; the image must not preinstall flatpaks"
