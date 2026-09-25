#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# finalize.sh ROOT : last installer step.
#   - snapper config for / and the first snapshot ("SOS installed")
#   - /srv/ai (@ai): group "ai", setgid + ACLs, no btrfs compression (models do not compress)
#   - first-run flag for the wizard: /var/lib/svoya/first-run + /var/lib/svoya/install.json
#   - remove live-only packages and files, the private pool APT config, unmount the medium
set -euo pipefail
# shellcheck source=installer/scripts/lib.sh
. /usr/lib/svoya/installer/lib.sh
need_root_arg "${1:-}"

# --- model store --------------------------------------------------------------------------------
in_target systemd-tmpfiles --create /usr/lib/tmpfiles.d/svoya.conf || warn "tmpfiles for /srv/ai failed"
if [ "$(findmnt -no FSTYPE "$ROOT/srv/ai" 2>/dev/null)" = btrfs ]; then
    in_target btrfs property set /srv/ai compression none 2>/dev/null ||
        in_target chattr +m /srv/ai 2>/dev/null || true
fi

# --- remove what only the live session needed ----------------------------------------------------
if [ -f "$ROOT/usr/share/svoya/live-packages.list" ]; then
    mapfile -t live < <(grep -v '^\s*$' "$ROOT/usr/share/svoya/live-packages.list")
    purge=()
    for p in "${live[@]}"; do
        if target_installed "$p"; then purge+=("$p"); fi
    done
    if [ "${#purge[@]}" -gt 0 ]; then
        log "removing live-only packages: ${purge[*]}"
        in_target apt-get -y -q purge --autoremove "${purge[@]}" || warn "could not purge all live packages"
    fi
fi
while read -r path; do
    case $path in /*) rm -f "$ROOT$path" ;; esac
done < <(grep -v '^\s*#' /usr/share/svoya/live-exclude.rsync 2>/dev/null || true)
rm -f "$ROOT/etc/svoya/live" "$ROOT/etc/svoya/greetd-live.toml"

# --- snapshots (after the cleanup, so the first snapshot is the clean installed system) ---------
if [ -x "$ROOT/usr/lib/svoya/setup-snapper" ]; then
    in_target /usr/lib/svoya/setup-snapper || warn "snapper setup failed; run 'sos doctor' after the first boot"
fi

# --- first run ------------------------------------------------------------------------------------
mkdir -p "$ROOT/var/lib/svoya"
: >"$ROOT/var/lib/svoya/first-run"
fw=bios
[ -d /sys/firmware/efi ] && fw=efi
encrypted=false
[ -s "$ROOT/etc/crypttab" ] && encrypted=true
fs=$(findmnt -no FSTYPE "$ROOT" || echo unknown)
python3 - "$ROOT/var/lib/svoya/install.json" "$fw" "$encrypted" "$fs" <<'PY'
import datetime, json, pathlib, sys
path, fw, encrypted, fs = sys.argv[1:5]
info = {}
for line in pathlib.Path("/etc/os-release").read_text().splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        info[k] = v.strip('"')
disk_info = pathlib.Path("/run/sos-installer/medium/.disk/info")
json.dump({
    "installedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "version": info.get("VERSION_ID"),
    "medium": disk_info.read_text().strip() if disk_info.exists() else None,
    "firmware": fw,
    "encrypted": encrypted == "true",
    "rootFilesystem": fs,
}, open(path, "w"), indent=1, ensure_ascii=False)
PY

# --- APT and medium --------------------------------------------------------------------------------
rm -rf "$ROOT$POOL_LIST" "$ROOT$POOL_PARTS" "${ROOT:?}/var/lib/sos-installer"
if [ -f /root/.cache/calamares/session.log ]; then
    install -Dm0600 /root/.cache/calamares/session.log "$ROOT/var/log/installer/calamares.log"
fi
if mountpoint -q "$ROOT$TARGET_MEDIUM"; then umount "$ROOT$TARGET_MEDIUM" || umount -l "$ROOT$TARGET_MEDIUM"; fi
rmdir "$ROOT$TARGET_MEDIUM" 2>/dev/null || true
log "installation finalized"
