#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# GitHub-hosted ubuntu-24.04 runners: free ~60 GB by deleting preinstalled toolchains we never use,
# then pick the filesystem with the most free space for the ISO work directory.
# Prints "work_dir=<path>" to $GITHUB_OUTPUT (and stdout).
set -euo pipefail

df -h / /mnt 2>/dev/null || true
sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc /usr/local/.ghcup \
    /opt/hostedtoolcache/CodeQL /usr/local/share/boost /usr/share/swift /usr/local/julia* \
    /usr/local/share/chromium /usr/local/share/powershell /opt/microsoft /opt/google \
    "${AGENT_TOOLSDIRECTORY:-/nonexistent}" || true
sudo docker image prune --all --force >/dev/null 2>&1 || true
sudo apt-get clean || true

best=/
best_free=$(df --output=avail -B1 / | tail -n1)
if [ -d /mnt ]; then
    mnt_free=$(df --output=avail -B1 /mnt | tail -n1)
    if [ "$mnt_free" -gt "$best_free" ]; then best=/mnt; best_free=$mnt_free; fi
fi
work=$best/sos-work
[ "$best" = / ] && work=/var/tmp/sos-work
sudo mkdir -p "$work"
sudo chown "$(id -u):$(id -g)" "$work"
echo "free on $best: $((best_free / 1024 / 1024 / 1024)) GiB"
df -h / /mnt 2>/dev/null || true
echo "work_dir=$work"
if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "work_dir=$work" >>"$GITHUB_OUTPUT"; fi
