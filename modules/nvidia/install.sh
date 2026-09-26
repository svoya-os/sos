#!/usr/bin/env bash
# SOS module nvidia — driver extras: suspend/resume, CUDA after resume, containers (CDI). Idempotent.
# The driver packages themselves come from the manifest (Canonical-signed, branch chosen by sos).
# shellcheck source=../lib/common.sh
source "${SVOYA_LIB:?}/common.sh"
sv_require_root
: "${SVOYA_NVIDIA_BRANCH:?no NVIDIA GPU detected}"
# NVIDIA Container Toolkit repository key (pinned; used only if the engine archive lacks the toolkit)
NV_CTK_FPR=${NV_CTK_FPR:-C95B321B61E88C1809C4F759DDCAE044F796ECB0}

# 1. keep VRAM across sleep; open modules use kernel suspend notifiers; KMS for Wayland
{
  echo "# SOS nvidia module (sos modules remove nvidia deletes this file)"
  echo "options nvidia NVreg_PreserveVideoMemoryAllocations=1 NVreg_TemporaryFilePath=/var/tmp"
  [[ "${SVOYA_NVIDIA_OPEN:-1}" == 1 ]] && echo "options nvidia NVreg_UseKernelSuspendNotifiers=1"
  echo "options nvidia_drm modeset=1 fbdev=1"
} | sv_write /etc/modprobe.d/svoya-nvidia.conf
printf '# SOS: CUDA needs nvidia_uvm\nnvidia_uvm\n' | sv_write /etc/modules-load.d/svoya-nvidia-uvm.conf
for unit in nvidia-suspend.service nvidia-resume.service nvidia-hibernate.service; do
  if systemctl cat "$unit" >/dev/null 2>&1; then sv_run systemctl enable "$unit"; fi
done

# 2. after resume: reload nvidia_uvm and restart local AI services (otherwise CUDA fails)
sv_write /usr/lib/systemd/system-sleep/svoya-nvidia-uvm 0755 <"$SVOYA_MODULE_DIR/files/svoya-nvidia-uvm"

# 3. GPUs in podman/docker through CDI (toolkit ≥ 1.18 keeps the spec fresh by itself)
if ! sv_have nvidia-ctk; then
  if sv_apt_available nvidia-container-toolkit; then
    sv_run apt-get install -y nvidia-container-toolkit
  else
    key=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    tmp=$(mktemp)
    sv_run curl --proto '=https' -fsSL -o "$tmp" https://nvidia.github.io/libnvidia-container/gpgkey
    fpr=$(gpg --show-keys --with-colons "$tmp" 2>/dev/null | awk -F: '/^fpr/ {print $10; exit}') || true
    [[ "$fpr" == "$NV_CTK_FPR" ]] || { rm -f "$tmp"; sv_die "unexpected NVIDIA repository key ($fpr) — not adding it"; }
    gpg --dearmor <"$tmp" | sv_write "$key"
    rm -f "$tmp"
    echo "deb [signed-by=$key] https://nvidia.github.io/libnvidia-container/stable/deb/\$(ARCH) /" |
      sv_write /etc/apt/sources.list.d/nvidia-container-toolkit.list
    sv_run apt-get update
    sv_run apt-get install -y nvidia-container-toolkit
    install -d /var/lib/svoya/module-extra && echo nvidia-container-toolkit >>/var/lib/svoya/module-extra/nvidia.apt
  fi
fi
if sv_have nvidia-ctk; then
  sv_run nvidia-ctk cdi generate --output=/var/run/cdi/nvidia.yaml || sv_warn "CDI spec not generated yet (reboot first)"
  if systemctl cat nvidia-cdi-refresh.path >/dev/null 2>&1; then sv_run systemctl enable --now nvidia-cdi-refresh.path; fi
fi

# 4. the options above must be in the initramfs when the driver loads early
sv_run update-initramfs -u
sv_say "Reboot to load the driver. Check afterwards with: sos gpu" \
       "Перезагрузитесь, чтобы загрузился драйвер. Потом проверьте: sos gpu"
