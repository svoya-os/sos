#!/usr/bin/env bash
# SOS module ml-lab — notebooks, trackers and pixi (conda-forge only). Idempotent.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
for tool in jupyterlab marimo tensorboard mlflow trackio; do
  sv_uv_tool "$tool"
done
[[ "${SVOYA_OPT_LABEL_STUDIO:-}" == 1 ]] && sv_uv_tool --python 3.12 label-studio

# pixi: official release, sha256-verified; conda-forge only — never Anaconda "defaults"
if ! sv_have pixi; then
  sv_github_install prefix-dev/pixi "${SVOYA_PIXI_VERSION:-latest}" "pixi-$(sv_arch)-unknown-linux-musl\.tar\.gz" /usr/local/bin/pixi pixi
fi
sv_write /etc/pixi/config.toml <<'EOT'
# SOS ml-lab: conda-forge only. Anaconda's "defaults" channel needs a paid license for organisations > 200 people.
default-channels = ["conda-forge"]
EOT
sv_write /etc/conda/.condarc <<'EOT'
# SOS ml-lab: conda-forge only (no Anaconda "defaults")
channels:
  - conda-forge
channel_priority: strict
EOT
sv_say "ML Lab ready: jupyter lab · marimo · tensorboard · mlflow ui · trackio · pixi" \
       "ML-лаборатория готова: jupyter lab · marimo · tensorboard · mlflow ui · trackio · pixi"
