# SPDX-License-Identifier: Apache-2.0
"""Deterministic OS controls used by the fast path and system tools.

Every setter is paired with a getter so callers can verify the effect before claiming success.
Backends: PipeWire (`wpctl`, fallback `pactl`), `brightnessctl`, NetworkManager (`nmcli`),
`bluetoothctl`, logind (`loginctl`), `grim`, `systemd-run --user`, `notify-send`,
`gtk-launch`/`gio launch`, `sos status --json` / `nvidia-smi` / sysfs / procfs.
"""

from __future__ import annotations

import configparser
import datetime as dt
import json
import os
import re
import secrets
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .paths import Paths
from .runner import Runner
from .svoya import SvoyaCli

SINK_WP = "@DEFAULT_AUDIO_SINK@"
SINK_PA = "@DEFAULT_SINK@"

APP_ALIASES: dict[str, list[str]] = {
    "браузер": ["firefox", "org.mozilla.firefox", "chromium", "google-chrome", "brave-browser", "librewolf"],
    "browser": ["firefox", "org.mozilla.firefox", "chromium", "google-chrome", "brave-browser", "librewolf"],
    "терминал": ["kitty", "foot", "alacritty", "org.gnome.Console", "org.gnome.Terminal", "konsole"],
    "консоль": ["kitty", "foot", "alacritty", "org.gnome.Console", "org.gnome.Terminal", "konsole"],
    "terminal": ["kitty", "foot", "alacritty", "org.gnome.Console", "org.gnome.Terminal", "konsole"],
    "файлы": ["org.gnome.Nautilus", "thunar", "nemo", "org.kde.dolphin", "pcmanfm"],
    "проводник": ["org.gnome.Nautilus", "thunar", "nemo", "org.kde.dolphin", "pcmanfm"],
    "файловый менеджер": ["org.gnome.Nautilus", "thunar", "nemo", "org.kde.dolphin", "pcmanfm"],
    "files": ["org.gnome.Nautilus", "thunar", "nemo", "org.kde.dolphin", "pcmanfm"],
    "file manager": ["org.gnome.Nautilus", "thunar", "nemo", "org.kde.dolphin", "pcmanfm"],
    "редактор": ["org.gnome.TextEditor", "code", "codium", "org.kde.kate", "gedit"],
    "editor": ["org.gnome.TextEditor", "code", "codium", "org.kde.kate", "gedit"],
    "телеграм": ["org.telegram.desktop", "telegram-desktop", "telegram"],
    "калькулятор": ["org.gnome.Calculator", "gnome-calculator", "qalculate-gtk", "kcalc"],
    "calculator": ["org.gnome.Calculator", "gnome-calculator", "qalculate-gtk", "kcalc"],
}


@dataclass
class Volume:
    level: float           # 0.0 … 1.5 (1.0 = 100 %)
    muted: bool
    backend: str

    @property
    def percent(self) -> int:
        return int(round(self.level * 100))


@dataclass
class DesktopEntry:
    id: str
    path: Path
    name: str
    names: list[str] = field(default_factory=list)   # all localized names, generic names, keywords
    exec: str = ""

    @property
    def binary(self) -> str:
        parts = [p for p in self.exec.split() if not p.startswith("%") and "=" not in p.split("/")[-1]]
        if not parts:
            return ""
        if Path(parts[0]).name == "flatpak" and "run" in parts:
            rest = [p for p in parts[parts.index("run") + 1:] if not p.startswith("-")]
            return rest[0] if rest else ""
        if Path(parts[0]).name == "env" and len(parts) > 1:
            return Path(parts[-1]).name
        return Path(parts[0]).name


class OsControl:
    def __init__(self, runner: Runner, paths: Paths, svoya: SvoyaCli | None = None,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.runner = runner
        self.paths = paths
        self.svoya = svoya or SvoyaCli(runner, paths)
        self.sleep = sleep

    def has(self, binary: str) -> bool:
        return self.runner.which(binary) is not None

    # ------------------------------------------------------------------ audio
    def volume_get(self) -> Volume | None:
        if self.has("wpctl"):
            res = self.runner.run(["wpctl", "get-volume", SINK_WP], timeout=2.0)
            m = re.search(r"Volume:\s*([\d.]+)", res.out) if res.ok else None
            if m:
                return Volume(float(m.group(1)), "[MUTED]" in res.out, "wpctl")
        if self.has("pactl"):
            res = self.runner.run(["pactl", "get-sink-volume", SINK_PA], timeout=2.0)
            m = re.search(r"(\d+)%", res.out) if res.ok else None
            if m:
                mute = self.runner.run(["pactl", "get-sink-mute", SINK_PA], timeout=2.0)
                return Volume(int(m.group(1)) / 100, "yes" in mute.out.lower(), "pactl")
        return None

    def volume_set(self, level: float | None = None, delta: float | None = None) -> bool:
        if self.has("wpctl"):
            if delta is not None:
                arg = f"{abs(round(delta * 100))}%{'+' if delta > 0 else '-'}"
            else:
                arg = f"{max(0.0, min(1.5, level or 0.0)):.2f}"
            return self.runner.run(["wpctl", "set-volume", "-l", "1.0", SINK_WP, arg], timeout=2.0).ok
        if self.has("pactl"):
            if delta is not None:
                arg = f"{'+' if delta > 0 else '-'}{abs(round(delta * 100))}%"
            else:
                arg = f"{round(max(0.0, min(1.5, level or 0.0)) * 100)}%"
            return self.runner.run(["pactl", "set-sink-volume", SINK_PA, arg], timeout=2.0).ok
        return False

    def mute_set(self, muted: bool | None) -> bool:
        value = "toggle" if muted is None else ("1" if muted else "0")
        if self.has("wpctl"):
            return self.runner.run(["wpctl", "set-mute", SINK_WP, value], timeout=2.0).ok
        if self.has("pactl"):
            return self.runner.run(["pactl", "set-sink-mute", SINK_PA, value], timeout=2.0).ok
        return False

    # ------------------------------------------------------------------ brightness
    def brightness_get(self) -> float | None:
        if not self.has("brightnessctl"):
            return None
        res = self.runner.run(["brightnessctl", "-m"], timeout=2.0)
        if not res.ok:
            return None
        for line in res.out.splitlines():
            parts = line.split(",")
            if len(parts) >= 5 and parts[1] == "backlight":
                try:
                    return int(parts[2]) / max(1, int(parts[4]))
                except ValueError:
                    continue
        parts = res.out.strip().split(",")
        if len(parts) >= 4 and parts[3].endswith("%"):
            return int(parts[3].rstrip("%")) / 100
        return None

    def brightness_set(self, level: float | None = None, delta: float | None = None) -> bool:
        if not self.has("brightnessctl"):
            return False
        if delta is not None:
            arg = f"{abs(round(delta * 100))}%{'+' if delta > 0 else '-'}"
        else:
            arg = f"{max(1, min(100, round((level or 0) * 100)))}%"
        return self.runner.run(["brightnessctl", "-q", "set", arg], timeout=2.0).ok

    # ------------------------------------------------------------------ radios
    def wifi_get(self) -> bool | None:
        if not self.has("nmcli"):
            return None
        res = self.runner.run(["nmcli", "radio", "wifi"], timeout=3.0)
        if not res.ok:
            return None
        out = res.out.strip().lower()
        return True if out.startswith("enabled") else False if out.startswith("disabled") else None

    def wifi_set(self, on: bool) -> bool:
        return self.has("nmcli") and self.runner.run(["nmcli", "radio", "wifi", "on" if on else "off"],
                                                      timeout=5.0).ok

    def bluetooth_get(self) -> bool | None:
        if not self.has("bluetoothctl"):
            return None
        res = self.runner.run(["bluetoothctl", "show"], timeout=3.0)
        m = re.search(r"Powered:\s*(yes|no)", res.out) if res.ok else None
        return None if not m else m.group(1) == "yes"

    def bluetooth_set(self, on: bool) -> bool:
        return self.has("bluetoothctl") and self.runner.run(["bluetoothctl", "power", "on" if on else "off"],
                                                             timeout=5.0).ok

    # ------------------------------------------------------------------ session
    def _session_id(self) -> str | None:
        sid = os.environ.get("XDG_SESSION_ID")
        if sid:
            return sid
        res = self.runner.run(["loginctl", "show-user", str(os.getuid()), "-p", "Display", "--value"], timeout=2.0)
        return res.out.strip() or None if res.ok else None

    def lock(self) -> tuple[bool, bool]:
        """Lock the session; returns (command_ok, verified_locked)."""
        if not self.has("loginctl"):
            return False, False
        sid = self._session_id()
        argv = ["loginctl", "lock-session"] + ([sid] if sid else [])
        if not self.runner.run(argv, timeout=3.0).ok:
            return False, False
        if not sid:
            return True, False
        for _ in range(5):
            res = self.runner.run(["loginctl", "show-session", sid, "-p", "LockedHint", "--value"], timeout=2.0)
            if res.ok and res.out.strip() == "yes":
                return True, True
            self.sleep(0.1)
        return True, False

    def screenshots_dir(self) -> Path:
        pictures = self.paths.home / "Pictures"
        try:
            text = (self.paths.config_home / "user-dirs.dirs").read_text(encoding="utf-8")
            m = re.search(r'^XDG_PICTURES_DIR="([^"]+)"', text, re.MULTILINE)
            if m:
                pictures = Path(m.group(1).replace("$HOME", str(self.paths.home)))
        except OSError:
            pass
        return pictures / "Screenshots"

    def screenshot(self) -> Path | None:
        if not self.has("grim"):
            return None
        d = self.screenshots_dir()
        d.mkdir(parents=True, exist_ok=True)
        path = d / dt.datetime.now().strftime("screenshot-%Y-%m-%d-%H%M%S.png")
        if not self.runner.run(["grim", str(path)], timeout=5.0).ok:
            return None
        try:
            with open(path, "rb") as fh:
                return path if fh.read(8) == b"\x89PNG\r\n\x1a\n" else None
        except OSError:
            return None

    # ------------------------------------------------------------------ timers / notifications
    def timer_start(self, seconds: int, label: str) -> str | None:
        if not self.has("systemd-run"):
            return None
        unit = f"jackson-timer-{secrets.token_hex(3)}"
        res = self.runner.run(["systemd-run", "--user", f"--on-active={seconds}s", f"--unit={unit}",
                               "--timer-property=AccuracySec=1s", "--collect",
                               "notify-send", "-a", "Джексон", "-u", "critical", label, "⏰"], timeout=5.0)
        if not res.ok:
            return None
        check = self.runner.run(["systemctl", "--user", "is-active", f"{unit}.timer"], timeout=3.0)
        return unit if check.out.strip() == "active" else None

    def timer_stop(self, unit: str) -> bool:
        return self.runner.run(["systemctl", "--user", "stop", f"{unit}.timer"], timeout=5.0).ok

    def notify(self, title: str, body: str = "", urgency: str = "normal") -> bool:
        if not self.has("notify-send"):
            return False
        return self.runner.run(["notify-send", "-a", "Джексон", "-u", urgency, title, body], timeout=3.0).ok

    # ------------------------------------------------------------------ applications
    def desktop_dirs(self) -> list[Path]:
        data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
        dirs = [self.paths.data_home / "applications",
                self.paths.data_home / "flatpak" / "exports" / "share" / "applications",
                Path("/var/lib/flatpak/exports/share/applications")]
        dirs += [Path(d) / "applications" for d in data_dirs if d]
        seen, out = set(), []
        for d in dirs:
            if str(d) not in seen:
                seen.add(str(d))
                out.append(d)
        return out

    def desktop_entries(self) -> list[DesktopEntry]:
        entries: dict[str, DesktopEntry] = {}
        for d in self.desktop_dirs():
            if not d.is_dir():
                continue
            for path in sorted(d.rglob("*.desktop")):
                app_id = str(path.relative_to(d)).replace("/", "-")[: -len(".desktop")]
                if app_id in entries:
                    continue  # earlier dirs take precedence (user overrides)
                entry = self._parse_desktop(path, app_id)
                if entry is not None:
                    entries[app_id] = entry
        return list(entries.values())

    @staticmethod
    def _parse_desktop(path: Path, app_id: str) -> DesktopEntry | None:
        cp = configparser.RawConfigParser(interpolation=None, strict=False)
        cp.optionxform = str  # type: ignore[assignment]
        try:
            cp.read(path, encoding="utf-8")
        except (configparser.Error, UnicodeDecodeError, OSError):
            return None
        if not cp.has_section("Desktop Entry"):
            return None
        sec = cp["Desktop Entry"]
        if sec.get("Type", "Application") != "Application" or sec.get("NoDisplay") == "true" \
                or sec.get("Hidden") == "true":
            return None
        names = []
        for key, value in sec.items():
            base = key.split("[")[0]
            if base in ("Name", "GenericName"):
                names.append(value)
            elif base == "Keywords":
                names += [k for k in value.split(";") if k]
        return DesktopEntry(app_id, path, sec.get("Name", app_id), names, sec.get("Exec", ""))

    def find_app(self, query: str) -> DesktopEntry | None:
        q = query.lower().replace("ё", "е").strip()
        if not q:
            return None
        entries = self.desktop_entries()
        by_id = {e.id.lower(): e for e in entries}
        for alias in APP_ALIASES.get(q, []):
            if alias.lower() in by_id:
                return by_id[alias.lower()]
        best: tuple[int, DesktopEntry] | None = None
        for e in entries:
            names = [n.lower().replace("ё", "е") for n in [e.name, *e.names]]
            score = 0
            if q == e.id.lower() or q == e.binary.lower() or q in names:
                score = 100
            elif any(n.startswith(q) for n in names) or e.id.lower().endswith("." + q):
                score = 60
            elif len(q) >= 4 and any(q in n for n in names):
                score = 30
            if score and (best is None or score > best[0]):
                best = (score, e)
        return best[1] if best else None

    def launch(self, entry: DesktopEntry) -> tuple[bool, bool]:
        """Launch an application; returns (started, verified_process_seen)."""
        before = self._pids(entry.binary)
        started = False
        if self.has("gtk-launch"):
            started = self.runner.run(["gtk-launch", entry.id], timeout=5.0).ok
        if not started and self.has("gio"):
            started = self.runner.run(["gio", "launch", str(entry.path)], timeout=5.0).ok
        if not started and entry.exec:
            argv = [p for p in entry.exec.split() if not p.startswith("%")]
            started = self.runner.spawn(argv) is not None
        if not started:
            return False, False
        if not entry.binary:
            return True, False
        for _ in range(6):
            if self._pids(entry.binary) - before or (before and self._pids(entry.binary)):
                return True, True
            self.sleep(0.1)
        return True, False

    def _pids(self, binary: str) -> set[str]:
        if not binary or not self.has("pgrep"):
            return set()
        res = self.runner.run(["pgrep", "-u", str(os.getuid()), "-f", binary], timeout=2.0)
        return set(res.out.split()) if res.ok else set()

    def xdg_open(self, target: str) -> bool:
        return self.has("xdg-open") and self.runner.spawn(["xdg-open", target]) is not None

    TERMINALS = ("kitty", "foot", "alacritty", "ghostty", "ptyxis", "gnome-terminal", "konsole", "x-terminal-emulator")

    def open_terminal(self, argv: list[str], hold: bool = True) -> bool:
        """Run *argv* in a visible terminal (installs ask for confirmation and passwords there); with
        *hold* the window waits for Enter afterwards, so the result can be read."""
        cmd = ["sh", "-c", '"$@"; printf "\\n"; read -r _', "sh", *argv] if hold else list(argv)
        if self.has("xdg-terminal-exec"):
            return self.runner.spawn(["xdg-terminal-exec", *cmd]) is not None
        for term in self.TERMINALS:
            if self.has(term):
                flag = "--" if term in ("gnome-terminal", "ptyxis") else "-e"
                return self.runner.spawn([term, flag, *cmd]) is not None
        return False

    # ------------------------------------------------------------------ information
    def gpus(self) -> list[dict[str, Any]]:
        status = self.svoya.status()
        if status and isinstance(status.get("gpu"), list) and status["gpu"]:
            return [g for g in status["gpu"] if isinstance(g, dict)]
        if self.has("nvidia-smi"):
            res = self.runner.run(["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total,temperature.gpu,"
                                   "utilization.gpu,driver_version", "--format=csv,noheader,nounits"], timeout=5.0)
            gpus = []
            for line in res.out.splitlines() if res.ok else []:
                f = [x.strip() for x in line.split(",")]
                if len(f) >= 7:
                    gpus.append({"index": _int(f[0]), "vendor": "nvidia", "name": f[1],
                                 "vramUsedMiB": _int(f[2]), "vramTotalMiB": _int(f[3]), "tempC": _int(f[4]),
                                 "util": _int(f[5]), "driver": f[6]})
            if gpus:
                return gpus
        return self._sysfs_gpus()

    def _sysfs_gpus(self) -> list[dict[str, Any]]:
        gpus = []
        for card in sorted(Path("/sys/class/drm").glob("card[0-9]")):
            dev = card / "device"
            try:
                vendor = (dev / "vendor").read_text().strip()
            except OSError:
                continue
            total = _read_int(dev / "mem_info_vram_total")
            used = _read_int(dev / "mem_info_vram_used")
            name = {"0x1002": "AMD GPU", "0x10de": "NVIDIA GPU", "0x8086": "Intel GPU"}.get(vendor, "GPU")
            g: dict[str, Any] = {"index": len(gpus), "vendor": name.split()[0].lower(), "name": name}
            if total:
                g["vramTotalMiB"] = total // (1024 * 1024)
            if used is not None:
                g["vramUsedMiB"] = used // (1024 * 1024)
            gpus.append(g)
        return gpus

    def disks(self) -> list[dict[str, Any]]:
        out, seen = [], set()
        for label, p in (("/", Path("/")), ("~", self.paths.home), ("/srv/ai", Path("/srv/ai"))):
            try:
                dev = os.stat(p).st_dev
                if dev in seen:
                    continue
                seen.add(dev)
                u = shutil.disk_usage(p)
            except OSError:
                continue
            out.append({"mount": label, "total": u.total, "used": u.used, "free": u.free})
        return out

    def battery(self) -> dict[str, Any] | None:
        for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
            cap = _read_int(bat / "capacity")
            if cap is None:
                continue
            try:
                status = (bat / "status").read_text().strip()
            except OSError:
                status = "Unknown"
            return {"percent": cap, "status": status}
        return None

    def meminfo(self) -> dict[str, int]:
        info: dict[str, int] = {}
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                key, _, rest = line.partition(":")
                num = rest.strip().split()
                if num and num[0].isdigit():
                    info[key] = int(num[0]) * 1024
        except OSError:
            pass
        return info

    def uptime(self) -> float | None:
        try:
            return float(Path("/proc/uptime").read_text().split()[0])
        except (OSError, ValueError, IndexError):
            return None

    def cpu(self) -> dict[str, Any]:
        model, cores = "", os.cpu_count() or 0
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    model = line.split(":", 1)[1].strip()
                    break
        except OSError:
            pass
        load = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
        return {"model": model, "cores": cores, "load1": round(load[0], 2)}

    def local_ips(self) -> list[str]:
        if self.has("ip"):
            res = self.runner.run(["ip", "-j", "addr", "show", "scope", "global"], timeout=2.0)
            try:
                data = json.loads(res.out) if res.ok else []
            except ValueError:
                data = []
            ips = []
            for iface in data:
                for a in iface.get("addr_info", []):
                    if a.get("local") and a.get("family") in ("inet", "inet6"):
                        ips.append(f"{a['local']} ({iface.get('ifname', '?')})")
            return ips
        return []


def _int(value: str) -> int | None:
    try:
        return int(float(value))
    except ValueError:
        return None


def _read_int(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None
