# shellcheck shell=bash
# SPDX-License-Identifier: Apache-2.0
# Helpers shared by packages/build-all.sh and the per-package prepare.sh scripts.

log()  { printf '\033[1;33m==>\033[0m %s\n' "$*" >&2; }
info() { printf '    %s\n' "$*" >&2; }
warn() { printf '\033[1;35mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# git_fetch_commit URL COMMIT DEST [SPARSE_PATH...]
# Shallow, blob-less fetch of exactly one commit (GitHub allows fetching reachable SHAs).
# With sparse paths only those paths are checked out (non-cone patterns).
git_fetch_commit() {
    local url=$1 commit=$2 dest=$3
    shift 3
    rm -rf "$dest"
    mkdir -p "$dest"
    git -C "$dest" init -q
    git -C "$dest" remote add origin "$url"
    if [ "$#" -gt 0 ]; then
        git -C "$dest" config core.sparseCheckout true
        git -C "$dest" sparse-checkout set --no-cone "$@"
    fi
    local attempt
    for attempt in 1 2 3; do
        if git -C "$dest" fetch -q --depth 1 --filter=blob:none origin "$commit"; then
            break
        fi
        [ "$attempt" = 3 ] && die "git fetch failed: $url@$commit"
        sleep $((attempt * 5))
    done
    git -C "$dest" -c advice.detachedHead=false checkout -q FETCH_HEAD
    local got
    got=$(git -C "$dest" rev-parse HEAD)
    [ "$got" = "$commit" ] || die "commit mismatch for $url: wanted $commit, got $got"
    rm -rf "$dest/.git"
}

# sha256_of FILE
sha256_of() { sha256sum "$1" | cut -d' ' -f1; }

# download URL DEST (retries, fails on HTTP errors)
download() {
    curl --fail --location --silent --show-error --retry 5 --retry-delay 5 -o "$2" "$1"
}
