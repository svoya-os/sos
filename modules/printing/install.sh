#!/usr/bin/env bash
# SOS module printing — printers on the network and on USB, scanners. Idempotent.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
# The image keeps printer discovery off: no network traffic nobody asked for (ARCHITECTURE §7).
# Installing this module is the asking.
for unit in cups.socket cups.service cups-browsed.service ipp-usb.service; do
  if systemctl cat "$unit" >/dev/null 2>&1; then
    sv_run systemctl enable --now "$unit" || sv_warn "$unit did not start"
  fi
done
sv_say "Printers on your network appear by themselves; add others in «Print settings» (system-config-printer)." \
       "Принтеры в сети появятся сами; другие — в окне «Настройки печати» (system-config-printer)."
exit 0
