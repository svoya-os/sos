#!/usr/bin/env bash
# SOS module voice — Jackson's ears and voice, all on this computer (v0.2 «Голос»). Idempotent.
# The runtime goes to a venv (/opt/svoya/venvs/voice), the models to the shared store
# (/srv/ai/voice): Silero VAD (MIT), Parakeet TDT 0.6B v3 (CC-BY-4.0) and GigaAM v3 (MIT) through
# onnx-asr (MIT) to listen; Supertonic 3 (code MIT, model OpenRAIL-M) to speak, fast on any processor.
# Jackson's own voices (Qwen3-TTS on an NVIDIA graphics card) come with the voice-gpu module.
# jacksond starts svoya-voice.service (svoya-jackson) the first time the microphone is pressed.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
engine=${SVOYA_VOICE_ENGINE:-supertonic}
sv_venv voice numpy "onnxruntime>=1.20" "onnx-asr[hub]>=0.10" huggingface_hub "supertonic==1.3.1"
install -d -m 0755 /srv/ai/voice
sv_run env PYTHONPATH=/usr/lib/svoya /opt/svoya/venvs/voice/bin/python -m jackson.voice.setup \
  --models /srv/ai/voice --engine "$engine"
sv_say "Voice installed: press the microphone in Jackson's panel, or hold Super+J. Models: Parakeet TDT 0.6B v3 (CC-BY-4.0, NVIDIA), GigaAM v3 (MIT, Sber), Silero VAD (MIT), Supertonic 3 (OpenRAIL-M, Supertone)." \
       "Голос установлен: нажми микрофон в панели Джексона или зажми Super+J. Модели: Parakeet TDT 0.6B v3 (CC-BY-4.0, NVIDIA), GigaAM v3 (MIT, Сбер), Silero VAD (MIT), Supertonic 3 (OpenRAIL-M, Supertone)."
[[ -d /srv/ai/voice/qwen3-tts ]] || case "${SVOYA_TORCH_BACKEND:-cpu}" in
  cu*) sv_say "This graphics card can give Jackson his own voice (Кентафурик): sos install voice-gpu" \
              "На этой видеокарте у Джексона может быть свой голос (Кентафурик): sos install voice-gpu" ;;
esac
