#!/usr/bin/env bash
# SOS module gaming — Steam (i386) with the 32-bit graphics drivers games still load, gamepad rules,
# optional launchers from Flathub. Idempotent.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
if ! dpkg --print-foreign-architectures | grep -qx i386; then
  sv_run dpkg --add-architecture i386
  sv_run apt-get update
fi
extra=()
# Gamepads, Steam Controller and VR headsets work without root (udev rules).
sv_apt_available steam-devices && extra+=(steam-devices)
# 32-bit OpenGL/Vulkan: the Steam client and many games under Proton load 32-bit parts.
for p in libgl1-mesa-dri:i386 mesa-vulkan-drivers:i386; do
  sv_apt_available "$p" && extra+=("$p")
done
# NVIDIA: Mesa does not drive the card, the driver's own 32-bit libraries are needed (same branch).
# (dpkg-query fails when nothing matches: without `|| true` pipefail ended the install on every
# computer without NVIDIA — the games bot found it.)
nv=$(dpkg-query -W -f='${binary:Package} ${db:Status-Abbrev}\n' 'libnvidia-gl-*' 2>/dev/null |
  awk '$2 == "ii" && $1 !~ /:i386$/ { print $1; exit }') || true
if [[ -n "$nv" ]] && sv_apt_available "$nv:i386"; then
  extra+=("$nv:i386")
fi
sv_apt_track_install steam-installer "${extra[@]}"
# Debian names its launcher entry «Install Steam» (the package is steam-installer), and the launcher
# and the top bar kept saying so after Steam was installed (the games bot). The same entry as
# «Steam» in /usr/local/share, which comes first in XDG_DATA_DIRS; the packaged file stays as it is.
steam_entry=${SVOYA_STEAM_DESKTOP:-/usr/share/applications/steam.desktop}
if [[ -f "$steam_entry" ]]; then
  # the entry's own name only: the actions (Store, Library…) keep theirs
  awk '/^\[/ { main = ($0 == "[Desktop Entry]") }
       main && /^Name=/ { print "Name=Steam"; next }
       main && /^Name\[/ { next }
       { print }' "$steam_entry" |
    sv_write "${SVOYA_STEAM_DESKTOP_OVERRIDE:-/usr/local/share/applications/steam.desktop}"
fi
[[ "${SVOYA_OPT_HEROIC:-}" == 1 ]] && sv_flatpak_install com.heroicgameslauncher.hgl
[[ "${SVOYA_OPT_LUTRIS:-}" == 1 ]] && sv_flatpak_install net.lutris.Lutris
[[ "${SVOYA_OPT_PROTONPLUS:-}" == 1 ]] && sv_flatpak_install com.vysp3r.ProtonPlus
[[ "${SVOYA_OPT_LACT:-}" == 1 ]] && sv_flatpak_install io.github.ilya_zlobintsev.LACT
sv_say "Steam downloads its (proprietary) client from Valve on first start. In a game's launch options: gamemoderun mangohud %command%" \
       "Steam скачает свой (проприетарный) клиент у Valve при первом запуске. В параметрах запуска игры: gamemoderun mangohud %command%"
