#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Make /dev/kvm usable by the runner user (GitHub's documented udev rule for hosted runners).
set -euo pipefail
echo 'KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"' |
    sudo tee /etc/udev/rules.d/99-kvm4all.rules >/dev/null
sudo udevadm control --reload-rules
sudo udevadm trigger --name-match=kvm
sleep 1
if [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
    echo "KVM available"
else
    echo "::warning::/dev/kvm is not usable; QEMU falls back to TCG (much slower)"
fi
