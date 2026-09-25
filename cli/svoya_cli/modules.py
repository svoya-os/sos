"""``sos modules list | info | add | remove | profiles`` — ARCHITECTURE §4.5.

``add`` = snapshot → apt/flatpak/scripts → record in /var/lib/svoya/modules.json → snapshot.
``remove`` reverses it: only packages *this module* installed and no other module still needs are
removed. Root work runs in one elevated process (``pkexec sos modules add … --yes``) that re-reads
the catalog from its trusted location; per-user steps (``user_scripts``) run afterwards as the user.
Scripts get a clean environment (see ``script_env``) and live in ``modules/<id>/``.

Catalog extensions beyond §4.5 (all optional): ``aliases`` (names for ``sos install``),
``hardware`` (["nvidia"] | ["amd"] …), ``options`` ({name = {en, ru, disk_gb}} → ``--with name``),
``user_scripts`` ({install, remove} run as the user), ``proprietary`` (installed only on request),
and placeholders in ``apt`` entries: ``{nvidia.branch}``, ``{nvidia.open}``, ``{kernel.flavor}``.
"""
from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import i18n, ui
from .context import Ctx
from .i18n import pick, tr
from .runner import svoya_argv
from .snapshots import Guard
from .util import iso, read_json, write_json

REQUIRED = ("id", "name", "summary", "category")
CATEGORIES = ("ai", "media", "ml", "agents", "dev", "system", "cloud", "apps")
FLATHUB = "https://dl.flathub.org/repo/flathub.flatpakrepo"
CLEAN_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


class ModuleError(Exception):
    pass


def load_catalog(modules_dir: Path) -> dict[str, dict]:
    cat: dict[str, dict] = {}
    for f in sorted(modules_dir.glob("*.toml")) if modules_dir.is_dir() else []:
        if f.name == "profiles.toml":
            continue
        try:
            m = tomllib.loads(f.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as e:
            raise ModuleError(f"{f}: {e}") from None
        missing = [k for k in REQUIRED if k not in m]
        if missing:
            raise ModuleError(f"{f}: missing {', '.join(missing)}")
        if m["id"] != f.stem:
            raise ModuleError(f"{f}: id {m['id']!r} does not match the file name")
        m.setdefault("requires", [])
        m.setdefault("apt", [])
        m.setdefault("flatpak", [])
        m.setdefault("scripts", {})
        m.setdefault("profiles", [])
        m["_dir"] = str(modules_dir / m["id"])
        cat[m["id"]] = m
    return cat


def load_profiles(modules_dir: Path) -> dict:
    try:
        return tomllib.loads((modules_dir / "profiles.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def find(cat: dict[str, dict], name: str) -> dict | None:
    n = name.lower()
    if n in cat:
        return cat[n]
    for m in cat.values():
        if n in [a.lower() for a in m.get("aliases", [])]:
            return m
    return None


# ---------------------------------------------------------------- machine facts for scripts/placeholders

def gpu_facts(ctx: Ctx) -> dict:
    from .config import load as load_cfg
    from .hw import gpu as gpu_mod
    from .hw import nvidia_db
    gpus = gpu_mod.inventory(ctx)
    g = gpu_mod.primary_compute(gpus)
    kernel = (ctx.read("/proc/sys/kernel/osrelease") or os.uname().release).strip()
    out = {"vendors": sorted({x.vendor for x in gpus}), "vendor": g.vendor if g else "none",
           "kernel.flavor": nvidia_db.kernel_flavor(kernel), "torch": gpu_mod.torch_backend(
               g, load_cfg(ctx.paths).get("gpu", {}).get("rocm_backend", "rocm7.2"))}
    nv = next((x for x in gpus if x.vendor == "nvidia"), None)
    if nv is not None and nv.arch_info and nv.arch_info.branch:
        info = nv.arch_info
        out.update({"nvidia.arch": info.id, "nvidia.branch": info.branch,
                    "nvidia.open": "-open" if info.open_modules != "unsupported" else ""})
    amd = next((x for x in gpus if x.vendor == "amd"), None)
    if amd is not None:
        out["amd.gfx"] = amd.gfx or ""
    return out


def expand(pkgs: list[str], facts: dict) -> list[str]:
    out = []
    for p in pkgs:
        missing = [k for k in re.findall(r"\{([a-z.]+)\}", p) if k not in facts]
        if missing:
            raise ModuleError(tr(f"{p}: needs {', '.join(missing)} (hardware not present)",
                                 f"{p}: нужно {', '.join(missing)} (такого оборудования нет)"))
        out.append(re.sub(r"\{([a-z.]+)\}", lambda m: str(facts[m.group(1)]), p))
    return out


def applicable(m: dict, facts: dict) -> tuple[bool, str]:
    hw = m.get("hardware") or []
    if hw and not any(v in facts.get("vendors", []) for v in hw):
        return False, tr(f"needs a {'/'.join(hw)} GPU", f"нужна видеокарта {'/'.join(hw)}")
    return True, ""


# ---------------------------------------------------------------- state

def load_state(ctx: Ctx) -> dict:
    s = read_json(ctx.paths.modules_state) or {}
    s.setdefault("v", 1)
    s.setdefault("modules", {})
    s.setdefault("history", [])
    return s


def size_label(gb: float) -> str:
    """«1,2 ГБ»; below 0.1 GB in megabytes («1 МБ»), so a small package does not read as «0 ГБ»."""
    if 0 < gb < 0.1:
        return f"{max(1, round(gb * 1024))} {tr('MB', 'МБ')}"
    return f"{i18n.smart(gb)} {tr('GB', 'ГБ')}"


def shipped(ctx: Ctx, m: dict) -> bool:
    """Part of the image rather than added through sos: ``detect`` names a file that proves it."""
    d = m.get("detect")
    return bool(d) and ctx.sys(d).exists()


def with_shipped(ctx: Ctx, cat: dict, state: dict) -> dict:
    """The state plus modules that came with the image, so they list as installed and can be removed."""
    for m in cat.values():
        if m["id"] not in state["modules"] and shipped(ctx, m):
            state["modules"][m["id"]] = {"apt": list(m["apt"]), "aptNew": list(m["apt"]), "flatpak": [],
                                         "options": [], "shipped": True}
    return state


def save_state(ctx: Ctx, state: dict) -> None:
    state["history"] = state["history"][-200:]
    write_json(ctx.paths.modules_state, state)


# ---------------------------------------------------------------- planning

@dataclass
class Plan:
    action: str                                  # add | remove
    modules: list[dict] = field(default_factory=list)
    apt: list[str] = field(default_factory=list)
    flatpak: list[str] = field(default_factory=list)
    scripts: list[tuple[str, str, str]] = field(default_factory=list)   # (module, path, "root"|"user")
    options: dict[str, list[str]] = field(default_factory=dict)
    disk_gb: float = 0.0
    vram_gb_min: float = 0.0
    notes: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def as_json(self) -> dict:
        return {"action": self.action, "modules": [m["id"] for m in self.modules], "apt": self.apt,
                "flatpak": self.flatpak, "scripts": [{"module": a, "path": b, "as": c} for a, b, c in self.scripts],
                "options": self.options, "diskGb": round(self.disk_gb, 3), "vramGbMin": self.vram_gb_min,
                "notes": self.notes, "skipped": self.skipped}


def resolve_order(cat: dict, ids: list[str]) -> list[dict]:
    order: list[dict] = []
    seen: set[str] = set()

    def visit(i: str, stack: tuple = ()) -> None:
        if i in stack:
            raise ModuleError(f"dependency cycle: {' → '.join(stack + (i,))}")
        if i in seen:
            return
        m = cat.get(i)
        if m is None:
            raise ModuleError(tr(f"unknown module: {i}", f"неизвестный модуль: {i}"))
        for dep in m["requires"]:
            visit(dep, stack + (i,))
        seen.add(i)
        order.append(m)

    for i in ids:
        visit(i)
    return order


def plan_add(cat: dict, ids: list[str], state: dict, facts: dict, options: list[str] | None = None,
             force: bool = False) -> Plan:
    options = options or []
    plan = Plan("add")
    installed = state["modules"]
    for m in resolve_order(cat, ids):
        if m["id"] in installed and m["id"] not in ids:
            continue
        ok, why = applicable(m, facts)
        if not ok and not force:
            if m["id"] in ids:
                raise ModuleError(f"{m['id']}: {why}")
            plan.skipped.append(f"{m['id']}: {why}")
            continue
        if m["id"] in installed:
            plan.notes.append(tr(f"{m['id']} is already installed — re-running its install (idempotent)",
                                 f"{m['id']} уже установлен — повторяю установку (идемпотентно)"))
        plan.modules.append(m)
        for p in expand(m["apt"], facts):
            if p not in plan.apt:
                plan.apt.append(p)
        for fp in m["flatpak"]:
            if fp not in plan.flatpak:
                plan.flatpak.append(fp)
        opts = [o for o in options if o in (m.get("options") or {})]
        if opts:
            plan.options[m["id"]] = opts
        plan.disk_gb += float(m.get("disk_gb", 0)) + sum(float(m["options"][o].get("disk_gb", 0)) for o in opts)
        plan.vram_gb_min = max(plan.vram_gb_min, float(m.get("vram_gb_min", 0)))
        if m["scripts"].get("install"):
            plan.scripts.append((m["id"], os.path.join(m["_dir"], m["scripts"]["install"]), "root"))
        if (m.get("user_scripts") or {}).get("install"):
            plan.scripts.append((m["id"], os.path.join(m["_dir"], m["user_scripts"]["install"]), "user"))
        if m.get("license_note"):
            plan.notes.append(f"{m['id']}: {pick(m['license_note'])}")
    unknown_opts = [o for o in options if not any(o in (m.get("options") or {}) for m in plan.modules)]
    if unknown_opts:
        raise ModuleError(tr(f"unknown option(s): {', '.join(unknown_opts)}", f"неизвестные опции: {', '.join(unknown_opts)}"))
    return plan


def plan_remove(cat: dict, ids: list[str], state: dict, force: bool = False) -> Plan:
    plan = Plan("remove")
    installed = state["modules"]
    for i in ids:
        if i not in installed:
            raise ModuleError(tr(f"{i} is not installed", f"{i} не установлен"))
        users = [o for o, rec in installed.items() if o not in ids and i in (cat.get(o) or {}).get("requires", [])]
        if users and not force:
            raise ModuleError(tr(f"{i} is needed by {', '.join(users)} (remove them first or use --force)",
                                 f"{i} нужен модулям {', '.join(users)} (сначала удалите их или --force)"))
    still_needed: set[str] = set()
    for o, rec in installed.items():
        if o not in ids:
            still_needed.update(rec.get("apt", []))
    for i in ids:
        rec = installed[i]
        m = cat.get(i, {"id": i, "_dir": "", "scripts": {}})
        plan.modules.append(m)
        if m.get("user_scripts", {}).get("remove"):
            plan.scripts.append((i, os.path.join(m["_dir"], m["user_scripts"]["remove"]), "user"))
        if m.get("scripts", {}).get("remove"):
            plan.scripts.append((i, os.path.join(m["_dir"], m["scripts"]["remove"]), "root"))
        for p in rec.get("aptNew", []):
            if p not in still_needed and p not in plan.apt:
                plan.apt.append(p)
        for fp in rec.get("flatpak", []):
            if fp not in plan.flatpak:
                plan.flatpak.append(fp)
        plan.disk_gb += float(m.get("disk_gb", 0))
    return plan


# ---------------------------------------------------------------- execution

def script_env(ctx: Ctx, m: dict, action: str, facts: dict, options: list[str], as_user: bool) -> dict:
    uid, name, home = ctx.target_user()
    env = {"PATH": CLEAN_PATH, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "DEBIAN_FRONTEND": "noninteractive",
           "HOME": str(home) if as_user else "/root",
           "SVOYA_MODULE": m["id"], "SVOYA_ACTION": action, "SVOYA_MODULE_DIR": m["_dir"],
           "SVOYA_LIB": str(Path(m["_dir"]).parent / "lib"), "SVOYA_TARGET_USER": name,
           "SVOYA_TARGET_UID": str(uid), "SVOYA_TARGET_HOME": str(home), "SVOYA_AI_ROOT": str(ctx.paths.ai_root),
           "SVOYA_LANG": i18n.lang(), "SVOYA_GPU_VENDOR": facts.get("vendor", "none"),
           "SVOYA_TORCH_BACKEND": facts.get("torch", "cpu"), "SVOYA_KERNEL_FLAVOR": facts.get("kernel.flavor", "generic"),
           "SVOYA_NVIDIA_ARCH": facts.get("nvidia.arch", ""), "SVOYA_NVIDIA_BRANCH": facts.get("nvidia.branch", ""),
           "SVOYA_NVIDIA_OPEN": "1" if facts.get("nvidia.open") else "0", "SVOYA_AMD_GFX": facts.get("amd.gfx", "")}
    if as_user:
        for k in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY"):
            if ctx.env.get(k):
                env[k] = ctx.env[k]
    for o in options:
        env["SVOYA_OPT_" + re.sub(r"[^A-Z0-9]", "_", o.upper())] = "1"
    return env


def dpkg_installed(ctx: Ctx, pkgs: list[str]) -> set[str]:
    if not pkgs:
        return set()
    r = ctx.runner.run(["dpkg-query", "-W", "-f=${Package}\t${db:Status-Abbrev}\n", *pkgs], timeout=30)
    out = set()
    for line in r.out.splitlines():
        name, _, status = line.partition("\t")
        if status.startswith("ii"):
            out.add(name.split(":")[0])
    return out


def apply_root(ctx: Ctx, plan: Plan, facts: dict, *, snapshot: bool = True) -> dict:
    """The privileged half. Returns a result dict; raises nothing for script failures (reported)."""
    r = ctx.runner
    state = load_state(ctx)
    result: dict = {"ok": True, "steps": []}
    verb = "add" if plan.action == "add" else "remove"
    desc = f"sos: modules {verb} {' '.join(m['id'] for m in plan.modules)}"
    guard = Guard(ctx, desc) if snapshot else None
    if guard:
        guard.__enter__()
        if guard.reason:
            result["steps"].append(f"no snapshot: {guard.reason}")
    try:
        if plan.action == "add":
            before = dpkg_installed(ctx, plan.apt)
            new = [p for p in plan.apt if p not in before]
            if new:
                r.stream(["apt-get", "update"], env={"DEBIAN_FRONTEND": "noninteractive", "PATH": CLEAN_PATH})
                rc = r.stream(["apt-get", "install", "-y", *new], env={"DEBIAN_FRONTEND": "noninteractive", "PATH": CLEAN_PATH})
                result["steps"].append(f"apt-get install {' '.join(new)} → {rc}")
                if rc != 0:
                    result["ok"] = False
                    return result
            if plan.flatpak:
                r.run(["flatpak", "remote-add", "--system", "--if-not-exists", "flathub", FLATHUB], timeout=120, mutating=True)
                rc = r.stream(["flatpak", "install", "--system", "-y", "--noninteractive", "flathub", *plan.flatpak])
                result["steps"].append(f"flatpak install {' '.join(plan.flatpak)} → {rc}")
                if rc != 0:
                    result["ok"] = False
                    return result
            for mid, path, who in plan.scripts:
                if who != "root":
                    continue
                m = next(x for x in plan.modules if x["id"] == mid)
                rc = r.stream(["bash", path], env=script_env(ctx, m, "install", facts, plan.options.get(mid, []), False),
                              cwd=m["_dir"])
                result["steps"].append(f"{mid}/{os.path.basename(path)} → {rc}")
                if rc != 0:
                    result["ok"] = False
                    return result
            for m in plan.modules:
                mine = [p for p in expand(m["apt"], facts)]
                state["modules"][m["id"]] = {
                    "installedAt": iso(ctx.now()), "apt": mine, "aptNew": [p for p in mine if p in new],
                    "flatpak": list(m["flatpak"]), "options": plan.options.get(m["id"], []),
                    "snapshot": {"pre": guard.pre if guard else None}}
        else:
            for mid, path, who in plan.scripts:
                if who != "root":
                    continue
                m = next(x for x in plan.modules if x["id"] == mid)
                rc = r.stream(["bash", path], env=script_env(ctx, m, "remove", facts, [], False), cwd=m["_dir"])
                result["steps"].append(f"{mid}/{os.path.basename(path)} → {rc}")
            if plan.flatpak:
                r.stream(["flatpak", "uninstall", "--system", "-y", "--noninteractive", *plan.flatpak])
            if plan.apt:
                rc = r.stream(["apt-get", "remove", "-y", *plan.apt], env={"DEBIAN_FRONTEND": "noninteractive", "PATH": CLEAN_PATH})
                result["steps"].append(f"apt-get remove {' '.join(plan.apt)} → {rc}")
            for m in plan.modules:
                state["modules"].pop(m["id"], None)
        state["history"].append({"action": plan.action, "modules": [m["id"] for m in plan.modules],
                                 "at": iso(ctx.now()), "ok": result["ok"], "snapshot": {"pre": guard.pre if guard else None}})
        if not ctx.dry_run:
            save_state(ctx, state)
    finally:
        if guard:
            guard.__exit__(None, None, None)
            result["snapshot"] = {"pre": guard.pre, "post": guard.post}
    return result


def run_user_scripts(ctx: Ctx, plan: Plan, facts: dict) -> list[str]:
    log = []
    for mid, path, who in plan.scripts:
        if who != "user":
            continue
        m = next(x for x in plan.modules if x["id"] == mid)
        env = script_env(ctx, m, "install" if plan.action == "add" else "remove", facts, plan.options.get(mid, []), True)
        argv = ["bash", path]
        uid, name, _home = ctx.target_user()
        if ctx.is_root and uid != 0:          # never run per-user steps as root
            argv = ["runuser", "-u", name, "--", "env", *[f"{k}={v}" for k, v in env.items()], "bash", path]
        rc = ctx.runner.stream(argv, env=env, cwd=m["_dir"])
        log.append(f"{mid}/{os.path.basename(path)} → {rc}")
    return log


# ---------------------------------------------------------------- CLI

def render_plan(plan: Plan, facts: dict) -> None:
    st = ui.style()
    verb = tr("add", "добавить") if plan.action == "add" else tr("remove", "удалить")
    ui.head(f"{verb}: " + ", ".join(m["id"] for m in plan.modules))
    ui.kv(tr("snapshot", "снимок"), tr("before and after (snapper)", "до и после (snapper)"), width=11)
    if plan.apt:
        ui.kv("apt", " ".join(plan.apt), width=11)
    if plan.flatpak:
        ui.kv("flatpak", " ".join(plan.flatpak), width=11)
    for mid, path, who in plan.scripts:
        ui.kv(tr("script", "скрипт"), f"{path} " + st.faint(f"({'root' if who == 'root' else tr('as you', 'от вас')})"), width=11)
    for mid, opts in plan.options.items():
        ui.kv(tr("options", "опции"), f"{mid}: {', '.join(opts)}", width=11)
    if plan.action == "add":
        ui.kv(tr("disk", "диск"), f"≈ {size_label(plan.disk_gb)}", width=11)
        if plan.vram_gb_min:
            ui.kv(tr("VRAM", "видеопамять"), tr(f"from {i18n.smart(plan.vram_gb_min)} GB", f"от {i18n.smart(plan.vram_gb_min)} ГБ"), width=11)
    for n in plan.notes:
        ui.note(n)
    for s in plan.skipped:
        ui.note(tr("skipped ", "пропущено ") + s)


def cmd_list(args, ctx: Ctx, cat: dict) -> int:
    state = with_shipped(ctx, cat, load_state(ctx))
    facts = gpu_facts(ctx)
    rows = []
    for m in sorted(cat.values(), key=lambda m: (CATEGORIES.index(m["category"]) if m["category"] in CATEGORIES else 99, m["id"])):
        ok, why = applicable(m, facts)
        rows.append({"id": m["id"], "name": m["name"], "summary": m["summary"], "category": m["category"],
                     "installed": m["id"] in state["modules"], "applicable": ok, "reason": why or None,
                     "diskGb": m.get("disk_gb", 0), "vramGbMin": m.get("vram_gb_min", 0), "requires": m["requires"],
                     "profiles": m["profiles"], "aliases": m.get("aliases", []), "options": list((m.get("options") or {}).keys()),
                     "proprietary": bool(m.get("proprietary")), "licenseNote": m.get("license_note")})
    if args.json:
        ui.print_json({"modules": rows})
        return 0
    st = ui.style()
    ui.head(tr("modules", "модули") + st.faint(tr(" · nothing is installed unless you ask", " · ставится только то, что попросите")))
    name_w = max([24] + [len(pick(r["name"])) for r in rows])   # «Студия (картинки и видео)» is 25
    for r in rows:
        mark = st.ok("✓") if r["installed"] else (st.faint("·") if r["applicable"] else st.faint("×"))
        name = pick(r["name"])
        extra = st.faint(size_label(r["diskGb"])) if r["diskGb"] else ""
        ui.out(f"  {mark} {r['id'].ljust(12)} {name.ljust(name_w)}  {extra}")
        ui.note(pick(r["summary"]) + (f" — {r['reason']}" if not r["applicable"] else ""), indent=17)
    ui.note(tr("sos install <id> · sos remove <id> · sos modules info <id>",
               "sos установить <id> · sos удалить <id> · sos modules info <id>"))
    return 0


def cmd_info(args, ctx: Ctx, cat: dict) -> int:
    m = find(cat, args.module)
    if m is None:
        return _unknown(args.module, cat)
    state = with_shipped(ctx, cat, load_state(ctx))
    if args.json:
        ui.print_json({k: v for k, v in m.items() if not k.startswith("_")} | {"installed": m["id"] in state["modules"],
                                                                                "state": state["modules"].get(m["id"])})
        return 0
    st = ui.style()
    ui.head(f"{pick(m['name'])} {st.faint('(' + m['id'] + ')')}" + (st.ok(tr("  installed", "  установлен")) if m["id"] in state["modules"] else ""))
    ui.out("  " + pick(m["summary"]))
    for label, val in ((tr("requires", "требует"), ", ".join(m["requires"]) or "—"),
                       ("apt", " ".join(m["apt"]) or "—"), ("flatpak", " ".join(m["flatpak"]) or "—"),
                       (tr("disk", "диск"), f"≈ {size_label(float(m.get('disk_gb', 0)))}"),
                       (tr("VRAM", "видеопамять"), f"{i18n.smart(float(m['vram_gb_min']))} {tr('GB', 'ГБ')}+"
                        if float(m.get("vram_gb_min", 0)) > 0 else "—"),
                       (tr("profiles", "профили"), ", ".join(m["profiles"]) or "—")):
        ui.kv(label, val, width=12)
    for o, d in (m.get("options") or {}).items():
        ui.kv(f"--with {o}", pick(d) + (st.faint(f"  +{d.get('disk_gb')} {tr('GB', 'ГБ')}") if d.get("disk_gb") else ""), width=12)
    if m.get("license_note"):
        ui.kv(tr("license", "лицензия"), pick(m["license_note"]), width=12)
    for kind in ("scripts", "user_scripts"):
        for action, fn in (m.get(kind) or {}).items():
            path = Path(m["_dir"]) / fn
            ui.kv(f"{action}", str(path) + st.faint("" if kind == "scripts" else tr(" (as you)", " (от вас)")), width=12)
            if args.show_scripts and path.exists():
                for line in path.read_text().splitlines():
                    ui.out("      " + st.faint(line))
    return 0


def _unknown(name: str, cat: dict) -> int:
    import difflib
    names = list(cat) + [a for m in cat.values() for a in m.get("aliases", [])]
    close = difflib.get_close_matches(name, names, n=3, cutoff=0.5)
    ui.err(tr(f"sos: no module '{name}'", f"sos: нет модуля «{name}»") +
           (tr(". Did you mean: ", ". Может быть: ") + ", ".join(close) + "?" if close else ""))
    return 2


def cmd_profiles(args, ctx: Ctx, cat: dict) -> int:
    prof = load_profiles(ctx.paths.modules_dir)
    facts = gpu_facts(ctx)
    out = []
    for pid, p in (prof.get("profiles") or {}).items():
        mods = resolve_profile_modules(p, facts, prof, offline=args.offline)
        out.append({"id": pid, "name": p.get("name"), "summary": p.get("summary"), "modules": mods,
                    "layout": p.get("layout"), "jacksonRoute": ("local" if args.offline else p.get("jackson_route")),
                    "diskGb": round(sum(float(cat.get(m, {}).get("disk_gb", 0)) for m in mods), 1)})
    if args.json:
        ui.print_json({"profiles": out, "modifiers": prof.get("modifiers", {})})
        return 0
    st = ui.style()
    ui.head(tr("profiles", "профили") + (st.faint(tr(" · offline", " · без сети")) if args.offline else ""))
    for p in out:
        ui.out(f"  {st.accent(p['id'].ljust(10))} {pick(p['name'])}  {st.faint(p['layout'] or '')} · {st.faint(p['jacksonRoute'] or '')}")
        ui.note(", ".join(p["modules"]) + f"  ≈ {i18n.smart(p['diskGb'])} {tr('GB', 'ГБ')}", indent=13)
    return 0


def resolve_profile_modules(p: dict, facts: dict, prof: dict, offline: bool = False) -> list[str]:
    mods: list[str] = []
    for m in p.get("modules", []):
        if m == "@gpu":
            vendor = facts.get("vendor")
            m = {"nvidia": "nvidia", "amd": "rocm"}.get(vendor or "", "")
            if not m:
                continue
        if m not in mods:
            mods.append(m)
    if offline:
        mod = (prof.get("modifiers") or {}).get("offline", {})
        mods = [m for m in mods if m not in mod.get("remove_modules", [])]
        for m in mod.get("add_modules", []):
            if m not in mods:
                mods.append(m)
    return mods


def cmd_change(args, ctx: Ctx, cat: dict, action: str) -> int:
    facts = gpu_facts(ctx)
    state = with_shipped(ctx, cat, load_state(ctx))
    names = list(args.modules)
    options = list(getattr(args, "options", []) or [])
    if action == "add" and getattr(args, "profile", None):
        prof = load_profiles(ctx.paths.modules_dir)
        p = (prof.get("profiles") or {}).get(args.profile)
        if p is None:
            ui.err(tr(f"sos: no profile '{args.profile}'", f"sos: нет профиля «{args.profile}»"))
            return 2
        names += resolve_profile_modules(p, facts, prof, offline=getattr(args, "offline", False))
    if not names:
        ui.err(tr("sos: name at least one module (sos modules list)", "sos: укажите модуль (sos modules list)"))
        return 2
    ids = []
    for n in names:
        m = find(cat, n)
        if m is None:
            return _unknown(n, cat)
        if m["id"] not in ids:
            ids.append(m["id"])
    try:
        plan = plan_add(cat, ids, state, facts, options, force=args.force) if action == "add" else \
            plan_remove(cat, ids, state, force=args.force)
    except ModuleError as e:
        ui.err(f"sos: {e}")
        return 2
    if args.json and (ctx.dry_run or not args.yes):
        ui.print_json({"plan": plan.as_json(), "dryRun": ctx.dry_run})
        return 0
    if not args.json and not getattr(args, "root_only", False):
        render_plan(plan, facts)
        if args.show_scripts:
            for _mid, path, _who in plan.scripts:
                ui.out(ui.style().faint(f"--- {path}"))
                try:
                    ui.out(Path(path).read_text())
                except OSError:
                    pass
    if ctx.dry_run:
        res = apply_root(ctx, plan, facts, snapshot=not args.no_snapshot)
        run_user_scripts(ctx, plan, facts)
        for s in res["steps"]:
            if s.startswith("no snapshot"):
                ui.note(tr(f"note: {s}", f"внимание: без снимка — {s.split(': ', 1)[-1]}"))
        return 0
    if not ui.confirm(tr("Go ahead?", "Выполнить?"), default=True, assume=True if args.yes else None):
        return 1
    if not ctx.is_root:                  # state lives in /var/lib/svoya: the root half always runs
        argv = ["pkexec", *svoya_argv(), "modules", action, *ids, "--yes", "--root-only"]
        argv += [f"--with={o}" for o in options] if action == "add" else []
        if args.force:
            argv.append("--force")
        if args.no_snapshot:
            argv.append("--no-snapshot")
        rc = ctx.runner.stream(argv)
        if rc != 0:
            ui.err(tr(f"sos: the privileged step failed ({rc})", f"sos: шаг с правами root не удался ({rc})"))
            return rc
    else:
        res = apply_root(ctx, plan, facts, snapshot=not args.no_snapshot)
        for s in res["steps"]:
            ui.note(s)
        if not res["ok"]:
            return 1
        if getattr(args, "root_only", False):
            return 0
    for line in run_user_scripts(ctx, plan, facts):
        ui.note(line)
    ui.head(tr("done · undo with `sos undo`", "готово · отменить: `sos undo`"))
    return 0


def main(args, ctx: Ctx | None = None) -> int:
    ctx = ctx or Ctx()
    try:
        cat = load_catalog(ctx.paths.modules_dir)
    except ModuleError as e:
        ui.err(f"sos: {e}")
        return 2
    cmd = args.modules_cmd or "list"
    if cmd == "list":
        return cmd_list(args, ctx, cat)
    if cmd == "info":
        return cmd_info(args, ctx, cat)
    if cmd == "profiles":
        return cmd_profiles(args, ctx, cat)
    return cmd_change(args, ctx, cat, "add" if cmd == "add" else "remove")
