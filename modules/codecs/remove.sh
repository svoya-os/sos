#!/usr/bin/env bash
# SOS module codecs
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
sv_apt_track_remove
