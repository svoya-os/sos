#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Release assets and some upload paths are limited to 2 GiB per file.
#   scripts/split-artifact.sh split FILE [PART_MIB]   -> FILE.partNN (only if needed) + SHA256SUMS
#   scripts/split-artifact.sh join  DIR               -> reassembles *.iso from parts, verifies SHA256SUMS
set -euo pipefail

cmd=${1:-}
case $cmd in
    split)
        file=$2
        part_mib=${3:-1900}
        dir=$(dirname "$file")
        name=$(basename "$file")
        size=$(stat -c %s "$file")
        (
            cd "$dir"
            if [ "$size" -gt $((part_mib * 1024 * 1024)) ]; then
                split --bytes="${part_mib}M" --numeric-suffixes=0 --suffix-length=2 "$name" "$name.part"
                sha256sum "$name" "$name".part* >SHA256SUMS
                rm -f "$name"
                echo "split $name into $(ls "$name".part* | wc -l) parts of <= ${part_mib} MiB"
                printf 'Reassemble with:  cat %s.part* > %s && sha256sum -c --ignore-missing SHA256SUMS\n' \
                    "$name" "$name" >"$name.README.txt"
            else
                sha256sum "$name" >SHA256SUMS
                echo "$name is small enough ($((size / 1024 / 1024)) MiB); not split"
            fi
        )
        ;;
    join)
        dir=${2:-.}
        cd "$dir"
        for first in *.part00; do
            [ -e "$first" ] || continue
            name=${first%.part00}
            cat "$name".part* >"$name"
            rm -f "$name".part*
            echo "reassembled $name"
        done
        sha256sum -c --ignore-missing SHA256SUMS
        ;;
    *)
        echo "usage: $0 split FILE [PART_MIB] | join DIR" >&2
        exit 2
        ;;
esac
