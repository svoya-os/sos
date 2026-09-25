"""Everything the doctor looks at, gathered once. All probes go through ``ctx`` (fake root + fake
runner in tests) and never raise: a probe that cannot run leaves its fact as ``None``."""
from __future__ import annotations

import datetime as dt
import glob
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from ..context import Ctx
from ..hw import amd_db
from ..hw import gpu as gpu_mod
from ..util import version_key

NV_SERVICES = ("nvidia-suspend.service", "nvidia-resume.service", "nvidia-hibernate.service",
               "nvidia-cdi-refresh.path", "nvidia-persistenced.service")
SLEEP_HOOK = "svoya-nvidia-uvm"
SECUREBOOT_VAR = "/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-e0c16a4c8f68"


@dataclass
class Facts:
    kernel: str = ""
    gpus: list = field(default_factory=list)
    primary: object = None
    # NVIDIA
    nv_loaded: bool = False
    nv_version: str | None = None
    nv_open: bool | None = None
    nv_taint: str | None = None
    nv_params: dict = field(default_factory=dict)
    nv_modeset: bool | None = None
    nouveau_loaded: bool = False
    uvm_loaded: bool = False
    dev_uvm: bool = False
    nv_module_kind: str | None = None            # prebuilt | dkms | None
    kernels: list = field(default_factory=list)  # installed kernel releases, newest last
    nv_module_for: dict = field(default_factory=dict)   # kernel → bool
    modprobe: dict = field(default_factory=dict)        # module → {option: value}
    services: dict = field(default_factory=dict)        # unit → is-enabled state
    sleep_hook: bool = False
    secure_boot: bool | None = None
    # containers
    ctk_version: str | None = None
    cdi_specs: list = field(default_factory=list)
    cdi_devices: list = field(default_factory=list)
    podman: bool = False
    docker: bool = False
    # graphics stack
    vulkan_icds: list = field(default_factory=list)
    boot_vga: str | None = None
    aq_drm_devices: str | None = None
    # compute
    uv_backend_env: str | None = None
    uv_present: bool = False
    kfd: bool = False
    kfd_targets: list = field(default_factory=list)
    ttm_pages_limit: int | None = None
    cmdline: str = ""
    # user & storage
    user: str = ""
    user_groups: list = field(default_factory=list)
    srv_ai: dict = field(default_factory=dict)
    swaps: list = field(default_factory=list)
    mem_total: int | None = None
    root_fs: str | None = None
    snapper: bool = False
    snapper_root: bool = False
    last_snapshot: dt.datetime | None = None
    now: dt.datetime | None = None


def _yn(v: str | None) -> bool | None:
    if v is None:
        return None
    v = v.strip().upper()
    return v in ("Y", "1", "YES") if v else None


def parse_modprobe(texts: list[str]) -> dict:
    out: dict[str, dict[str, str]] = {}
    for text in texts:
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            m = re.match(r"^options\s+(\S+)\s+(.*)$", line)
            if not m:
                continue
            mod = m.group(1).replace("-", "_")
            for kv in m.group(2).split():
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    out.setdefault(mod, {})[k] = v
    return out


def parse_nv_params(text: str) -> dict:
    """``/proc/driver/nvidia/params``: ``PreserveVideoMemoryAllocations: 1``."""
    out = {}
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def parse_swaps(text: str) -> list[dict]:
    out = []
    for line in text.splitlines()[1:]:
        f = line.split()
        if len(f) >= 3:
            out.append({"name": f[0], "type": f[1], "sizeKiB": int(f[2]) if f[2].isdigit() else 0})
    return out


def mount_for(path: str, mounts_text: str) -> tuple[str | None, str | None]:
    """Longest mount point containing ``path`` → (mountpoint, fstype)."""
    best: tuple[str | None, str | None] = (None, None)
    for line in mounts_text.splitlines():
        f = line.split()
        if len(f) < 3:
            continue
        mp = f[1].replace("\\040", " ")
        if (path == mp or path.startswith(mp.rstrip("/") + "/") or mp == "/") and \
                (best[0] is None or len(mp) > len(best[0])):
            best = (mp, f[2])
    return best


def gather(ctx: Ctx, *, gpu_only: bool = False) -> Facts:
    r = ctx.runner
    f = Facts(now=ctx.now())
    f.kernel = (ctx.read("/proc/sys/kernel/osrelease") or os.uname().release).strip()
    f.gpus = gpu_mod.inventory(ctx)
    f.primary = gpu_mod.primary_compute(f.gpus)

    # ---- NVIDIA kernel side
    ver = ctx.read("/proc/driver/nvidia/version")
    f.nv_loaded = ctx.exists("/sys/module/nvidia") or ver is not None
    if ver:
        m = re.search(r"Kernel Module(?: for \S+)?\s+(\d+\.\d+(?:\.\d+)?)", ver)
        f.nv_version = m.group(1) if m else None
        f.nv_open = "Open Kernel Module" in ver
    if not f.nv_version:
        v = ctx.read("/sys/module/nvidia/version")
        f.nv_version = v.strip() if v else None
    t = ctx.read("/sys/module/nvidia/taint")
    f.nv_taint = t.strip() if t is not None else None
    f.nv_params = parse_nv_params(ctx.read("/proc/driver/nvidia/params") or "")
    f.nv_modeset = _yn(ctx.read("/sys/module/nvidia_drm/parameters/modeset"))
    f.nouveau_loaded = ctx.exists("/sys/module/nouveau")
    f.uvm_loaded = ctx.exists("/sys/module/nvidia_uvm")
    f.dev_uvm = ctx.exists("/dev/nvidia-uvm")

    # installed kernels and NVIDIA modules for each (prebuilt Canonical-signed vs DKMS)
    kernels = set()
    for p in glob.glob(str(ctx.sys("/boot")) + "/vmlinuz-*"):
        kernels.add(Path(p).name[len("vmlinuz-"):])
    moddir = ctx.sys("/lib/modules")
    if not kernels and moddir.is_dir():
        kernels = {d.name for d in moddir.iterdir() if d.is_dir()}
    kernels.add(f.kernel)
    f.kernels = sorted(kernels, key=version_key)
    for k in f.kernels:
        found = None
        base = moddir / k
        for pat in ("kernel/nvidia*/nvidia.ko*", "updates/dkms/nvidia.ko*", "kernel/drivers/video/nvidia*.ko*",
                    "updates/nvidia.ko*", "extra/nvidia.ko*"):
            hits = glob.glob(str(base / pat))
            if hits:
                found = hits[0]
                break
        f.nv_module_for[k] = found is not None
        if k == f.kernel and found:
            f.nv_module_kind = "dkms" if "/dkms/" in found else "prebuilt"

    texts = []
    for d in ("/etc/modprobe.d", "/usr/lib/modprobe.d", "/lib/modprobe.d"):
        for p in sorted(glob.glob(str(ctx.sys(d)) + "/*.conf")):
            try:
                texts.append(Path(p).read_text(errors="replace"))
            except OSError:
                pass
    f.modprobe = parse_modprobe(texts)

    if r.which("systemctl"):
        res = r.run(["systemctl", "is-enabled", *NV_SERVICES], timeout=10)
        states = [ln.strip() for ln in res.out.splitlines()]
        for unit, state in zip(NV_SERVICES, states):
            f.services[unit] = state
    f.sleep_hook = any(ctx.exists(f"{d}/{SLEEP_HOOK}") for d in
                       ("/usr/lib/systemd/system-sleep", "/etc/systemd/system-sleep", "/lib/systemd/system-sleep"))

    sb = None
    try:
        raw = ctx.sys(SECUREBOOT_VAR).read_bytes()
        if len(raw) >= 5:
            sb = raw[4] == 1
    except OSError:
        pass
    if sb is None and r.which("mokutil"):
        res = r.run(["mokutil", "--sb-state"], timeout=10)
        txt = (res.out + res.err).lower()
        if "enabled" in txt:
            sb = True
        elif "disabled" in txt or "not supported" in txt:
            sb = False
    f.secure_boot = sb

    # ---- containers
    if r.which("nvidia-ctk"):
        res = r.run(["nvidia-ctk", "--version"], timeout=10)
        m = re.search(r"version\s+(\d+\.\d+\.\d+)", res.out + res.err)
        f.ctk_version = m.group(1) if m else None
        res = r.run(["nvidia-ctk", "cdi", "list"], timeout=15)
        f.cdi_devices = [ln.strip() for ln in res.out.splitlines() if "=" in ln and "/" in ln]
    for d in ("/etc/cdi", "/var/run/cdi", "/run/cdi"):
        f.cdi_specs += sorted(glob.glob(str(ctx.sys(d)) + "/*.yaml") + glob.glob(str(ctx.sys(d)) + "/*.json"))
    f.podman, f.docker = bool(r.which("podman")), bool(r.which("docker"))

    # ---- graphics
    for d in ("/usr/share/vulkan/icd.d", "/etc/vulkan/icd.d"):
        f.vulkan_icds += sorted(Path(p).name for p in glob.glob(str(ctx.sys(d)) + "/*.json"))
    f.boot_vga = next((g.pci.slot for g in f.gpus if g.pci.boot_vga), None)
    f.aq_drm_devices = ctx.env.get("AQ_DRM_DEVICES")
    if f.aq_drm_devices is None:
        for p in [ctx.paths.config_home / "hypr" / "user.conf", ctx.paths.config_home / "hypr" / "hyprland.conf",
                  ctx.sys("/usr/share/svoya/hypr/hyprland.conf")]:
            try:
                m = re.search(r"^\s*env\s*=\s*AQ_DRM_DEVICES\s*,\s*(\S+)", p.read_text(), re.M)
            except OSError:
                continue
            if m:
                f.aq_drm_devices = m.group(1)
                break

    # ---- compute
    f.uv_backend_env = ctx.env.get("UV_TORCH_BACKEND")
    if f.uv_backend_env is None:
        for p in sorted(glob.glob(str(ctx.paths.config_home / "environment.d") + "/*.conf")):
            try:
                m = re.search(r"^\s*UV_TORCH_BACKEND\s*=\s*(\S+)", Path(p).read_text(), re.M)
            except OSError:
                continue
            if m:
                f.uv_backend_env = m.group(1).strip('"')
    f.uv_present = bool(r.which("uv"))
    f.kfd = ctx.exists("/dev/kfd")
    f.kfd_targets = amd_db.kfd_targets(ctx.sys("/sys/class/kfd/kfd/topology/nodes"))
    pl = ctx.read("/sys/module/ttm/parameters/pages_limit")
    f.ttm_pages_limit = int(pl.strip()) if pl and pl.strip().isdigit() else None
    f.cmdline = (ctx.read("/proc/cmdline") or "").strip()
    mem = ctx.read("/proc/meminfo") or ""
    m = re.search(r"^MemTotal:\s+(\d+)\s+kB", mem, re.M)
    f.mem_total = int(m.group(1)) * 1024 if m else None

    # ---- user
    uid, name, _home = ctx.target_user()
    f.user = name
    res = r.run(["id", "-Gn", name], timeout=5)
    f.user_groups = res.out.split() if res.ok else []
    if gpu_only:
        return f

    # ---- storage & snapshots
    mounts = ctx.read("/proc/mounts") or ""
    ai = ctx.paths.ai_root
    info: dict = {"path": str(ai), "exists": ai.exists()}
    if ai.exists():
        try:
            du = shutil.disk_usage(ai)
            info.update(free=du.free, total=du.total)
            st = ai.stat()
            info.update(mode=st.st_mode & 0o7777, gid=st.st_gid, ino=st.st_ino)
        except OSError:
            pass
        mp, fstype = mount_for("/srv/ai", mounts)
        info.update(mount=mp, fstype=fstype, subvolume=(fstype == "btrfs" and info.get("ino") == 256))
        try:
            import grp
            info["group"] = grp.getgrgid(info["gid"]).gr_name if "gid" in info else None
        except (KeyError, ImportError):
            info["group"] = None
    f.srv_ai = info
    f.swaps = parse_swaps(ctx.read("/proc/swaps") or "")
    _mp, f.root_fs = mount_for("/", mounts)
    f.snapper = bool(r.which("snapper"))
    f.snapper_root = ctx.exists("/etc/snapper/configs/root")
    if f.snapper and f.snapper_root:
        from ..snapshots import Snapper
        f.last_snapshot = Snapper(ctx).last_date()
    return f
