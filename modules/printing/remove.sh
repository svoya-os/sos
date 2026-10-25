#!/usr/bin/env bash
# SOS module printing
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
for unit in cups-browsed.service ipp-usb.service; do
  if systemctl cat "$unit" >/dev/null 2>&1; then sv_run systemctl disable --now "$unit" || true; fi
done
exit 0
