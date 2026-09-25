#!/usr/bin/env bash
# SOS module base-ai — the shared model store and core tools. Idempotent.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
AI=${SVOYA_AI_ROOT:-/srv/ai}

# 1. /srv/ai: its own btrfs subvolume (so root snapshots never carry model files), group "ai", setgid
getent group ai >/dev/null || sv_run groupadd --system ai
if [[ ! -d "$AI" ]]; then
  if [[ $(stat -f -c %T "$(dirname "$AI")") == btrfs ]]; then
    sv_run btrfs subvolume create "$AI"
  else
    sv_run install -d "$AI"
  fi
fi
sv_run chgrp ai "$AI"
sv_run chmod 2775 "$AI"
install -d -g ai -m 2775 "$AI/hub" "$AI/datasets" "$AI/views"
if [[ -n "${SVOYA_TARGET_USER:-}" && "${SVOYA_TARGET_USER}" != root ]]; then
  id -nG "$SVOYA_TARGET_USER" | tr ' ' '\n' | grep -qx ai || sv_run usermod -aG ai "$SVOYA_TARGET_USER"
fi

# 2. every tool shares one Hugging Face cache under /srv/ai (llama.cpp, ComfyUI, hf, transformers)
sv_write /etc/profile.d/svoya-ai.sh <<EOT
# SOS base-ai: one model store for every tool
export HF_HOME=$AI
EOT
sv_write /etc/environment.d/60-svoya-ai.conf <<EOT
# SOS base-ai: one model store for every tool (systemd user sessions)
HF_HOME=$AI
EOT

# 3. uv — from the engine archive when packaged, else the official release, sha256-verified
if ! sv_have uv; then
  if sv_apt_available uv; then
    sv_run apt-get install -y uv
  else
    sv_github_install astral-sh/uv "${SVOYA_UV_VERSION:-latest}" "uv-$(sv_arch)-unknown-linux-gnu\.tar\.gz" /usr/local/bin/uv uv
    printf '#!/bin/sh\nexec uv tool run "$@"\n' | sv_write /usr/local/bin/uvx 0755
  fi
fi

# 4. hf (Hugging Face CLI) and nvitop as isolated tools
sv_have hf || sv_uv_tool huggingface_hub
sv_have nvitop || sv_uv_tool nvitop

sv_say "Model store ready: $AI (group ai). Log out and in once so your account joins the group." \
       "Хранилище готово: $AI (группа ai). Выйдите и войдите один раз, чтобы учётная запись вошла в группу."
