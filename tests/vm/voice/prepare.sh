#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# On the CI host, before the voice bot boots the VM (tests/vm/voice.json "serve"): the phrases it
# will say into the VM's virtual microphone, in a natural Russian voice (Vosk TTS, Apache-2.0).
set -euo pipefail
dir=${1:?folder to put the phrases in}
venv=$(mktemp -d)
python3 -m venv "$venv"
"$venv/bin/pip" install --quiet vosk-tts
"$venv/bin/python" - "$dir" <<'PY'
import sys
from vosk_tts import Model, Synth

synth = Synth(Model(model_name="vosk-model-tts-ru-0.9-multi"))
synth.synth("Который час?", f"{sys.argv[1]}/q1.wav", speaker_id=2)
synth.synth("Спасибо, всё.", f"{sys.argv[1]}/q2.wav", speaker_id=2)
PY
rm -rf "$venv"
ls -l "$dir"
