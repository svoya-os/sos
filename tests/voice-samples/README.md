# Jackson's voice: samples

Voice mode (v0.2 «Голос») lets Jackson answer out loud. Before choosing how he sounds, the same
lines (`lines.json`: a greeting, a report with numbers, a system check, in Russian and English)
are rendered in every candidate voice that can run on the user's computer:

| engine | what | license | where it runs |
|---|---|---|---|
| **qwen** | [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS): a voice for each of Jackson's characters is *designed* from a text description (`designs` in `lines.json`, 1.7B VoiceDesign) and then *cloned* by the Base model, so one voice speaks both languages; 0.6B is the size a CPU could run | Apache-2.0 | GPU; 0.6B on a fast CPU |
| **supertonic** | [Supertonic 3](https://github.com/supertone-oss-archive/supertonic), preset male voices M1–M5 | code MIT, model OpenRAIL-M | any CPU |
| **vosk** | [Vosk TTS](https://github.com/alphacep/vosk-tts), 5 Russian voices | Apache-2.0 | any CPU |
| **silero** | [Silero](https://github.com/snakers4/silero-models) `v5_cis_base_nostress` with [silero-stress](https://github.com/snakers4/silero-stress), Russian | MIT | any CPU |
| **kokoro** | [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), English voices | Apache-2.0 | any CPU |

Piper's Russian voices are left out: they are fine-tuned from a voice whose dataset allows
research use only, and one of them has a non-commercial dataset.

`score.py` transcribes every sample with the recognizer Jackson would listen with (Parakeet TDT
0.6B v3 through onnx-asr) and reports the character error rate and the real-time factor on the
runner's CPU. The workflow `.github/workflows/voice-samples.yml` runs both whenever this folder
changes and publishes the samples (Opus) with `results.md` to the `ci-screens` branch
(`evals/voice/<run>/`).
