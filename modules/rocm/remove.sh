#!/usr/bin/env bash
# SOS module rocm — undo the optional parts (group membership is harmless and kept).
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
sv_flatpak_remove io.github.ilya_zlobintsev.LACT
