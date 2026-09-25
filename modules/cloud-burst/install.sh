#!/usr/bin/env bash
# SOS module cloud-burst — SkyPilot and dstack as isolated tools. Idempotent.
# Credentials are never written here: `sky check` / `dstack config` store them where each tool expects,
# and Jackson keeps API keys in the Secret Service keyring.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
sv_uv_tool skypilot
sv_uv_tool dstack
sv_say "Cloud tools ready: sky (SkyPilot), dstack, rclone. Projects from 'sos new' include a sky.yaml." \
       "Облачные инструменты готовы: sky (SkyPilot), dstack, rclone. В проектах 'sos new' уже есть sky.yaml."
