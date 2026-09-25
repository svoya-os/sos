#!/usr/bin/env bash
# SOS module gaming — Steam (i386), optional launchers from Flathub. Idempotent.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
if ! dpkg --print-foreign-architectures | grep -qx i386; then
  sv_run dpkg --add-architecture i386
  sv_run apt-get update
fi
sv_apt_track_install steam-installer
[[ "${SVOYA_OPT_HEROIC:-}" == 1 ]] && sv_flatpak_install com.heroicgameslauncher.hgl
[[ "${SVOYA_OPT_LUTRIS:-}" == 1 ]] && sv_flatpak_install net.lutris.Lutris
[[ "${SVOYA_OPT_LACT:-}" == 1 ]] && sv_flatpak_install io.github.ilya_zlobintsev.LACT
sv_say "Steam downloads its (proprietary) client from Valve on first start." \
       "Steam скачает свой (проприетарный) клиент у Valve при первом запуске."
