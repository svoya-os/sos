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
# Steam's runtime creates user namespaces (the requirements check at every start, pressure-vessel for
# games); Ubuntu allows that only under an AppArmor profile that says so. Without one Steam stopped
# with «Steam now requires user namespaces to be enabled» (the games bot found it).
sv_write /etc/apparmor.d/sos-steam <"$SVOYA_MODULE_DIR/files/sos-steam.apparmor"
if sv_have apparmor_parser && aa-enabled >/dev/null 2>&1; then
  sv_run apparmor_parser -r -W /etc/apparmor.d/sos-steam
fi
[[ "${SVOYA_OPT_HEROIC:-}" == 1 ]] && sv_flatpak_install com.heroicgameslauncher.hgl
[[ "${SVOYA_OPT_LUTRIS:-}" == 1 ]] && sv_flatpak_install net.lutris.Lutris
[[ "${SVOYA_OPT_PROTONPLUS:-}" == 1 ]] && sv_flatpak_install com.vysp3r.ProtonPlus
[[ "${SVOYA_OPT_LACT:-}" == 1 ]] && sv_flatpak_install io.github.ilya_zlobintsev.LACT
sv_say "Steam downloads its (proprietary) client from Valve on first start. In a game's launch options: gamemoderun mangohud %command%" \
       "Steam скачает свой (проприетарный) клиент у Valve при первом запуске. В параметрах запуска игры: gamemoderun mangohud %command%"
