#!/usr/bin/env bash
# SOS module voice — speech runtimes in an isolated venv (/opt/svoya/venvs/voice). Idempotent.
# Speech models are downloaded only when you first use push-to-talk, after Jackson asks.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
# sherpa-onnx runs Parakeet TDT v3 (RU/EN/ET) on the CPU; chatterbox-tts brings PyTorch for the GPU
sv_venv voice sherpa-onnx soundfile chatterbox-tts
sv_say "Voice runtimes installed (≈3.5 GB with PyTorch). Models: Parakeet TDT v3 (CC-BY-4.0, attribution), Chatterbox (MIT), Qwen3-TTS (Apache-2.0)." \
       "Голосовые рантаймы установлены (≈3,5 ГБ с PyTorch). Модели: Parakeet TDT v3 (CC-BY-4.0, атрибуция), Chatterbox (MIT), Qwen3-TTS (Apache-2.0)."
