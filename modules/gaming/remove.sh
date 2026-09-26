#!/usr/bin/env bash
# SOS module gaming — the i386 architecture stays enabled (other packages may need it).
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
sv_apt_track_remove
[[ -f /usr/local/share/applications/steam.desktop ]] && sv_run rm -f /usr/local/share/applications/steam.desktop
sv_flatpak_remove com.heroicgameslauncher.hgl net.lutris.Lutris com.vysp3r.ProtonPlus io.github.ilya_zlobintsev.LACT
