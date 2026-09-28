#!/bin/sh
# SOS: joins the image parts in this folder (*.iso.part00, *.iso.part01, …) into one .iso and checks
# it against SHA256SUMS. Linux and macOS:  sh sos-join.sh
set -eu
cd "$(dirname "$0")"
sum_of() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1
}
[ -f SHA256SUMS ] || { echo "SHA256SUMS is missing: download it from the same page, it is how the image is checked."; exit 1; }
found=0 bad=0
for first in *.iso.part00; do
    [ -e "$first" ] || continue
    found=1
    iso=${first%.part00}
    echo "Joining $iso ..."
    # only whole parts: a browser's unfinished download (…part01.part, …part01.crdownload) is not one
    cat "$iso".part[0-9][0-9] >"$iso"
    want=$(awk -v f="$iso" '{ n = $2; sub(/^\*/, "", n); if (n == f) { print $1; exit } }' SHA256SUMS)
    have=$(sum_of "$iso")
    if [ -z "$want" ]; then
        echo "SHA256SUMS has no sum for $iso: $have"; bad=1
    elif [ "$want" = "$have" ]; then
        echo "Done, the image is intact: $iso (you can delete the parts)"
    else
        echo "Checksum mismatch for $iso: a part did not download completely, or the files come from different"
        echo "builds. Download the parts and SHA256SUMS again."
        rm -f "$iso"; bad=1
    fi
done
[ "$found" = 1 ] || { echo "No image parts here (*.iso.part00)."; exit 1; }
exit "$bad"
