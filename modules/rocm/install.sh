#!/usr/bin/env bash
# SOS module rocm — GPU access for your account, APU memory advice, optional LACT. Idempotent.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
if [[ -n "${SVOYA_TARGET_USER:-}" && "$SVOYA_TARGET_USER" != root ]]; then
  for g in render video; do
    getent group "$g" >/dev/null || continue
    id -nG "$SVOYA_TARGET_USER" | tr ' ' '\n' | grep -qx "$g" || sv_run usermod -aG "$g" "$SVOYA_TARGET_USER"
  done
fi
if [[ "${SVOYA_AMD_GFX:-}" == gfx1151 ]]; then
  sv_say "Strix Halo: by default the GPU sees only part of your RAM. 'sos doctor' prints the kernel parameters for a larger GTT (applied only if you run them)." \
         "Strix Halo: по умолчанию ГП видит лишь часть ОЗУ. 'sos doctor' покажет параметры ядра для большего GTT (применяются, только если вы их запустите)."
fi
if [[ "${SVOYA_OPT_LACT:-}" == 1 ]]; then
  sv_flatpak_install io.github.ilya_zlobintsev.LACT
fi
sv_say "Log out and in once so the render/video groups apply." "Выйдите и войдите один раз, чтобы применились группы render/video."
