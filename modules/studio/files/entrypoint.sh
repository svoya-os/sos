#!/bin/sh
# SOS Studio container entrypoint: custom-node dependencies go into a persistent venv on /data
# (layered over the image's packages), then ComfyUI starts. Published only on 127.0.0.1 by the host.
set -eu
VENV=/data/venv
[ -x "$VENV/bin/python" ] || python -m venv --system-site-packages "$VENV"
for req in /opt/ComfyUI/custom_nodes/*/requirements.txt; do
  [ -f "$req" ] || continue
  uv pip install --python "$VENV/bin/python" -r "$req" || echo "! could not install $req" >&2
done
exec "$VENV/bin/python" main.py --listen 0.0.0.0 --port 8188 \
  --extra-model-paths-config /srv/ai/views/comfyui/extra_model_paths.yaml \
  --user-directory /data/user --output-directory /data/output --input-directory /data/input
