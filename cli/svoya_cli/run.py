"""``sos run <script> [args]`` and ``sos job progress|done|start|list``.

The header matches the design mockup (design/out/desktop-graphite.png, terminal window)::

    › sos run train.py
      среда    torch 2.13 · CUDA 13.0 · RTX 4090 24 ГБ
      модель   qwen3-tts-0.6b + LoRA r16
      данные   ru-voice · 48 213 примеров
      трекинг  localhost:7860 (trackio)

Values come from the project's ``svoya.toml`` ([run], [[datasets]], [tracking]), the project venv
(torch version read from its dist-info — no slow ``import torch``) and live GPU stats. Then the script
runs (``uv run python`` in uv projects) with ``UV_TORCH_BACKEND``/``HF_HOME`` from ``.env``, and a job
file lets the bar show progress (``SVOYA_JOB_ID``/``SVOYA_JOB_FILE`` are exported for the script).

UpsiL programs (``*.upl``, package ``upsil``) run with ``upsil run``; when the project has a ``.venv``
(``uv add torch`` for ``nn``), they run in it, with only the ``upsil`` package added to its path.
UpsiL's ``sys.progress``, ``nn.fit`` and ``ask_all`` write the job file, so the bar shows them.
"""
from __future__ import annotations

import glob
import os
import re
import shlex
import signal
import subprocess
import sys
import time
import tomllib
from pathlib import Path

from . import i18n, jobs, ui
from .context import Ctx
from .i18n import tr


def find_project(start: Path) -> Path | None:
    for d in [start, *start.parents]:
        if (d / "svoya.toml").is_file() or (d / "pyproject.toml").is_file():
            return d
    return None


def read_manifest(project: Path | None) -> dict:
    if project is None:
        return {}
    try:
        return tomllib.loads((project / "svoya.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def read_dotenv(project: Path | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if project is None:
        return out
    try:
        text = (project / ".env").read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip().removeprefix("export ").strip()] = v.strip().strip('"').strip("'")
    return out


_LOCAL = {"cu": "CUDA", "rocm": "ROCm", "xpu": "XPU", "cpu": "CPU"}


def torch_info(project: Path | None) -> tuple[str | None, str | None]:
    """('2.13', 'CUDA 13.0') from ``.venv/lib/python*/site-packages/torch-<ver>.dist-info``."""
    if project is None:
        return None, None
    hits = glob.glob(str(project / ".venv" / "lib" / "python*" / "site-packages" / "torch-*.dist-info"))
    if not hits:
        return None, None
    m = re.match(r"torch-(\d+)\.(\d+)[^+]*(?:\+([a-z]+)([\d.]*))?\.dist-info$", Path(hits[0]).name)
    if not m:
        return None, None
    ver = f"{m.group(1)}.{m.group(2)}"
    kind, num = m.group(3), m.group(4) or ""
    if not kind:
        return ver, None
    if kind == "cu" and num.isdigit() and len(num) >= 3:
        num = f"{num[:-1]}.{num[-1]}"          # cu130 → 13.0, cu126 → 12.6
    return ver, f"{_LOCAL.get(kind, kind.upper())} {num}".strip()


def python_version(project: Path | None) -> str | None:
    """The project's Python: ``.venv/pyvenv.cfg`` (``version = 3.12.3``) or ``.python-version``."""
    if project is None:
        return None
    try:
        m = re.search(r"^version(?:_info)?\s*=\s*(\d+\.\d+)", (project / ".venv" / "pyvenv.cfg").read_text(), re.M)
        if m:
            return m.group(1)
    except OSError:
        pass
    try:
        v = (project / ".python-version").read_text().strip()
        return v or None
    except OSError:
        return None


def header(script: str, manifest: dict, torch: tuple[str | None, str | None], gpu: dict | None,
           project_python: str | None = None, upsil: str | None = None) -> list[tuple[str, str]]:
    """(label, rendered value) rows; empty rows are left out."""
    st = ui.style()
    dot = f" {st.faint('·')} "
    rows: list[tuple[str, str]] = []
    env = [f"upsil {upsil}"] if upsil else []
    if torch[0]:
        env.append(f"torch {torch[0]}")
    if torch[1]:
        env.append(torch[1])
    if gpu:
        g = gpu.get("name", "GPU")
        if gpu.get("vramTotalMiB"):
            g += " " + st.faint(f"{i18n.smart(gpu['vramTotalMiB'] / 1024)} {tr('GB', 'ГБ')}")
        env.append(g)
    elif not torch[0] and not upsil:
        env.append(f"python {project_python or f'{sys.version_info.major}.{sys.version_info.minor}'}")
    rows.append((tr("env", "среда"), dot.join(env)))
    run = manifest.get("run") or {}
    model = run.get("model")
    if model and model != "—":
        rows.append((tr("model", "модель"), model + (f" {st.faint('+')} {run['adapter']}" if run.get("adapter") else "")))
    ds_name = run.get("dataset")
    if ds_name and ds_name not in ("—",):
        ds = next((d for d in manifest.get("datasets", []) if d.get("name") == ds_name), {})
        n = int(ds.get("examples") or 0)
        val = ds_name
        if n:
            val += dot + i18n.count(n, "example", "examples", "пример", "примера", "примеров")
        rows.append((tr("data", "данные"), val))
    tr_ = manifest.get("tracking") or {}
    if tr_.get("url"):
        url = re.sub(r"^https?://", "", tr_["url"]).rstrip("/")
        rows.append((tr("tracking", "трекинг"), st.cloud(url) + (" " + st.faint(f"({tr_['tool']})") if tr_.get("tool") else "")))
    return rows


UPSIL_PATH = Path("/usr/lib/upsil/path")   # the upsil package ships a folder holding only `upsil`


def upsil_home() -> Path | None:
    """The installed ``upsil`` package folder, found without importing it."""
    import importlib.util
    try:
        spec = importlib.util.find_spec("upsil")
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.origin or not spec.origin.endswith("__init__.py"):
        return None
    return Path(spec.origin).parent


def upsil_version(home: Path | None) -> str | None:
    if home is None:
        return None
    try:
        m = re.search(r'^__version__\s*=\s*"([^"]+)"', (home / "__init__.py").read_text(encoding="utf-8"), re.M)
    except OSError:
        return None
    return m.group(1) if m else None


def upsil_pythonpath(home: Path, cache: Path) -> str | None:
    """A PYTHONPATH entry that adds only ``upsil`` to a project venv (never all of dist-packages,
    which would shadow the venv's own torch or numpy)."""
    try:
        if (UPSIL_PATH / "upsil").resolve() == home.resolve():
            return str(UPSIL_PATH)
        shim = cache / "upsil-path"
        link = shim / "upsil"
        if link.is_symlink() and link.resolve() == home.resolve():
            return str(shim)
        shim.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(home, target_is_directory=True)
        return str(shim)
    except OSError:
        return None


def upsil_command(script: str, args: list[str], project: Path | None, which,
                  pythonpath: str | None) -> list[str] | None:
    """``upsil run`` in the project venv when there is one (and ``upsil`` can be put on its path),
    else the system ``upsil``; None when UpsiL is not installed."""
    venv = project / ".venv" / "bin" / "python" if project is not None else None
    if venv is not None and venv.exists() and pythonpath:
        return [str(venv), "-m", "upsil", "run", script, *args]
    if which("upsil"):
        return ["upsil", "run", script, *args]
    if pythonpath:
        return [sys.executable, "-m", "upsil", "run", script, *args]
    return None


def build_command(script: str, args: list[str], project: Path | None, which) -> list[str]:
    p = Path(script)
    if p.suffix == ".upl":
        return upsil_command(script, args, project, which, None) or ["upsil", "run", script, *args]
    if p.suffix == ".py":
        if project is not None and (project / "pyproject.toml").is_file() and which("uv"):
            return ["uv", "run", "python", script, *args]
        if project is not None and (project / ".venv" / "bin" / "python").exists():
            return [str(project / ".venv" / "bin" / "python"), script, *args]
        return [sys.executable if not which("python3") else "python3", script, *args]
    if p.suffix == ".sh":
        return ["bash", script, *args]
    return [str(p if p.is_absolute() or "/" in script else Path(".") / p), *args]


def upsil_cli_version(ctx: Ctx) -> str | None:
    """``upsil version`` (an ``upsil`` on PATH that this Python cannot import, e.g. from pipx)."""
    try:
        r = ctx.runner.run(["upsil", "version"], timeout=10)
    except OSError:
        return None
    m = re.search(r"(\d+\.\d+(?:\.\d+)?\S*)", r.out or "")
    return m.group(1) if r.ok and m else None


def main(args, ctx: Ctx | None = None) -> int:
    ctx = ctx or Ctx()
    cwd = Path.cwd()
    project = find_project(cwd)
    manifest = read_manifest(project)
    is_upl = Path(args.script).suffix == ".upl"
    dotenv = read_dotenv(project)
    upsil_env: dict[str, str] = {}
    upsil_ver = None
    if is_upl:
        home = upsil_home()
        upsil_ver = upsil_version(home)
        pythonpath = upsil_pythonpath(home, ctx.paths.cache_dir) if home is not None else None
        cmd = upsil_command(args.script, list(args.args), project, ctx.runner.which, pythonpath)
        if cmd is None:
            ui.err(tr("sos: UpsiL is not installed: sudo apt install upsil",
                      "sos: UpsiL не установлен: sudo apt install upsil"))
            return 127
        if cmd[1:3] == ["-m", "upsil"] and pythonpath:
            upsil_env["PYTHONPATH"] = os.pathsep.join(filter(None, [pythonpath, os.environ.get("PYTHONPATH")]))
        if cmd[0] == "upsil" and not upsil_ver:
            upsil_ver = upsil_cli_version(ctx)
        chosen = dotenv.get("UPSIL_LLM_MODEL") or os.environ.get("UPSIL_LLM_MODEL")
        run_sec = manifest.get("run") or {}
        if chosen and run_sec.get("model") in (None, "", "—"):
            manifest = {**manifest, "run": {**run_sec, "model": chosen}}   # the model UpsiL will ask
    else:
        cmd = build_command(args.script, list(args.args), project, ctx.runner.which)
    if not args.no_header:
        from .hw import gpu as gpu_mod
        stats = gpu_mod.live_stats(ctx)
        gpu = max(stats, key=lambda g: g.get("vramTotalMiB") or 0) if stats else None
        shown = " ".join([Path(args.script).name if "/" not in args.script else args.script, *map(shlex.quote, args.args)])
        ui.head(f"sos run {shown}")
        for label, value in header(args.script, manifest, torch_info(project), gpu, python_version(project),
                                   upsil=upsil_ver):
            ui.kv(label, value, width=9)
        ui.out("")
    env = dict(os.environ)
    env.update(dotenv)
    env.update(upsil_env)
    backend = (manifest.get("gpu") or {}).get("backend")
    if backend and "UV_TORCH_BACKEND" not in dotenv:
        env["UV_TORCH_BACKEND"] = backend
    job = None
    if not args.no_job:
        label = args.label or jobs.default_label(args.script)
        job = jobs.create(ctx.paths.jobs_dir, label=label, command=cmd, cwd=str(cwd), pid=os.getpid(),
                          now=ctx.now(), base=Path(args.script).stem)
        env["SVOYA_JOB_ID"] = job["id"]
        env["SVOYA_JOB_FILE"] = str(jobs.job_path(ctx.paths.jobs_dir, job["id"]))
    start = time.monotonic()
    try:
        proc = subprocess.Popen(cmd, env=env)
    except OSError as e:
        ui.err(f"sos: {e}")
        if job:
            jobs.finish(ctx.paths.jobs_dir, job["id"], ctx.now(), 127)
        return 127

    def forward(signum, _frame):
        try:
            proc.send_signal(signum)
        except ProcessLookupError:
            pass
    old = {s: signal.signal(s, forward) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        rc = proc.wait()
    finally:
        for s, h in old.items():
            signal.signal(s, h)
    if job:
        try:
            jobs.finish(ctx.paths.jobs_dir, job["id"], ctx.now(), rc)
        except (OSError, FileNotFoundError):
            pass
    took = i18n.duration(time.monotonic() - start)
    st = ui.style()
    if rc == 0:
        ui.out(f"{st.ok('•')} {tr('done', 'готово')} {st.faint('· ' + took)}")
    else:
        ui.out(f"{st.bad('×')} {tr(f'exited with {rc}', f'завершилось с кодом {rc}')} {st.faint('· ' + took)}")
    return rc if rc >= 0 else 128 - rc


def main_job(args, ctx: Ctx | None = None) -> int:
    ctx = ctx or Ctx()
    d = ctx.paths.jobs_dir
    try:
        if args.job_cmd == "progress":
            jobs.update(d, args.id, ctx.now(), progress=args.progress, etaSec=args.eta,
                        message=args.message, label=args.label)
            return 0
        if args.job_cmd == "done":
            jobs.finish(d, args.id, ctx.now(), args.exit_code)
            return 0
        if args.job_cmd == "start":
            j = jobs.create(d, label=args.label, command=[], cwd=os.getcwd(), pid=args.pid or os.getppid(),
                            now=ctx.now())
            print(j["id"])
            return 0
    except FileNotFoundError:
        ui.err(tr(f"sos: no job {args.id}", f"sos: нет задачи {args.id}"))
        return 1
    except ValueError as e:
        ui.err(f"sos: {e}")
        return 2
    # list
    now = ctx.now()
    items = jobs.running(d, now)
    if args.all:
        from .util import read_json
        items = [j for j in (read_json(f) for f in sorted(d.glob("*.json"))) if isinstance(j, dict)] if d.is_dir() else []
    if args.json:
        ui.print_json(items)
        return 0
    if not items:
        ui.head(tr("no running jobs", "задач нет"))
        return 0
    ui.head(tr("jobs", "задачи"))
    st = ui.style()
    for j in items:
        p = j.get("progress")
        eta = jobs.eta(j, now)
        ui.out(f"  {st.accent(j['id'])}  {j.get('label', '')}  "
               + (f"{round(p * 100)}%  " if isinstance(p, (int, float)) else "")
               + st.faint(j.get("state", "") + (tr(f" · {i18n.duration(eta)} left", f" · ещё {i18n.duration(eta)}") if eta else "")))
    return 0
