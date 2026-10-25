"""``sos doctor --hardware`` (``sos hardware``, ``sos железо``): is this computer ready for daily work?

Read from sysfs and procfs, no root needed: the model and its firmware (UEFI or BIOS, Secure Boot),
the processor and memory, graphics and the driver in use, the screens, Wi-Fi and Ethernet (driver,
radio switches), Bluetooth, sound cards, the battery's health, the sleep states, touchpad, touch
screen and camera, the disks; from the kernel log the firmware files it could not load and its
last errors. Problems come first, each with what to do. ``--save`` writes the same report to a
file to send (``~/sos-hardware-report.txt``). It never contains serial numbers or MAC addresses.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from .. import ui
from ..context import Ctx
from ..i18n import count, smart, tr
from ..util import iso
from .facts import SECUREBOOT_VAR

VENDOR_NAMES = {0x10DE: "NVIDIA", 0x1002: "AMD", 0x8086: "Intel", 0x14E4: "Broadcom", 0x168C: "Qualcomm Atheros",
                0x17CB: "Qualcomm", 0x10EC: "Realtek", 0x14C3: "MediaTek", 0x1969: "Qualcomm Atheros"}
DMI = ("sys_vendor", "product_name", "product_version", "board_vendor", "board_name", "bios_version", "bios_date")
FIRMWARE_FAIL = (re.compile(r"Direct firmware load for (\S+) failed"),
                 re.compile(r"firmware: failed to load (\S+)"),
                 re.compile(r"failed to load firmware (\S+)", re.I))
SKIP_DISKS = ("loop", "ram", "zram", "sr", "fd", "dm-", "md", "nbd")


def _text(ctx: Ctx, path: str | Path) -> str | None:
    v = ctx.read(str(path))
    return v.strip() if v is not None else None


def _int(ctx: Ctx, path: str | Path) -> int | None:
    v = _text(ctx, path)
    try:
        return int(v, 0) if v is not None else None
    except ValueError:
        return None


def _children(ctx: Ctx, path: str) -> list[Path]:
    try:
        return sorted(ctx.sys(path).iterdir())
    except OSError:
        return []


def _driver(dev: Path) -> str | None:
    link = dev / "driver"
    try:
        return link.resolve().name if link.exists() else None
    except OSError:
        return None


def _rel(ctx: Ctx, p: Path) -> str:
    """A path in the fake root back to the system path (for ctx.read)."""
    root = str(ctx.sys("/"))
    s = str(p)
    return "/" + s[len(root):].lstrip("/") if s.startswith(root) else s


# ---- gathering ------------------------------------------------------------------------------------
def computer(ctx: Ctx) -> dict:
    dmi = {k: _text(ctx, f"/sys/class/dmi/id/{k}") for k in DMI}
    sb = None
    try:
        raw = ctx.sys(SECUREBOOT_VAR).read_bytes()
        if len(raw) >= 5:
            sb = raw[4] == 1
    except OSError:
        pass
    return {"vendor": dmi["sys_vendor"], "product": dmi["product_name"], "version": dmi["product_version"],
            "board": " ".join(x for x in (dmi["board_vendor"], dmi["board_name"]) if x) or None,
            "bios": " ".join(x for x in (dmi["bios_version"], dmi["bios_date"]) if x) or None,
            "firmware": "uefi" if ctx.exists("/sys/firmware/efi") else "bios", "secureBoot": sb,
            "kernel": _text(ctx, "/proc/sys/kernel/osrelease") or os.uname().release}


def processor(ctx: Ctx) -> dict:
    info = ctx.read("/proc/cpuinfo") or ""
    m = re.search(r"^model name\s*:\s*(.+)$", info, re.M)
    threads = len(re.findall(r"^processor\s*:", info, re.M))
    mem = re.search(r"^MemTotal:\s*(\d+)\s*kB", ctx.read("/proc/meminfo") or "", re.M)
    return {"model": m.group(1).strip() if m else None, "threads": threads or None,
            "memoryGiB": round(int(mem.group(1)) / 1048576, 1) if mem else None}


def pci_devices(ctx: Ctx, classes: tuple[int, ...]) -> list[dict]:
    """PCI devices whose class (upper byte) is one of `classes`: id, kind, driver in use."""
    out = []
    for d in _children(ctx, "/sys/bus/pci/devices"):
        cls = _int(ctx, _rel(ctx, d / "class"))
        if cls is None or (cls >> 16) not in classes:
            continue
        vid, did = _int(ctx, _rel(ctx, d / "vendor")), _int(ctx, _rel(ctx, d / "device"))
        if vid is None or did is None:
            continue
        out.append({"slot": d.name, "class": f"{cls >> 8:04x}", "id": f"{vid:04x}:{did:04x}",
                    "vendor": VENDOR_NAMES.get(vid, f"{vid:04x}"), "driver": _driver(d)})
    return out


def screens(ctx: Ctx) -> list[str]:
    out = []
    for c in _children(ctx, "/sys/class/drm"):
        if "-" in c.name and _text(ctx, _rel(ctx, c / "status")) == "connected":
            out.append(c.name.split("-", 1)[1])
    return out


def network(ctx: Ctx) -> list[dict]:
    out = []
    for n in _children(ctx, "/sys/class/net"):
        if not (n / "device").exists():          # lo, bridges, tunnels, containers
            continue
        wifi = (n / "wireless").exists() or (n / "phy80211").exists()
        out.append({"name": n.name, "kind": "wifi" if wifi else "ethernet", "driver": _driver(n / "device"),
                    "state": _text(ctx, _rel(ctx, n / "operstate"))})
    return out


def radios(ctx: Ctx) -> list[dict]:
    out = []
    for r in _children(ctx, "/sys/class/rfkill"):
        t = _text(ctx, _rel(ctx, r / "type"))
        if not t:
            continue
        out.append({"type": t, "name": _text(ctx, _rel(ctx, r / "name")),
                    "soft": _text(ctx, _rel(ctx, r / "soft")) == "1", "hard": _text(ctx, _rel(ctx, r / "hard")) == "1"})
    return out


def sound(ctx: Ctx) -> list[dict]:
    out = []
    for line in (ctx.read("/proc/asound/cards") or "").splitlines():
        m = re.match(r"^\s*(\d+) \[(\S+)\s*\]: (.+?) - (.+)$", line)
        if m:
            out.append({"index": int(m.group(1)), "id": m.group(2), "driver": m.group(3).strip(),
                        "name": m.group(4).strip()})
    return out


def power(ctx: Ctx) -> dict:
    bats, ac = [], None
    for p in _children(ctx, "/sys/class/power_supply"):
        kind = _text(ctx, _rel(ctx, p / "type"))
        if kind == "Mains":
            on = _text(ctx, _rel(ctx, p / "online"))
            ac = (on == "1") if on is not None else ac
        elif kind == "Battery" and _text(ctx, _rel(ctx, p / "scope")) != "Device":    # not a mouse's
            full = _int(ctx, _rel(ctx, p / "energy_full")) or _int(ctx, _rel(ctx, p / "charge_full"))
            design = _int(ctx, _rel(ctx, p / "energy_full_design")) or _int(ctx, _rel(ctx, p / "charge_full_design"))
            bats.append({"name": p.name, "capacity": _int(ctx, _rel(ctx, p / "capacity")),
                         "status": _text(ctx, _rel(ctx, p / "status")),
                         "healthPct": round(100 * full / design) if full and design else None})
    return {"batteries": bats, "ac": ac, "sleep": _text(ctx, "/sys/power/mem_sleep")}


def inputs(ctx: Ctx) -> dict:
    pads, touch = [], []
    for block in (ctx.read("/proc/bus/input/devices") or "").split("\n\n"):
        m = re.search(r'^N: Name="(.+)"$', block, re.M)
        if not m:
            continue
        name = m.group(1)
        low = name.lower()
        if any(w in low for w in ("touchpad", "trackpad", "glidepoint")):
            pads.append(name)
        elif "touchscreen" in low or "wacom" in low:
            touch.append(name)
    cams = []
    for v in _children(ctx, "/sys/class/video4linux"):
        name = _text(ctx, _rel(ctx, v / "name"))
        if name and name not in cams:
            cams.append(name)
    return {"touchpad": sorted(set(pads)), "touchscreen": sorted(set(touch)), "camera": cams}


def disks(ctx: Ctx) -> list[dict]:
    out = []
    for b in _children(ctx, "/sys/block"):
        if b.name.startswith(SKIP_DISKS):
            continue
        sectors = _int(ctx, _rel(ctx, b / "size")) or 0
        if not sectors:
            continue
        out.append({"name": b.name, "model": _text(ctx, _rel(ctx, b / "device" / "model")),
                    "sizeGB": round(sectors * 512 / 1e9), "ssd": _text(ctx, _rel(ctx, b / "queue" / "rotational")) == "0",
                    "removable": _text(ctx, _rel(ctx, b / "removable")) == "1"})
    return out


def kernel_log(ctx: Ctx) -> tuple[list[str], list[str]]:
    """Firmware files the kernel could not load, and its last distinct errors (this boot)."""
    r = ctx.runner
    warn = err = ""
    if r.which("journalctl"):
        warn = r.run(["journalctl", "-k", "-b", "-p", "warning", "-o", "cat", "--no-pager"], timeout=15).out
        err = r.run(["journalctl", "-k", "-b", "-p", "err", "-o", "cat", "--no-pager"], timeout=15).out
    missing: list[str] = []
    for line in warn.splitlines():
        for rx in FIRMWARE_FAIL:
            m = rx.search(line)
            if m and m.group(1) not in missing:
                missing.append(m.group(1))
    errors: list[str] = []
    for line in err.splitlines():
        line = line.strip()[:160]
        if line and line not in errors:
            errors.append(line)
    return missing, errors[-12:]


def gather(ctx: Ctx) -> dict:
    missing, errors = kernel_log(ctx)
    rep = {"computer": computer(ctx), "processor": processor(ctx),
           "graphics": pci_devices(ctx, (0x03,)), "screens": screens(ctx),
           "networkControllers": pci_devices(ctx, (0x02,)), "network": network(ctx), "radios": radios(ctx),
           "bluetooth": any(p.name.startswith("hci") for p in _children(ctx, "/sys/class/bluetooth")),
           "sound": sound(ctx), "power": power(ctx), "input": inputs(ctx), "disks": disks(ctx),
           "firmwareMissing": missing, "kernelErrors": errors, "at": iso(ctx.now())}
    rep["problems"] = problems(rep)
    return rep


# ---- judging --------------------------------------------------------------------------------------
def _p(level: str, en: str, ru: str, fix_en: str = "", fix_ru: str = "") -> dict:
    return {"level": level, "en": en, "ru": ru, "fixEn": fix_en, "fixRu": fix_ru}


def problems(rep: dict) -> list[dict]:
    out = []
    for g in rep["graphics"]:
        if not g["driver"]:
            out.append(_p("fail", f"Graphics {g['vendor']} {g['id']} has no driver: the screen runs in a basic mode",
                          f"Видеокарта {g['vendor']} {g['id']} без драйвера: экран работает в упрощённом режиме",
                          "sos gpu", "sos видеокарта"))
        elif g["vendor"] == "NVIDIA" and g["driver"] == "nouveau":
            out.append(_p("warn", "NVIDIA runs on nouveau: for AI and games install NVIDIA's driver",
                          "NVIDIA работает на nouveau: для ИИ и игр поставьте драйвер NVIDIA",
                          "sos gpu (or the NVIDIA ISO)", "sos видеокарта (или образ с NVIDIA)"))
    for n in rep["networkControllers"]:
        if n["class"] == "0280" and not n["driver"]:
            out.append(_p("fail", f"Wi-Fi adapter {n['vendor']} {n['id']} has no driver",
                          f"Wi‑Fi адаптер {n['vendor']} {n['id']} без драйвера",
                          "send this report: the driver can be found", "пришлите этот отчёт: драйвер подберём"))
    if not any(x["kind"] == "wifi" for x in rep["network"]) and not any(
            n["class"] == "0280" for n in rep["networkControllers"]):
        out.append(_p("info", "No Wi-Fi adapter found (a USB one shows up once its driver is loaded)",
                      "Wi‑Fi адаптер не найден (USB-адаптер виден, когда загружен его драйвер)"))
    for r in rep["radios"]:
        kind = {"wlan": "Wi-Fi", "bluetooth": "Bluetooth"}.get(r["type"], r["type"])
        if r["hard"]:
            out.append(_p("warn", f"{kind} is switched off by a switch or in the firmware settings",
                          f"{kind} выключен переключателем или в настройках BIOS/UEFI",
                          "the radio key (Fn) or BIOS", "клавиша радио (Fn) или BIOS"))
        elif r["soft"]:
            out.append(_p("warn", f"{kind} is switched off in software", f"{kind} выключен программно",
                          f"rfkill unblock {r['type']}", f"rfkill unblock {r['type']}"))
    if rep["firmwareMissing"]:
        files = ", ".join(rep["firmwareMissing"][:6])
        out.append(_p("warn", f"The kernel could not load firmware: {files}",
                      f"Ядро не нашло прошивку: {files}",
                      "send this report: the package can be found", "пришлите этот отчёт: пакет подберём"))
    if not rep["sound"]:
        out.append(_p("fail", "No sound card: many laptops need the SOF firmware",
                      "Звуковых карт нет: многим ноутбукам нужна прошивка SOF",
                      "send this report", "пришлите этот отчёт"))
    for b in rep["power"]["batteries"]:
        if b["healthPct"] is not None and b["healthPct"] < 70:
            out.append(_p("warn", f"Battery {b['name']} holds {b['healthPct']}% of its new capacity",
                          f"Батарея {b['name']} держит {b['healthPct']}% от новой ёмкости"))
    mem = rep["processor"]["memoryGiB"]
    if mem is not None and mem < 7.5:
        out.append(_p("warn", f"{mem:g} GB of memory: local models will be slow or will not fit",
                      f"Памяти {str(mem).replace('.', ',').removesuffix(',0')} ГБ: локальные модели будут медленными или не поместятся"))
    if rep["disks"] and not any(not d["removable"] for d in rep["disks"]):
        out.append(_p("warn", "No internal disk: nowhere to install SOS", "Нет внутреннего диска: SOS некуда установить"))
    if rep["computer"]["firmware"] == "bios":
        out.append(_p("info", "Started in BIOS (legacy) mode: SOS installs, but UEFI is better",
                      "Компьютер загрузился в режиме BIOS: SOS установится, но лучше UEFI",
                      "switch to UEFI in the firmware settings", "включите UEFI в настройках прошивки"))
    if rep["computer"]["secureBoot"] and any(g["vendor"] == "NVIDIA" for g in rep["graphics"]):
        out.append(_p("info", "Secure Boot is on: installing NVIDIA's driver asks for a MOK password once",
                      "Secure Boot включён: при установке драйвера NVIDIA один раз спросят пароль MOK"))
    order = {"fail": 0, "warn": 1, "info": 2}
    return sorted(out, key=lambda p: order[p["level"]])


# ---- the report -----------------------------------------------------------------------------------
def lines(rep: dict) -> list[tuple[str, str]]:
    """(label, value) rows in the reader's language."""
    c, p, pw, inp = rep["computer"], rep["processor"], rep["power"], rep["input"]
    rows = []
    model = " ".join(x for x in (c["vendor"], c["product"], c["version"]) if x) or "?"
    fw = "UEFI" if c["firmware"] == "uefi" else "BIOS"
    sb = {True: tr("Secure Boot on", "Secure Boot вкл."), False: tr("Secure Boot off", "Secure Boot выкл."),
          None: ""}[c["secureBoot"]]
    rows.append((tr("Computer", "Компьютер"), " · ".join(x for x in (model, c["bios"] and f"BIOS {c['bios']}", fw, sb) if x)))
    cpu = " · ".join(x for x in (p["model"], p["threads"] and count(p["threads"], "thread", "threads", "поток", "потока", "потоков"),
                                p["memoryGiB"] and tr(f"{smart(p['memoryGiB'])} GB RAM", f"{smart(p['memoryGiB'])} ГБ памяти")) if x)
    rows.append((tr("Processor", "Процессор"), cpu or "?"))
    gfx = [f"{g['vendor']} {g['id']} → {g['driver'] or tr('no driver', 'нет драйвера')}" for g in rep["graphics"]]
    if rep["screens"]:
        gfx.append(tr("screens: ", "экраны: ") + ", ".join(rep["screens"]))
    rows.append((tr("Graphics", "Графика"), " · ".join(gfx) or "?"))
    net = [f"{n['name']} {'Wi-Fi' if n['kind'] == 'wifi' else 'Ethernet'} ({n['driver'] or '?'}, {n['state'] or '?'})"
           for n in rep["network"]]
    net += [f"{n['vendor']} {n['id']} → {n['driver'] or tr('no driver', 'нет драйвера')}"
            for n in rep["networkControllers"] if not n["driver"]]
    if rep["bluetooth"]:
        net.append("Bluetooth")
    rows.append((tr("Network", "Сеть"), " · ".join(net) or tr("none", "нет")))
    rows.append((tr("Sound", "Звук"), " · ".join(f"{s['name']} ({s['driver']})" for s in rep["sound"]) or tr("none", "нет")))
    bat = [f"{b['name']} {b['capacity'] if b['capacity'] is not None else '?'}%"
           + (tr(f", health {b['healthPct']}%", f", износ: держит {b['healthPct']}%") if b["healthPct"] is not None else "")
           for b in pw["batteries"]]
    if pw["ac"] is not None:
        bat.append(tr("on AC", "от сети") if pw["ac"] else tr("on battery", "от батареи"))
    rows.append((tr("Power", "Питание"), " · ".join(bat) or tr("no battery", "без батареи")))
    rows.append((tr("Sleep", "Сон"), pw["sleep"] or "?"))
    ins = [tr("touchpad: ", "тачпад: ") + ", ".join(inp["touchpad"])] if inp["touchpad"] else []
    if inp["touchscreen"]:
        ins.append(tr("touch screen: ", "сенсорный экран: ") + ", ".join(inp["touchscreen"]))
    if inp["camera"]:
        ins.append(tr("camera: ", "камера: ") + ", ".join(inp["camera"]))
    rows.append((tr("Input", "Ввод"), " · ".join(ins) or "—"))
    rows.append((tr("Disks", "Диски"), " · ".join(
        f"{d['name']} {d['model'] or ''} {d['sizeGB']} GB {'SSD' if d['ssd'] else 'HDD'}"
        + (tr(" (removable)", " (съёмный)") if d["removable"] else "") for d in rep["disks"]) or "?"))
    rows.append((tr("Kernel", "Ядро"), c["kernel"]))
    return rows


def render(rep: dict, color: bool = True) -> str:
    st = ui.style() if color else None
    paint = (lambda kind, s: getattr(st, kind)(s)) if st else (lambda kind, s: s)
    ru = tr("en", "ru") == "ru"
    out = [paint("accent", tr("SOS hardware report", "SOS: отчёт о железе")) + "  " + paint("faint", rep["at"]), ""]
    for label, value in lines(rep):
        out.append(f"  {label:<10} {value}")
    out += ["", "  " + tr("Problems", "Что не так")]
    if not rep["problems"]:
        out.append("   " + paint("ok", "✓") + " " + tr("nothing found: ready for daily work",
                                                          "ничего не найдено: можно работать"))
    for pr in rep["problems"]:
        mark = {"fail": paint("bad", "×"), "warn": paint("warn", "!"), "info": paint("faint", "·")}[pr["level"]]
        out.append(f"   {mark} {pr['ru'] if ru else pr['en']}")
        fix = pr["fixRu"] if ru else pr["fixEn"]
        if fix:
            out.append("     " + paint("faint", "→ " + fix))
    if rep["firmwareMissing"]:
        out += ["", "  " + tr("Missing firmware", "Не найдена прошивка")] + [f"   {f}" for f in rep["firmwareMissing"]]
    if rep["kernelErrors"]:
        out += ["", "  " + tr("Kernel errors (this boot, last ones)", "Ошибки ядра (эта загрузка, последние)")]
        out += [f"   {e}" for e in rep["kernelErrors"]]
    return "\n".join(out) + "\n"


def main(args, ctx: Ctx) -> int:
    rep = gather(ctx)
    if getattr(args, "json", False):
        ui.print_json(rep)
    else:
        ui.out(render(rep))
    save = getattr(args, "save", None)
    if save is not None:
        path = Path(os.path.expanduser(save or "~/sos-hardware-report.txt"))
        try:
            path.write_text(render(rep, color=False), encoding="utf-8")
            ui.note(tr(f"saved: {path} (no serial numbers, no MAC addresses) — send it to whoever helps you",
                       f"сохранено: {path} (без серийных номеров и MAC-адресов) — отправьте тому, кто помогает"))
        except OSError as e:
            ui.err(tr(f"could not save {path}: {e}", f"не удалось сохранить {path}: {e}"))
            return 1
    return 1 if any(p["level"] == "fail" for p in rep["problems"]) else 0
