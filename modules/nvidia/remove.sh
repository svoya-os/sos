#!/usr/bin/env bash
# SOS module nvidia — remove our settings (the driver packages are removed by sos itself).
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
systemctl disable --now nvidia-cdi-refresh.path 2>/dev/null || true
rm -f /etc/modprobe.d/svoya-nvidia.conf /etc/modules-load.d/svoya-nvidia-uvm.conf \
  /usr/lib/systemd/system-sleep/svoya-nvidia-uvm /var/run/cdi/nvidia.yaml
sv_apt_track_remove
rm -f /etc/apt/sources.list.d/nvidia-container-toolkit.list /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
sv_run update-initramfs -u
sv_say "Reboot: the open-source nouveau driver takes over (no CUDA)." \
       "Перезагрузитесь: дальше работает открытый драйвер nouveau (без CUDA)."
