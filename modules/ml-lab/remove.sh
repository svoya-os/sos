#!/usr/bin/env bash
# SOS module ml-lab — remove the tools (your notebooks and runs are untouched).
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
for tool in jupyterlab marimo tensorboard mlflow trackio label-studio; do sv_uv_tool_remove "$tool"; done
rm -f /usr/local/bin/pixi /etc/pixi/config.toml /etc/conda/.condarc
