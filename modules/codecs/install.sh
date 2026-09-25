#!/usr/bin/env bash
# SOS module codecs — hardware video decoding for the GPU in this machine. Idempotent.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
case "${SVOYA_GPU_VENDOR:-none}" in
  nvidia) sv_apt_available nvidia-vaapi-driver && sv_apt_track_install nvidia-vaapi-driver ;;
  intel) sv_apt_available intel-media-va-driver-non-free && sv_apt_track_install intel-media-va-driver-non-free ;;
esac
exit 0
