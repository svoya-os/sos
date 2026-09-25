#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# gpu-drivers.sh ROOT : NVIDIA drivers for the installed system.
#   1. the medium's pool: Canonical-signed prebuilt modules + userspace, no DKMS (works offline and
#      with Secure Boot, no MOK enrollment); branch chosen by PCI modalias (gpu_select.py)
#   2. otherwise, if online: `ubuntu-drivers install` (Canonical's own selection)
# AMD and Intel need nothing here (Mesa is part of the image; ROCm is a module).
# The result is recorded in /var/lib/svoya/gpu-install.json for the first-run wizard / sos doctor.
set -euo pipefail
# shellcheck source=installer/scripts/lib.sh
. /usr/lib/svoya/installer/lib.sh
need_root_arg "${1:-}"

record() { # METHOD BRANCH
    mkdir -p "$ROOT/var/lib/svoya"
    python3 - "$ROOT/var/lib/svoya/gpu-install.json" "$1" "$2" "${SOS_GPU_DRIVER:-}" "${SOS_GPU_DEVICES:-}" <<'PY'
import json, sys
path, method, branch, driver, devices = sys.argv[1:6]
json.dump({"vendor": "nvidia" if devices else None, "devices": devices.split(),
           "method": method, "branch": branch or None, "driver": driver or None},
          open(path, "w"), indent=1)
PY
}

eval "$(python3 /usr/lib/svoya/installer/gpu_select.py --json "$MEDIUM/pool/svoya-gpu.json" --format shell)"

if [ -z "${SOS_GPU_DEVICES:-}" ]; then
    log "no NVIDIA GPU found; nothing to install"
    record none ""
    exit 0
fi
log "NVIDIA GPU(s): $SOS_GPU_DEVICES"

if [ -n "${SOS_GPU_BRANCH:-}" ] && [ -s "$ROOT$POOL_LIST" ]; then
    log "installing NVIDIA $SOS_GPU_BRANCH ($SOS_GPU_DRIVER) from the medium"
    # shellcheck disable=SC2086 # package list is intentionally split
    if pool_apt install $SOS_GPU_PACKAGES; then
        record pool "$SOS_GPU_BRANCH"
        regen_initramfs
        exit 0
    fi
    warn "offline driver install failed"
fi

if online && in_target sh -c 'command -v ubuntu-drivers' >/dev/null; then
    log "installing the driver chosen by ubuntu-drivers (online)"
    in_target apt-get -q update
    if in_target ubuntu-drivers install; then
        record ubuntu-drivers ""
        regen_initramfs
        exit 0
    fi
    warn "ubuntu-drivers failed"
fi

warn "no NVIDIA driver installed; the open-source nouveau driver is used. Run 'sos doctor' later."
record none ""
exit 0
