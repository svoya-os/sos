#!/usr/bin/env bash
# SOS module llm-local — remove engines and units. Models in /srv/ai are kept.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
rm -f /usr/lib/systemd/user/svoya-llm.service
if [[ -f /etc/systemd/system/svoya-ollama.service ]]; then
  systemctl disable --now svoya-ollama.service 2>/dev/null || true
  rm -f /etc/systemd/system/svoya-ollama.service
  systemctl daemon-reload
fi
rm -rf /opt/svoya/ollama /opt/svoya/venvs/vllm
rm -f /usr/local/bin/ollama /usr/local/bin/llama-swap /usr/local/bin/vllm
sv_uv_tool_remove open-webui
getent passwd ollama >/dev/null && userdel ollama 2>/dev/null || true
sv_say "Engines removed; models stay in ${SVOYA_AI_ROOT:-/srv/ai}." "Движки удалены; модели остались в ${SVOYA_AI_ROOT:-/srv/ai}."
