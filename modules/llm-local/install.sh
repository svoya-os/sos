#!/usr/bin/env bash
# SOS module llm-local — llama.cpp router over /srv/ai (+ optional engines). Idempotent.
# Nothing here starts by itself: the user unit is installed, not enabled ("AI never starts by itself").
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
AI=${SVOYA_AI_ROOT:-/srv/ai}
install -d -g ai -m 2775 "$AI/views/llama.cpp"
sv_write /usr/lib/systemd/user/svoya-llm.service <"$SVOYA_MODULE_DIR/files/svoya-llm.service"

if [[ "${SVOYA_OPT_OLLAMA:-}" == 1 ]]; then
  if ! sv_have ollama; then
    arch=amd64; [[ $(sv_arch) == aarch64 ]] && arch=arm64
    read -r name url sha <<<"$(sv_github_asset ollama/ollama "${SVOYA_OLLAMA_VERSION:-latest}" "ollama-linux-${arch}\.(tgz|tar\.zst)")"
    [[ -n "${url:-}" ]] || sv_die "no Ollama release asset for linux-$arch"
    tmpd=$(mktemp -d)
    sv_fetch "$url" "${sha:-}" "$tmpd/$name"
    install -d /opt/svoya/ollama
    case "$name" in
      *.tgz) sv_run tar -xzf "$tmpd/$name" -C /opt/svoya/ollama ;;
      *.tar.zst) sv_run tar --zstd -xf "$tmpd/$name" -C /opt/svoya/ollama ;;
    esac
    rm -rf "$tmpd"
    sv_run ln -sf /opt/svoya/ollama/bin/ollama /usr/local/bin/ollama
  fi
  getent passwd ollama >/dev/null || sv_run useradd --system --home-dir /var/lib/ollama --create-home \
    --shell /usr/sbin/nologin ollama
  for g in ai render video; do getent group "$g" >/dev/null && usermod -aG "$g" ollama; done
  install -d -o ollama -g ai -m 2775 "$AI/ollama"
  sv_write /etc/systemd/system/svoya-ollama.service <<EOT
[Unit]
Description=Ollama (SOS: localhost only, models in $AI/ollama)
After=network-online.target

[Service]
User=ollama
Group=ai
Environment=OLLAMA_HOST=127.0.0.1:11434
Environment=OLLAMA_MODELS=$AI/ollama
ExecStart=/usr/local/bin/ollama serve
Restart=on-failure
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=$AI/ollama /var/lib/ollama

[Install]
WantedBy=multi-user.target
EOT
  sv_run systemctl daemon-reload
  sv_say "Ollama installed (≈4 GB). It starts only when asked: systemctl start svoya-ollama" \
         "Ollama установлена (≈4 ГБ). Запускается только по просьбе: systemctl start svoya-ollama"
fi

if [[ "${SVOYA_OPT_LLAMA_SWAP:-}" == 1 ]] && ! sv_have llama-swap; then
  arch=amd64; [[ $(sv_arch) == aarch64 ]] && arch=arm64
  sv_github_install mostlygeek/llama-swap "${SVOYA_LLAMA_SWAP_VERSION:-latest}" "llama-swap_.*_linux_${arch}\.tar\.gz" /usr/local/bin/llama-swap llama-swap
fi

if [[ "${SVOYA_OPT_VLLM:-}" == 1 ]]; then
  case "${SVOYA_TORCH_BACKEND:-cpu}" in
    cu13*|rocm*) sv_venv vllm vllm && sv_run ln -sf /opt/svoya/venvs/vllm/bin/vllm /usr/local/bin/vllm ;;
    *) sv_warn "vLLM needs an NVIDIA Turing+ or ROCm GPU (backend ${SVOYA_TORCH_BACKEND:-cpu}) — skipped" ;;
  esac
fi

if [[ "${SVOYA_OPT_OPEN_WEBUI:-}" == 1 ]]; then
  sv_uv_tool --python 3.11 open-webui
  sv_say "Open WebUI: run 'open-webui serve --host 127.0.0.1'. Its license (≥0.6.6) requires keeping its branding." \
         "Open WebUI: 'open-webui serve --host 127.0.0.1'. Лицензия (≥0.6.6) требует сохранять их брендинг."
fi
sv_say "Local LLM server installed. Start it: systemctl --user start svoya-llm (API on 127.0.0.1:8080). Get a model: sos models suggest" \
       "Локальный сервер моделей установлен. Запуск: systemctl --user start svoya-llm (API на 127.0.0.1:8080). Модель: sos models suggest"
