#!/usr/bin/env bash
# SOS module base-ai — remove tools and settings. Models in /srv/ai are NEVER deleted here.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
rm -f /etc/profile.d/svoya-ai.sh /etc/environment.d/60-svoya-ai.conf
sv_uv_tool_remove huggingface_hub
sv_uv_tool_remove nvitop
sv_say "Your models were kept in ${SVOYA_AI_ROOT:-/srv/ai}. To free the space: sos models rm <repo> (or delete the folder yourself)." \
       "Модели остались в ${SVOYA_AI_ROOT:-/srv/ai}. Освободить место: sos models rm <repo> (или удалите папку сами)."
