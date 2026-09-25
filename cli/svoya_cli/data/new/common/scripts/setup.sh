#!/usr/bin/env bash
# Create the environment with the right PyTorch wheels for this GPU ({{ gpu.backend }}).
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync
