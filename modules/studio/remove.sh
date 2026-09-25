#!/usr/bin/env bash
# SOS module studio — remove the launcher and image recipe. Your outputs in ~/.local/share/svoya/studio stay.
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
rm -rf /usr/lib/svoya/studio
rm -f /usr/local/bin/sos-studio
if [[ -n "${SVOYA_TARGET_USER:-}" ]] && sv_have podman; then
  sv_as_user podman rmi -f localhost/sos-studio:latest >/dev/null 2>&1 || true
fi
sv_say "Studio removed; your images and workflows stay in ~/.local/share/svoya/studio." \
       "Студия удалена; ваши картинки и воркфлоу остались в ~/.local/share/svoya/studio."
