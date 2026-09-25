#!/usr/bin/env bash
# SOS module studio — ComfyUI sandbox (podman). The image is built on the first `sos-studio start`,
# so installing the module costs little; the build downloads ≈ 8–10 GB (Python + PyTorch + ComfyUI).
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
sv_write /usr/lib/svoya/studio/Containerfile <"$SVOYA_MODULE_DIR/files/Containerfile"
sv_write /usr/lib/svoya/studio/entrypoint.sh 0755 <"$SVOYA_MODULE_DIR/files/entrypoint.sh"
sv_write /usr/local/bin/sos-studio 0755 <"$SVOYA_MODULE_DIR/files/sos-studio"
install -d -g ai -m 2775 "${SVOYA_AI_ROOT:-/srv/ai}/views/comfyui"
sv_say "Studio installed. Start: sos-studio start → http://127.0.0.1:8188 (localhost only). Add nodes: sos-studio node-add <git-url> (snapshot + audit first)." \
       "Студия установлена. Запуск: sos-studio start → http://127.0.0.1:8188 (только localhost). Узлы: sos-studio node-add <git-url> (сначала снимок и аудит)."
