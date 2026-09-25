"""Doctor rules: pure functions ``Facts → Check``. Every check says what it saw (RU/EN) and, when
something is off, the exact fix. ``safe`` fixes are local and reversible (config files, module
loading, services, groups) and never download anything — ``sos fix`` applies only those, after a
snapshot. Everything else (drivers, kernel parameters, cabling) is shown as a command to run.
"""
from __future__ import annotations

import shlex
from dataclasses import dataclass, field

from ..hw import amd_db, nvidia_db
from ..hw.gpu import torch_backend
from .facts import SLEEP_HOOK, Facts

T = tuple[str, str]   # (en, ru)
GiB = 2**30
MODPROBE_FILE = "/etc/modprobe.d/svoya-nvidia.conf"
UVM_LOAD_FILE = "/etc/modules-load.d/svoya-nvidia-uvm.conf"
HOOK_PATH = f"/usr/lib/systemd/system-sleep/{SLEEP_HOOK}"
ZRAM_CONF = "/etc/systemd/zram-generator.conf"


@dataclass
class Fix:
    safe: bool
    commands: list[list[str]] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)          # system path → content (root)
    modes: dict[str, int] = field(default_factory=dict)
    user_files: dict[str, str] = field(default_factory=dict)     # user path → content
    root: bool = True
    note: T | None = None

    def lines(self) -> list[str]:
        out = [f"write {p}" for p in self.files] + [f"write {p}" for p in self.user_files]
        prefix = "sudo " if self.root else ""
        out += [prefix + shlex.join(c) if c[0] != "sos" else shlex.join(c) for c in self.commands]
        return out

    def as_json(self) -> dict:
        return {"safe": self.safe, "root": self.root, "commands": self.commands, "files": list(self.files),
                "userFiles": list(self.user_files), "display": self.lines(),
                "note": {"en": self.note[0], "ru": self.note[1]} if self.note else None}


@dataclass
class Check:
    id: str
    title: T
    status: str                  # ok | warn | fail | skip
    msg: T
    fix: Fix | None = None
    gpu: bool = True

    def as_json(self) -> dict:
        return {"id": self.id, "title": {"en": self.title[0], "ru": self.title[1]}, "status": self.status,
                "message": {"en": self.msg[0], "ru": self.msg[1]}, "gpu": self.gpu,
                "fix": self.fix.as_json() if self.fix else None}


def _nv(f: Facts):
    return next((g for g in f.gpus if g.vendor == "nvidia"), None)


def _amd(f: Facts):
    return next((g for g in f.gpus if g.vendor == "amd"), None)


def _major(v: str | None) -> int:
    t = nvidia_db.parse_version(v)
    return t[0] if t else 0


def recommendation(f: Facts) -> dict:
    """What the machine should run: driver packages, CUDA line, PyTorch backend."""
    g = f.primary
    out: dict = {"vendor": g.vendor if g else None, "name": g.name if g else None,
                 "torchBackend": torch_backend(g), "arch": None, "gfx": None}
    nv = _nv(f)
    if nv is not None and nv.arch_info:
        info = nv.arch_info
        out.update(arch=info.id, archName=info.name, cuda=info.cuda, branch=info.branch,
                   openModules=info.open_modules)
        if info.branch:
            out["packages"] = nvidia_db.driver_packages(info.branch, info.open_modules != "unsupported",
                                                        nvidia_db.kernel_flavor(f.kernel))
    amd = _amd(f)
    if amd is not None:
        out["gfx"] = amd.gfx
    return out


# ---------------------------------------------------------------- GPU presence & drivers

def check_detect(f: Facts) -> Check:
    t = ("graphics card", "видеокарта")
    if not f.gpus:
        return Check("gpu.detect", t, "warn", ("no GPU found — AI runs on the CPU (slow, but it works)",
                                              "видеокарта не найдена — ИИ пойдёт на процессоре (медленно, но работает)"))
    parts = []
    for g in f.gpus:
        arch = g.arch_info.name if g.arch_info else (g.gfx or "")
        kind = " (iGPU)" if g.integrated else ""
        parts.append(f"{g.name}{kind}" + (f" · {arch}" if arch else "") + f" · {g.pci.vendor_id:04x}:{g.pci.device_id:04x}")
    txt = "; ".join(parts)
    return Check("gpu.detect", t, "ok", (txt, txt))


def check_arch(f: Facts) -> Check:
    t = ("generation", "поколение")
    nv, amd = _nv(f), _amd(f)
    if nv is None and amd is None:
        return Check("gpu.arch", t, "skip", ("no NVIDIA/AMD GPU", "нет видеокарты NVIDIA/AMD"))
    if nv is not None:
        info = nv.arch_info
        if info is None:
            return Check("gpu.arch", t, "warn", (f"unknown NVIDIA device {nv.pci.device_id:04x} — assuming a new generation",
                                                f"неизвестное устройство NVIDIA {nv.pci.device_id:04x} — считаю новым поколением"))
        if info.branch is None:
            return Check("gpu.arch", t, "fail", (f"{info.name} is too old for current NVIDIA drivers; use the CPU or Vulkan via nouveau/NVK",
                                                f"{info.name} слишком старая для текущих драйверов NVIDIA; остаются процессор или Vulkan через nouveau/NVK"))
        if info.legacy:
            return Check("gpu.arch", t, "warn", (f"{info.name}: legacy — driver 580 is its last branch, CUDA 12.x (PyTorch cu126)",
                                                f"{info.name}: устаревшее — последняя ветка драйвера 580, CUDA 12.x (PyTorch cu126)"))
        return Check("gpu.arch", t, "ok", (f"{info.name} (compute {info.cc}) · CUDA {info.cuda}",
                                          f"{info.name} (compute {info.cc}) · CUDA {info.cuda}"))
    gfx = amd.gfx or "?"
    if gfx in amd_db.ROCM_SUPPORTED:
        return Check("gpu.arch", t, "ok", (f"{gfx} · supported by ROCm 7.1", f"{gfx} · поддерживается ROCm 7.1"))
    return Check("gpu.arch", t, "warn", (f"{gfx} · not officially supported by ROCm — llama.cpp Vulkan works",
                                        f"{gfx} · официально не поддерживается ROCm — llama.cpp на Vulkan работает"))


def check_nvidia_driver(f: Facts) -> Check:
    t = ("driver", "драйвер")
    nv = _nv(f)
    if nv is None:
        return Check("nvidia.driver", t, "skip", ("no NVIDIA GPU", "нет видеокарты NVIDIA"))
    rec = recommendation(f)
    pkgs = rec.get("packages") or []
    install = Fix(False, [["apt", "install", *pkgs]] if pkgs else [],
                  note=("then reboot", "затем перезагрузка")) if pkgs else None
    if f.nv_loaded and f.nv_version:
        kind = tr_kind(f.nv_open)
        return Check("nvidia.driver", t, "ok", (f"{f.nv_version} {kind[0]} loaded", f"{f.nv_version} {kind[1]} загружен"))
    if f.nouveau_loaded or nv.pci.driver == "nouveau":
        return Check("nvidia.driver", t, "fail", ("nouveau is driving the card: no CUDA", "работает nouveau: CUDA нет"), install)
    return Check("nvidia.driver", t, "fail", ("the NVIDIA driver is not loaded", "драйвер NVIDIA не загружен"), install)


def tr_kind(open_: bool | None) -> T:
    if open_ is None:
        return ("", "")
    return ("(open)", "(open)") if open_ else ("(proprietary)", "(проприетарный)")


def check_nvidia_branch(f: Facts) -> Check:
    t = ("driver branch", "ветка драйвера")
    nv = _nv(f)
    if nv is None or not f.nv_version or not nv.arch_info or not nv.arch_info.branch:
        return Check("nvidia.branch", t, "skip", ("not applicable", "не применимо"))
    info = nv.arch_info
    have, want = _major(f.nv_version), int(info.branch)
    pkgs = recommendation(f).get("packages") or []
    fix = Fix(False, [["apt", "install", *pkgs]], note=("then reboot", "затем перезагрузка")) if pkgs else None
    if info.id == "blackwell" and have < nvidia_db.BLACKWELL_MIN_DRIVER:
        return Check("nvidia.branch", t, "fail", (f"{f.nv_version} is too old for Blackwell (needs ≥ 570, recommended {want})",
                                                 f"{f.nv_version} слишком старый для Blackwell (нужен ≥ 570, рекомендуется {want})"), fix)
    if have < want:
        return Check("nvidia.branch", t, "warn", (f"{f.nv_version}; recommended branch is {want}",
                                                 f"{f.nv_version}; рекомендуемая ветка — {want}"), fix)
    return Check("nvidia.branch", t, "ok", (f"branch {have} (recommended {want})", f"ветка {have} (рекомендуется {want})"))


def check_nvidia_open(f: Facts) -> Check:
    t = ("kernel modules", "модули ядра")
    nv = _nv(f)
    if nv is None or not nv.arch_info or f.nv_open is None:
        return Check("nvidia.open", t, "skip", ("not applicable", "не применимо"))
    info = nv.arch_info
    pkgs = recommendation(f).get("packages") or []
    fix = Fix(False, [["apt", "install", *pkgs]], note=("replaces the current driver; reboot", "заменит текущий драйвер; перезагрузка")) if pkgs else None
    if info.open_modules == "required" and not f.nv_open:
        return Check("nvidia.open", t, "fail", ("Blackwell needs the open kernel modules", "Blackwell требует открытые модули ядра"), fix)
    if info.open_modules == "unsupported" and f.nv_open:
        return Check("nvidia.open", t, "fail", (f"open modules do not support {info.name}", f"открытые модули не поддерживают {info.name}"), fix)
    if info.open_modules == "recommended" and not f.nv_open:
        return Check("nvidia.open", t, "warn", ("open kernel modules are recommended for Turing and newer",
                                               "для Turing и новее рекомендуются открытые модули"), fix)
    return Check("nvidia.open", t, "ok", ("open" if f.nv_open else "proprietary (correct for this GPU)",
                                         "открытые" if f.nv_open else "проприетарные (верно для этой карты)"))


def check_secure_boot(f: Facts) -> Check:
    t = ("Secure Boot", "Secure Boot")
    nv = _nv(f)
    if f.secure_boot is None:
        return Check("boot.secureboot", t, "skip", ("state unknown (legacy BIOS?)", "состояние неизвестно (legacy BIOS?)"))
    if not f.secure_boot:
        return Check("boot.secureboot", t, "ok", ("off", "выключен"))
    if nv is None:
        return Check("boot.secureboot", t, "ok", ("on", "включён"))
    rec = recommendation(f)
    pkgs = rec.get("packages") or []
    fix = Fix(False, [["apt", "install", *pkgs]], note=("Canonical-signed modules: no MOK enrollment", "модули подписаны Canonical: без регистрации MOK")) if pkgs else None
    unsigned = f.nv_taint is not None and "E" in f.nv_taint
    if f.nv_module_kind == "dkms" and (not f.nv_loaded or unsigned):
        return Check("boot.secureboot", t, "fail", ("on, and the DKMS-built module is not signed by a trusted key",
                                                   "включён, а собранный DKMS модуль не подписан доверенным ключом"), fix)
    if f.nv_module_kind == "dkms":
        return Check("boot.secureboot", t, "warn", ("on; DKMS module works via an enrolled MOK — prebuilt signed modules are simpler",
                                                   "включён; модуль DKMS работает через MOK — готовые подписанные модули проще"), fix)
    return Check("boot.secureboot", t, "ok", ("on · signed prebuilt modules", "включён · подписанные готовые модули"))


def check_module_match(f: Facts) -> Check:
    t = ("driver ↔ kernel", "драйвер ↔ ядро")
    nv = _nv(f)
    if nv is None or not f.kernels:
        return Check("nvidia.kernel", t, "skip", ("not applicable", "не применимо"))
    newest = f.kernels[-1]
    rec = recommendation(f)
    branch = rec.get("branch") or nvidia_db.PRODUCTION_BRANCH
    sfx = "-open" if rec.get("openModules") not in (None, "unsupported") else ""
    missing = [k for k in f.kernels if not f.nv_module_for.get(k)]
    if newest in missing:
        return Check("nvidia.kernel", t, "fail",
                     (f"no NVIDIA module for kernel {newest}: after a reboot into it the driver will not load",
                      f"нет модуля NVIDIA для ядра {newest}: после перезагрузки в него драйвер не загрузится"),
                     Fix(False, [["apt", "install", f"linux-modules-nvidia-{branch}{sfx}-{newest}"]]))
    if f.kernel in missing and f.nv_loaded is False:
        return Check("nvidia.kernel", t, "fail", (f"no NVIDIA module for the running kernel {f.kernel}",
                                                 f"нет модуля NVIDIA для текущего ядра {f.kernel}"),
                     Fix(False, [["apt", "install", f"linux-modules-nvidia-{branch}{sfx}-{f.kernel}"]]))
    return Check("nvidia.kernel", t, "ok", (f"module present for {newest}", f"модуль есть для {newest}"))


def check_uvm(f: Facts) -> Check:
    t = ("nvidia_uvm (CUDA)", "nvidia_uvm (CUDA)")
    if _nv(f) is None or not f.nv_loaded:
        return Check("nvidia.uvm", t, "skip", ("not applicable", "не применимо"))
    if f.uvm_loaded and f.dev_uvm:
        return Check("nvidia.uvm", t, "ok", ("loaded, /dev/nvidia-uvm present", "загружен, /dev/nvidia-uvm на месте"))
    fix = Fix(True, [["modprobe", "nvidia_uvm"], ["nvidia-modprobe", "-u", "-c=0"]],
              files={UVM_LOAD_FILE: "# SOS: CUDA needs nvidia_uvm at boot\nnvidia_uvm\n"})
    return Check("nvidia.uvm", t, "fail", ("not loaded — CUDA programs fail with 'no CUDA-capable device'",
                                          "не загружен — CUDA-программы падают с «no CUDA-capable device»"), fix)


def check_modeset(f: Facts) -> Check:
    t = ("KMS for Wayland", "KMS для Wayland")
    if _nv(f) is None or not f.nv_loaded or f.nv_modeset is None:
        return Check("nvidia.modeset", t, "skip", ("not applicable", "не применимо"))
    if f.nv_modeset:
        return Check("nvidia.modeset", t, "ok", ("nvidia_drm modeset=1", "nvidia_drm modeset=1"))
    return Check("nvidia.modeset", t, "fail", ("nvidia_drm modeset is off — Hyprland needs it", "nvidia_drm modeset выключен — он нужен Hyprland"),
                 Fix(True, [["update-initramfs", "-u"]], files={MODPROBE_FILE: modprobe_conf(f)},
                     note=("takes effect after a reboot", "подействует после перезагрузки")))


def modprobe_conf(f: Facts) -> str:
    lines = ["# SOS (sos fix): NVIDIA settings for Wayland and suspend/resume",
             "options nvidia NVreg_PreserveVideoMemoryAllocations=1 NVreg_TemporaryFilePath=/var/tmp"]
    if f.nv_open:
        lines.append("options nvidia NVreg_UseKernelSuspendNotifiers=1")
    lines.append("options nvidia_drm modeset=1 fbdev=1")
    return "\n".join(lines) + "\n"


def check_suspend(f: Facts) -> Check:
    t = ("sleep & wake", "сон и пробуждение")
    if _nv(f) is None or not f.nv_loaded:
        return Check("nvidia.suspend", t, "skip", ("not applicable", "не применимо"))
    opts = f.modprobe.get("nvidia", {})
    problems_en, problems_ru = [], []
    if opts.get("NVreg_PreserveVideoMemoryAllocations") != "1":
        problems_en.append("VRAM is not preserved (NVreg_PreserveVideoMemoryAllocations)")
        problems_ru.append("видеопамять не сохраняется (NVreg_PreserveVideoMemoryAllocations)")
    if f.nv_open and opts.get("NVreg_UseKernelSuspendNotifiers") != "1":
        problems_en.append("open modules without NVreg_UseKernelSuspendNotifiers=1")
        problems_ru.append("открытые модули без NVreg_UseKernelSuspendNotifiers=1")
    units = ("nvidia-suspend.service", "nvidia-resume.service", "nvidia-hibernate.service")
    off = [u for u in units if f.services.get(u) not in ("enabled", "static", "alias")]
    if off and f.services:
        problems_en.append("disabled: " + ", ".join(off))
        problems_ru.append("выключены: " + ", ".join(off))
    if not problems_en:
        active = f.nv_params.get("PreserveVideoMemoryAllocations")
        if active not in (None, "1"):
            return Check("nvidia.suspend", t, "warn", ("configured; active after a reboot", "настроено; заработает после перезагрузки"))
        return Check("nvidia.suspend", t, "ok", ("VRAM preserved, suspend services on", "видеопамять сохраняется, службы сна включены"))
    cmds = [["systemctl", "enable", *units], ["update-initramfs", "-u"]]
    return Check("nvidia.suspend", t, "warn", ("; ".join(problems_en), "; ".join(problems_ru)),
                 Fix(True, cmds, files={MODPROBE_FILE: modprobe_conf(f)},
                     note=("reboot to apply", "применится после перезагрузки")))


def check_resume_hook(f: Facts, hook_source: str | None) -> Check:
    t = ("CUDA after resume", "CUDA после сна")
    if _nv(f) is None or not f.nv_loaded:
        return Check("nvidia.resume", t, "skip", ("not applicable", "не применимо"))
    if f.sleep_hook:
        return Check("nvidia.resume", t, "ok", ("nvidia_uvm is reloaded and AI services restarted after resume",
                                               "после сна nvidia_uvm перезагружается, ИИ-службы перезапускаются"))
    fix = Fix(True, files={HOOK_PATH: hook_source}, modes={HOOK_PATH: 0o755}) if hook_source else \
        Fix(False, [["sos", "install", "nvidia"]])
    return Check("nvidia.resume", t, "warn", ("no resume hook: CUDA breaks after sleep until nvidia_uvm is reloaded",
                                             "нет хука пробуждения: после сна CUDA ломается, пока не перезагрузить nvidia_uvm"), fix)


# ---------------------------------------------------------------- containers, Vulkan, compute

def check_containers(f: Facts) -> Check:
    t = ("GPU in containers", "ГП в контейнерах")
    if not (f.podman or f.docker):
        return Check("containers.gpu", t, "skip", ("no podman/docker", "нет podman/docker"))
    if _nv(f) is not None:
        if not f.ctk_version:
            return Check("containers.gpu", t, "warn", ("NVIDIA Container Toolkit is not installed", "NVIDIA Container Toolkit не установлен"),
                         Fix(False, [["sos", "install", "nvidia"]]))
        if nvidia_db.parse_version(f.ctk_version) < (1, 18):
            return Check("containers.gpu", t, "warn", (f"nvidia-ctk {f.ctk_version}; ≥ 1.18 refreshes CDI specs by itself",
                                                      f"nvidia-ctk {f.ctk_version}; ≥ 1.18 сам обновляет CDI-спецификации"),
                         Fix(False, [["apt", "install", "--only-upgrade", "nvidia-container-toolkit"]]))
        if not f.cdi_devices and not f.cdi_specs:
            return Check("containers.gpu", t, "warn", ("no CDI spec: `--device nvidia.com/gpu=all` will fail",
                                                      "нет CDI-спецификации: `--device nvidia.com/gpu=all` не сработает"),
                         Fix(True, [["nvidia-ctk", "cdi", "generate", "--output=/var/run/cdi/nvidia.yaml"],
                                    ["systemctl", "enable", "--now", "nvidia-cdi-refresh.path"]]))
        return Check("containers.gpu", t, "ok", (f"CDI ready ({len(f.cdi_devices) or len(f.cdi_specs)} entries)",
                                                f"CDI готов ({len(f.cdi_devices) or len(f.cdi_specs)} записей)"))
    if _amd(f) is not None:
        if f.kfd:
            return Check("containers.gpu", t, "ok", ("use --device /dev/kfd --device /dev/dri", "используйте --device /dev/kfd --device /dev/dri"))
        return Check("containers.gpu", t, "warn", ("/dev/kfd missing — ROCm containers will not see the GPU",
                                                  "/dev/kfd нет — контейнеры ROCm не увидят ГП"))
    return Check("containers.gpu", t, "skip", ("no discrete GPU", "нет дискретной видеокарты"))


ICD = {"nvidia": ("nvidia_icd.json", "libnvidia-gl-{branch}"), "amd": ("radeon_icd", "mesa-vulkan-drivers"),
       "intel": ("intel_icd", "mesa-vulkan-drivers")}


def check_vulkan(f: Facts) -> Check:
    t = ("Vulkan", "Vulkan")
    g = f.primary
    if g is None:
        return Check("vulkan.icd", t, "skip", ("no GPU", "нет видеокарты"))
    want, pkg = ICD.get(g.vendor, (None, None))
    if want is None:
        return Check("vulkan.icd", t, "skip", ("unknown vendor", "неизвестный производитель"))
    if any(want in x for x in f.vulkan_icds):
        return Check("vulkan.icd", t, "ok", (f"{want} present (llama.cpp Vulkan backend works)", f"{want} на месте (llama.cpp на Vulkan работает)"))
    branch = recommendation(f).get("branch") or nvidia_db.PRODUCTION_BRANCH
    return Check("vulkan.icd", t, "warn", (f"no {want} in /usr/share/vulkan/icd.d", f"нет {want} в /usr/share/vulkan/icd.d"),
                 Fix(False, [["apt", "install", pkg.format(branch=branch)]]))


def check_backend(f: Facts, user_env_path: str) -> Check:
    t = ("PyTorch backend", "бэкенд PyTorch")
    want = torch_backend(f.primary)
    have = f.uv_backend_env
    fix = Fix(True, root=False, user_files={user_env_path: f"# SOS (sos fix): PyTorch wheels for this GPU\nUV_TORCH_BACKEND={want}\n"},
              note=("applies to new sessions; `uv pip install torch` picks it up", "для новых сеансов; `uv pip install torch` его учтёт"))
    if have is None:
        if want == "cpu":
            why = ("UV_TORCH_BACKEND is not set; without a GPU PyTorch needs the cpu wheels",
                   "UV_TORCH_BACKEND не задан; без видеокарты PyTorch нужен в сборке cpu")
        else:
            why = (f"UV_TORCH_BACKEND is not set; this GPU needs {want}",
                   f"UV_TORCH_BACKEND не задан; этой видеокарте нужен {want}")
        return Check("compute.backend", t, "warn", why, fix)
    if have == "auto" and want in ("cu126",):
        return Check("compute.backend", t, "fail", ("uv 'auto' picks CUDA 12.8+ wheels that do not run on this GPU (uv #14742)",
                                                   "uv «auto» ставит колёса CUDA 12.8+, которые не работают на этой карте (uv #14742)"), fix)
    if have != want and have != "auto":
        return Check("compute.backend", t, "warn", (f"UV_TORCH_BACKEND={have}, recommended {want}",
                                                   f"UV_TORCH_BACKEND={have}, рекомендуется {want}"), fix)
    return Check("compute.backend", t, "ok", (f"UV_TORCH_BACKEND={have}", f"UV_TORCH_BACKEND={have}"))


def check_cuda(f: Facts) -> Check:
    t = ("CUDA compatibility", "совместимость CUDA")
    nv = _nv(f)
    if nv is None or not nv.arch_info or not f.nv_version:
        return Check("cuda.compat", t, "skip", ("not applicable", "не применимо"))
    info = nv.arch_info
    if info.cuda == "13.x" and _major(f.nv_version) < nvidia_db.CUDA13_MIN_DRIVER:
        pkgs = recommendation(f).get("packages") or []
        return Check("cuda.compat", t, "fail", (f"driver {f.nv_version} < 580: CUDA 13 (cu130 wheels) will not start",
                                               f"драйвер {f.nv_version} < 580: CUDA 13 (колёса cu130) не запустится"),
                     Fix(False, [["apt", "install", *pkgs]]) if pkgs else None)
    if info.cuda == "12.x":
        return Check("cuda.compat", t, "ok", ("CUDA 12.x line (cu126); CUDA 13 does not support this GPU",
                                             "линия CUDA 12.x (cu126); CUDA 13 эту карту не поддерживает"))
    return Check("cuda.compat", t, "ok", (f"driver {f.nv_version} runs CUDA 13.x", f"драйвер {f.nv_version} тянет CUDA 13.x"))


def check_prime(f: Facts) -> Check:
    t = ("desktop GPU", "ГП рабочего стола")
    igpu = next((g for g in f.gpus if g.integrated), None)
    dgpu = next((g for g in f.gpus if not g.integrated and g.vendor in ("nvidia", "amd")), None)
    if igpu is None or dgpu is None:
        return Check("gpu.prime", t, "skip", ("single GPU", "одна видеокарта"))
    first = (f.aq_drm_devices or "").split(":")[0]
    if first and (igpu.drm_card is None or first.endswith(f"/{igpu.drm_card}")):
        return Check("gpu.prime", t, "ok", ("the desktop runs on the iGPU; the dGPU is free for AI",
                                           "рабочий стол на встроенной; дискретная свободна для ИИ"))
    if f.boot_vga == igpu.pci.slot and not first:
        return Check("gpu.prime", t, "ok", ("the desktop starts on the iGPU", "рабочий стол стартует на встроенной"))
    order = ":".join(f"/dev/dri/{c}" for c in (igpu.drm_card, dgpu.drm_card) if c)
    return Check("gpu.prime", t, "warn",
                 ("the compositor runs on the dGPU and takes its VRAM; run the desktop on the iGPU (monitor on the motherboard port)",
                  "композитор работает на дискретной и занимает её видеопамять; лучше рабочий стол на встроенной (монитор — в разъём материнской платы)"),
                 Fix(False, [["sh", "-c", f"echo 'env = AQ_DRM_DEVICES,{order}' >> ~/.config/hypr/user.conf"]], root=False,
                     note=("then log out and back in", "затем выйти и войти снова")))


def check_rocm(f: Facts) -> Check:
    t = ("ROCm", "ROCm")
    amd = _amd(f)
    if amd is None:
        return Check("amd.rocm", t, "skip", ("no AMD GPU", "нет видеокарты AMD"))
    gfx = amd.gfx or (f.kfd_targets[0] if f.kfd_targets else None)
    if not f.kfd:
        return Check("amd.rocm", t, "warn", ("/dev/kfd missing — ROCm cannot see the GPU", "/dev/kfd нет — ROCm не видит ГП"),
                     Fix(False, [["sos", "install", "rocm"]]))
    if gfx in amd_db.ROCM_SUPPORTED:
        return Check("amd.rocm", t, "ok", (f"{gfx} supported", f"{gfx} поддерживается"))
    if gfx in amd_db.HSA_OVERRIDE:
        v = amd_db.HSA_OVERRIDE[gfx]
        return Check("amd.rocm", t, "warn", (f"{gfx} works only with HSA_OVERRIDE_GFX_VERSION={v} (unofficial); Vulkan is the safe path",
                                            f"{gfx} работает только с HSA_OVERRIDE_GFX_VERSION={v} (неофициально); надёжнее Vulkan"),
                     Fix(False, [["sh", "-c", f"echo HSA_OVERRIDE_GFX_VERSION={v} >> ~/.config/environment.d/60-svoya-rocm.conf"]], root=False))
    return Check("amd.rocm", t, "warn", (f"{gfx or 'this GPU'} is not supported by ROCm — use llama.cpp with Vulkan",
                                        f"{gfx or 'эта карта'} не поддерживается ROCm — используйте llama.cpp с Vulkan"))


def check_gtt(f: Facts) -> Check:
    t = ("iGPU memory (GTT)", "память iGPU (GTT)")
    amd = _amd(f)
    if amd is None or amd.gfx != amd_db.STRIX_HALO or not f.mem_total:
        return Check("amd.gtt", t, "skip", ("not a Strix Halo APU", "не APU Strix Halo"))
    want_gib = max(8, int(f.mem_total / GiB) - 8)
    pages = want_gib * 262144
    have = (f.ttm_pages_limit or 0) * 4096
    if "ttm.pages_limit" in f.cmdline or have >= 0.6 * f.mem_total:
        return Check("amd.gtt", t, "ok", (f"GPU may use ≈{int(have / GiB)} GB of RAM", f"ГП может брать ≈{int(have / GiB)} ГБ ОЗУ"))
    grub = f"GRUB_CMDLINE_LINUX_DEFAULT=\"$GRUB_CMDLINE_LINUX_DEFAULT ttm.pages_limit={pages} ttm.page_pool_size={pages}\""
    return Check("amd.gtt", t, "warn",
                 (f"the GPU may only use ≈{int(have / GiB)} GB; big models need ≈{want_gib} GB (kernel parameters)",
                  f"ГП доступно лишь ≈{int(have / GiB)} ГБ; большим моделям нужно ≈{want_gib} ГБ (параметры ядра)"),
                 Fix(False, [["sh", "-c", f"echo '{grub}' > /etc/default/grub.d/svoya-strix-halo.cfg && update-grub"]],
                     note=("kernel parameter change: reboot; undo by deleting the file", "меняет параметры ядра: перезагрузка; откат — удалить файл")))


def check_groups(f: Facts, store_group: str | None) -> Check:
    t = ("access groups", "группы доступа")
    need = []
    if f.gpus:
        need += ["render", "video"]
    if store_group:
        need.append(store_group)
    missing = [g for g in need if g not in f.user_groups]
    if not need:
        return Check("user.groups", t, "skip", ("nothing to check", "нечего проверять"))
    if not f.user_groups or not missing:
        return Check("user.groups", t, "ok" if f.user_groups else "skip",
                     (", ".join(need) or "—", ", ".join(need) or "—"))
    return Check("user.groups", t, "warn", (f"{f.user} is not in: {', '.join(missing)}", f"{f.user} не в группах: {', '.join(missing)}"),
                 Fix(True, [["usermod", "-aG", ",".join(missing), f.user]], note=("log out and back in", "выйти и войти снова")))


# ---------------------------------------------------------------- storage, memory, snapshots

def check_store(f: Facts) -> Check:
    t = ("model store /srv/ai", "хранилище /srv/ai")
    s = f.srv_ai
    if not s:
        return Check("storage.ai", t, "skip", ("not checked", "не проверялось"), gpu=False)
    if not s.get("exists"):
        cmds = []
        if f.root_fs == "btrfs":
            cmds.append(["btrfs", "subvolume", "create", s["path"]])
        else:
            cmds.append(["mkdir", "-p", s["path"]])
        cmds += [["groupadd", "-f", "ai"], ["chgrp", "ai", s["path"]], ["chmod", "2775", s["path"]]]
        return Check("storage.ai", t, "fail", ("missing — models have no shared home", "нет — у моделей нет общего дома"),
                     Fix(True, cmds), gpu=False)
    free = s.get("free")
    if free is not None and free < 10 * GiB:
        return Check("storage.ai", t, "fail", (f"only {free / GiB:.1f} GB free", f"свободно всего {free / GiB:.1f} ГБ"),
                     Fix(False, [["sos", "models", "dedup", "--apply"]]), gpu=False)
    if s.get("fstype") == "btrfs" and not s.get("subvolume"):
        return Check("storage.ai", t, "warn", ("not a separate btrfs subvolume: snapshots would carry model files",
                                              "не отдельный подтом btrfs: снимки будут тащить файлы моделей"), gpu=False)
    if free is not None and free < 50 * GiB:
        # a warning is for something to act on: say what gets tight, not that all is well
        return Check("storage.ai", t, "warn", (f"{free / GiB:.0f} GB free: room for a few models, not for large ones (30+ GB)",
                                              f"свободно {free / GiB:.0f} ГБ: на пару моделей хватит, на большие (30+ ГБ) — нет"),
                     gpu=False)
    txt = f"{(free or 0) / GiB:.0f} GB free" + (" · own subvolume" if s.get("subvolume") else "")
    txt_ru = f"свободно {(free or 0) / GiB:.0f} ГБ" + (" · свой подтом" if s.get("subvolume") else "")
    return Check("storage.ai", t, "ok", (txt, txt_ru), gpu=False)


def check_zram(f: Facts, generator_present: bool) -> Check:
    t = ("zram swap", "zram (сжатая память)")
    if any(s["name"].startswith("/dev/zram") for s in f.swaps):
        return Check("memory.zram", t, "ok", ("active", "работает"), gpu=False)
    conf = "[zram0]\nzram-size = min(ram / 2, 16384)\ncompression-algorithm = zstd\n"
    fix = Fix(True, [["systemctl", "daemon-reload"], ["systemctl", "start", "systemd-zram-setup@zram0.service"]],
              files={ZRAM_CONF: "# SOS (sos fix)\n" + conf}) if generator_present else \
        Fix(False, [["apt", "install", "systemd-zram-generator"]])
    msg = ("no zram: offloading big models to RAM will swap to disk instead", "zram нет: выгрузка больших моделей в ОЗУ уйдёт в своп на диске")
    return Check("memory.zram", t, "warn", msg, fix, gpu=False)


def check_snapper(f: Facts) -> Check:
    t = ("snapshots (undo)", "снимки (откат)")
    if f.root_fs != "btrfs":
        return Check("fs.snapper", t, "warn", (f"root is {f.root_fs or 'unknown'}, not btrfs: `sos undo` is unavailable",
                                              f"корень на {f.root_fs or 'неизвестной ФС'}, не btrfs: `sos undo` недоступен"), gpu=False)
    if not f.snapper:
        return Check("fs.snapper", t, "warn", ("snapper is not installed", "snapper не установлен"),
                     Fix(False, [["apt", "install", "snapper"]]), gpu=False)
    if not f.snapper_root:
        return Check("fs.snapper", t, "warn", ("snapper has no 'root' config", "у snapper нет конфигурации root"),
                     Fix(True, [["snapper", "-c", "root", "create-config", "/"]]), gpu=False)
    return Check("fs.snapper", t, "ok", ("btrfs + snapper", "btrfs + snapper"), gpu=False)


def check_recent_snapshot(f: Facts) -> Check:
    t = ("last snapshot", "последний снимок")
    if not (f.snapper and f.snapper_root):
        return Check("snapshots.recent", t, "skip", ("snapper not set up", "snapper не настроен"), gpu=False)
    fix = Fix(True, [["sos", "snapshot", "create", "--description", "doctor"]], root=False)
    if f.last_snapshot is None:
        return Check("snapshots.recent", t, "warn", ("none yet", "ещё не было"), fix, gpu=False)
    age = (f.now - f.last_snapshot).total_seconds() if f.now else 0
    days = age / 86400
    if days > 7:
        return Check("snapshots.recent", t, "warn", (f"{days:.0f} days ago", f"{days:.0f} дн. назад"), fix, gpu=False)
    return Check("snapshots.recent", t, "ok", (f"{age / 3600:.0f} h ago" if age < 172800 else f"{days:.0f} days ago",
                                              f"{age / 3600:.0f} ч назад" if age < 172800 else f"{days:.0f} дн. назад"), gpu=False)


def run_all(f: Facts, *, hook_source: str | None = None, user_env_path: str = "~/.config/environment.d/60-svoya-torch.conf",
            zram_generator: bool = False, gpu_only: bool = False) -> list[Check]:
    store_group = (f.srv_ai or {}).get("group") if (f.srv_ai or {}).get("group") not in (None, "root") else None
    checks = [
        check_detect(f), check_arch(f), check_nvidia_driver(f), check_nvidia_branch(f), check_nvidia_open(f),
        check_secure_boot(f), check_module_match(f), check_uvm(f), check_modeset(f), check_suspend(f),
        check_resume_hook(f, hook_source), check_containers(f), check_vulkan(f), check_backend(f, user_env_path),
        check_cuda(f), check_prime(f), check_rocm(f), check_gtt(f), check_groups(f, store_group),
    ]
    if not gpu_only:
        checks += [check_store(f), check_zram(f, zram_generator), check_snapper(f), check_recent_snapshot(f)]
    return checks
