#!/usr/bin/env bash
# SOS module voice — remove the runtime venv (downloaded voice models in /srv/ai stay).
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
rm -rf /opt/svoya/venvs/voice
