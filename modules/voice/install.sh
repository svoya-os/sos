#!/usr/bin/env bash
# SOS module voice — Jackson's ears and voice, all on this computer (v0.2 «Голос»). Idempotent.
# The runtime goes to a venv (/opt/svoya/venvs/voice), the models to the shared store
# (/srv/ai/voice): Silero VAD (MIT) and Parakeet TDT 0.6B v3 (CC-BY-4.0) through onnx-asr (MIT).
# jacksond starts svoya-voice.service (svoya-jackson) the first time the microphone is pressed.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
engine=${SVOYA_VOICE_ENGINE:-none}
sv_venv voice numpy "onnxruntime>=1.20" "onnx-asr[hub]>=0.10" huggingface_hub
install -d -m 0755 /srv/ai/voice
sv_run env PYTHONPATH=/usr/lib/svoya /opt/svoya/venvs/voice/bin/python -m jackson.voice.setup \
  --models /srv/ai/voice --engine "$engine"
sv_say "Voice installed: press the microphone in Jackson's panel, or hold Super+J. Models: Parakeet TDT 0.6B v3 (CC-BY-4.0, NVIDIA), Silero VAD (MIT)." \
       "Голос установлен: нажми микрофон в панели Джексона или зажми Super+J. Модели: Parakeet TDT 0.6B v3 (CC-BY-4.0, NVIDIA), Silero VAD (MIT)."
