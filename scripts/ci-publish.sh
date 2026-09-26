#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Publish a folder to the ci-screens branch (never main), readable without logging in:
#   scripts/ci-publish.sh <folder> <path in the branch> <commit message>
# Needs GH_TOKEN and REPO (CI_PUBLISH_URL instead, for tests). Several jobs of one run publish at
# the same time: each one rebases its commit onto the others' and pushes again.
#
# ISO #11 lost the safe-graphics screenshots that way: the rebase had no committer (the identity was
# given to `commit` only), stopped on the other job's commit, and the push of that commit reported
# success. The identity now belongs to the clone, and only a HEAD carrying our own commit is pushed.
set -uo pipefail
src=${1:?folder} dest=${2:?path in the branch} msg=${3:?commit message}
url=${CI_PUBLISH_URL:-https://x-access-token:${GH_TOKEN:?}@github.com/${REPO:?}.git}
[ -d "$src" ] || { echo "ci-publish: no $src"; exit 0; }

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
if ! git clone -q --depth 1 --branch ci-screens "$url" "$work" 2>/dev/null; then
    git init -q -b ci-screens "$work"            # the first publish creates the branch
    git -C "$work" remote add origin "$url"
fi
git -C "$work" config user.name sos-ci
git -C "$work" config user.email sos-ci@users.noreply.github.com
mkdir -p "$work/$dest"
cp -r "$src"/. "$work/$dest"/
git -C "$work" add -A
git -C "$work" commit -q -m "$msg" || { echo "ci-publish: nothing new for $dest"; exit 0; }

for i in 1 2 3 4 5 6 7 8; do
    # a rebase that stops leaves HEAD on someone else's commit: abort it and try again later
    git -C "$work" pull -q --rebase origin ci-screens 2>/dev/null || git -C "$work" rebase --abort 2>/dev/null
    if [ "$(git -C "$work" log -1 --format=%s)" = "$msg" ] && git -C "$work" push -q origin HEAD:ci-screens; then
        echo "ci-publish: $dest → ci-screens"
        exit 0
    fi
    sleep $((i * 4))
done
echo "::warning::ci-publish: $dest did not reach the ci-screens branch"
exit 0
