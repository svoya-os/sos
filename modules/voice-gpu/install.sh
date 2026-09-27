#!/usr/bin/env bash
# SOS module voice-gpu — Jackson's own voices on an NVIDIA graphics card. Idempotent.
# Adds PyTorch (the CUDA build sos picked for this card) and qwen-tts to the voice module's venv
# and fetches Qwen3-TTS 0.6B Base into /srv/ai/voice/qwen3-tts; svoya-voice then speaks with it
# (jackson/voice/tts.py prefers it while the NVIDIA driver is loaded) and clones each character's
# voice from the clips shipped with Jackson. About 4 GB of PyTorch/CUDA wheels and 2 GB of model.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
case "${SVOYA_TORCH_BACKEND:-cpu}" in
  cu*) ;;
  *) sv_die "Jackson's own voice needs an NVIDIA graphics card with its driver (PyTorch backend: ${SVOYA_TORCH_BACKEND:-cpu})" ;;
esac
[[ -x /opt/svoya/venvs/voice/bin/python ]] || sv_die "the voice module comes first: sos install voice"
sv_venv voice torch torchaudio "qwen-tts==0.1.1"
sv_run env PYTHONPATH=/usr/lib/svoya /opt/svoya/venvs/voice/bin/python -m jackson.voice.setup \
  --models /srv/ai/voice --engine qwen3
sv_say "Jackson's own voice installed: Кентафурик by day, the calm one in the evening (j voice to change). Model: Qwen3-TTS 0.6B Base (Apache-2.0, Alibaba Qwen)." \
       "Свой голос Джексона установлен: днём Кентафурик, вечером спокойный (поменять: j voice). Модель: Qwen3-TTS 0.6B Base (Apache-2.0, Alibaba Qwen)."
