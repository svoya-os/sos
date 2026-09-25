#!/usr/bin/env bash
# Build the PFF2 bitmap fonts of the SOS GRUB theme from IBM Plex Mono. Run at package build time;
# needs grub-mkfont (package grub-common). It is not run in the design repository.
#
#   branding/grub/make-fonts.sh [PLEX_MONO_TTF] [OUT_DIR]
#
# Output: OUT_DIR/svoya-mono-regular-{14,16,24}.pf2 — GRUB font names "Svoya Mono Regular 14|16|24"
# (theme.txt uses 16 and 24; 14 is kept for small-screen variants and `loadfont` by hand).
# GRUB's 00_header loads every *.pf2 found next to theme.txt, so install them in the theme directory.
#
# Licensing: IBM Plex is SIL OFL 1.1 with the Reserved Font Name "Plex". A format conversion is a
# "Modified Version" (OFL definitions; OFL-FAQ 2.2/2.3), so the converted family must not be called
# "Plex": it is named "Svoya Mono". Ship IBM-Plex-OFL.txt next to the .pf2 files (this script copies it).
#
# Ranges: Basic Latin, Latin-1 + Latin Extended-A, Cyrillic (incl. Ё, Ї, Є, Ў…), general punctuation
# (— – « » … · • ‰), №, €, arrows (↑ ↓ ← →), box drawing and block elements (GRUB's text menus and
# progress), geometric shapes (▲ ▼ ■). Glyphs missing from the TTF are skipped by grub-mkfont.
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="${1:-$here/../../design/fonts/IBMPlexMono-Regular.ttf}"
out="${2:-$here/svoya}"
# grub-mkfont takes only FROM-TO pairs: a single code point is written as a one-character range
# (a bare 0x2116 is "invalid font range", and then the theme had no fonts at all).
ranges="0x20-0x7E,0xA0-0x17F,0x400-0x4FF,0x2010-0x2027,0x2030-0x203A,0x2116-0x2116,0x20AC-0x20AC,0x2190-0x21FF,0x2212-0x2212,0x2500-0x257F,0x2580-0x259F,0x25A0-0x25FF"

command -v grub-mkfont >/dev/null || { echo "grub-mkfont not found (install grub-common)" >&2; exit 1; }
mkdir -p "$out"
for size in 14 16 24; do
    grub-mkfont --name="Svoya Mono" --size="$size" --range="$ranges" \
        --output="$out/svoya-mono-regular-$size.pf2" "$src"
done
cp "$(dirname "$src")/IBM-Plex-OFL.txt" "$out/Svoya-Mono-OFL.txt" 2>/dev/null || true
echo "fonts in $out:"; ls -1 "$out"/*.pf2
