#!/usr/bin/env bash
# SOS module voice-gpu — back to Supertonic: qwen-tts and PyTorch leave the voice venv, and the
# model folder goes too (it is what tells svoya-voice to use Jackson's own voice).
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
if [[ -x /opt/svoya/venvs/voice/bin/python ]] && sv_have uv; then
  sv_run uv pip uninstall --python /opt/svoya/venvs/voice/bin/python qwen-tts torchaudio torch || true
fi
rm -rf /srv/ai/voice/qwen3-tts /srv/ai/voice/qwen3-tts.part
