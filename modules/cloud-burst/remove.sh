#!/usr/bin/env bash
# SOS module cloud-burst
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
sv_uv_tool_remove skypilot
sv_uv_tool_remove dstack
