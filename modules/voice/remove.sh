#!/usr/bin/env bash
# SOS module voice — remove the runtime venv; the models in /srv/ai/voice stay (the store keeps
# models until you remove them there), svoya-voice.service no longer starts without the venv.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
rm -rf /opt/svoya/venvs/voice
