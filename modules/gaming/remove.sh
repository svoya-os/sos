#!/usr/bin/env bash
# SOS module gaming — the i386 architecture stays enabled (other packages may need it).
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
sv_apt_track_remove
if [[ -f /etc/apparmor.d/sos-steam ]]; then
  if sv_have apparmor_parser; then apparmor_parser -R /etc/apparmor.d/sos-steam 2>/dev/null || true; fi
  sv_run rm -f /etc/apparmor.d/sos-steam /var/cache/apparmor/*/sos-steam
fi
sv_flatpak_remove com.heroicgameslauncher.hgl net.lutris.Lutris com.vysp3r.ProtonPlus io.github.ilya_zlobintsev.LACT
