#!/usr/bin/env bash
# SOS module voice-gpu (as the user) — a running svoya-voice picks the new speech engine at once.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_user_systemctl try-restart svoya-voice.service
