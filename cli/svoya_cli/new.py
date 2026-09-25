"""``sos new <name> [--template torch|llm-finetune|comfy-node|agent|upsil]`` — a uv project wired to SOS.

Creates pyproject.toml (PyTorch index chosen by GPU Doctor — ``uv --torch-backend=auto`` ignores
the GPU generation), svoya.toml (GPU needs, backend, models/datasets by hash, tracker, cloud target),
src/, notebooks/, configs/, scripts/, tests/, ``data → /srv/ai/datasets`` and ``models → /srv/ai``
links, a dev container (GPU optional), a Containerfile, a SkyPilot task and a README; ``.env`` sets
``UV_TORCH_BACKEND``. Templates: ``svoya_cli/data/new/{common,<template>}``.

``upsil`` is an UpsiL program instead (main.upl, prompts.upl, tests for ``upsil test``): no Python
tree, and a ``pyproject.toml`` only so that ``uv add torch`` finds this machine's PyTorch wheels.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from pathlib import Path

from . import ui
from .context import Ctx
from .i18n import tr
from .theme import engine
from .util import read_json, toml_dumps

TEMPLATES = ("torch", "llm-finetune", "comfy-node", "agent", "upsil")
DOTFILES = {"gitignore": ".gitignore", "python-version": ".python-version", "env": ".env", "envrc": ".envrc"}
INDEX = {"cu130": "https://download.pytorch.org/whl/cu130", "cu126": "https://download.pytorch.org/whl/cu126",
         "xpu": "https://download.pytorch.org/whl/xpu", "cpu": "https://download.pytorch.org/whl/cpu"}

SPEC = {
    "torch": {"description": "PyTorch project", "deps": ["torch", "torchvision", "numpy"], "torch": True,
              "entry": "src/{pkg}/train.py", "model": "—", "dataset": "synthetic", "min_vram": 0, "accel": "L4:1"},
    "llm-finetune": {"description": "LoRA fine-tune of an LLM with TRL", "torch": True,
                     "deps": ["torch", "transformers", "trl>=1.13", "peft", "datasets", "accelerate", "trackio"],
                     "entry": "src/{pkg}/train.py", "model": "qwen3.5-2b", "model_repo": "Qwen/Qwen3.5-2B",
                     "adapter": "LoRA r16", "dataset": "trl-lib/Capybara", "min_vram": 12, "accel": "L40S:1"},
    "comfy-node": {"description": "ComfyUI custom node", "deps": [], "torch": False, "entry": "nodes.py",
                   "model": "—", "dataset": "—", "min_vram": 6, "accel": "L4:1"},
    "agent": {"description": "Tool-using agent for the local model server", "deps": [], "torch": False,
              "entry": "src/{pkg}/agent.py", "model": "", "dataset": "—", "min_vram": 0, "accel": "L4:1"},
    # torch: the index only (`uv add torch` when the program needs `import nn`), not a dependency
    # model: whatever `sos models serve` offers first, or UPSIL_LLM_MODEL in .env (sos run shows it)
    "upsil": {"description": "UpsiL program", "deps": [], "torch": True, "entry": "main.upl", "model": "—",
              "dataset": "—", "min_vram": 0, "accel": "L4:1", "common": False},
}


def package_name(name: str) -> str:
    p = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or "project"
    return f"p_{p}" if p[0].isdigit() else p


def index_url(backend: str) -> str:
    if backend.startswith("rocm"):
        return f"https://download.pytorch.org/whl/{backend}"
    return INDEX.get(backend, INDEX["cpu"])


def detect(ctx: Ctx) -> dict:
    """Backend from GPU Doctor's last run (cache) or a fresh inventory; GPU label from live stats."""
    from .config import load as load_cfg
    from .hw import gpu as gpu_mod
    cache = read_json(ctx.paths.state_dir / "doctor.json") or {}
    backend = cache.get("torchBackend")
    if not backend:
        backend = gpu_mod.torch_backend(gpu_mod.primary_compute(gpu_mod.inventory(ctx)),
                                        load_cfg(ctx.paths).get("gpu", {}).get("rocm_backend", "rocm7.2"))
    stats = gpu_mod.live_stats(ctx)
    label = "CPU"
    if stats:
        g = max(stats, key=lambda s: s.get("vramTotalMiB") or 0)
        label = g.get("name", "GPU") + (f" {round((g.get('vramTotalMiB') or 0) / 1024)} GB" if g.get("vramTotalMiB") else "")
    return {"backend": backend, "label": label}


def suggested_model() -> str:
    try:
        from .models.suggest import load_ladder
        lad = load_ladder()
        m = lad["models"]["qwen3.5-9b"]
        return Path(m["quants"][0]["file"]).stem
    except (KeyError, OSError):
        return "default"


def build_context(ctx: Ctx, name: str, template: str) -> tuple[dict, dict]:
    spec = SPEC[template]
    pkg = package_name(name)
    det = detect(ctx)
    backend = det["backend"]
    idx_name = f"pytorch-{backend.replace('.', '')}"
    torch_sources = ""
    if spec["torch"]:
        torch_sources = (f"\n[tool.uv.sources]\ntorch = [{{ index = \"{idx_name}\" }}]\ntorchvision = [{{ index = \"{idx_name}\" }}]\n"
                         f"\n# PyTorch wheels for this machine ({backend}); chosen by `sos doctor`, not uv's 'auto'\n"
                         f"[[tool.uv.index]]\nname = \"{idx_name}\"\nurl = \"{index_url(backend)}\"\nexplicit = true\n")
    if template == "comfy-node":
        torch_sources = f"\n[tool.comfy]\nPublisherId = \"\"\nDisplayName = \"{name}\"\nIcon = \"\"\n"
    entry = spec["entry"].format(pkg=pkg)
    model = spec["model"] or suggested_model()
    ai = str(ctx.paths.ai_root)
    variables = {
        "project": {"name": name, "package": pkg, "template": template, "description": spec["description"]},
        "deps": ",\n".join(f'    "{d}"' for d in spec["deps"]),
        "torch_sources": torch_sources,
        "gpu": {"backend": backend, "detected": det["label"], "index_url": index_url(backend), "index_name": idx_name},
        "run": {"entry": entry, "model": model, "model_repo": spec.get("model_repo", "")},
        "tracking": {"tool": "trackio", "url": "http://localhost:7860"},
        "cloud": {"accelerators": spec["accel"]},
        "paths": {"ai": ai, "datasets": f"{ai}/datasets"},
    }
    manifest = {
        "project": {"name": name, "template": template, "created": dt.date.today().isoformat()},
        "gpu": {"required": "optional", "backend": backend, "min_vram_gb": spec["min_vram"], "detected": det["label"]},
        "run": {k: v for k, v in {"entry": entry, "model": model, "adapter": spec.get("adapter"),
                                  "dataset": spec["dataset"]}.items() if v is not None},
        "models": [{"id": spec.get("model_repo") or model, "file": "", "sha256": ""}],
        "datasets": [{"name": spec["dataset"], "path": f"data/{spec['dataset'].split('/')[-1]}", "sha256": "", "examples": 0}],
        "tracking": {"tool": "trackio", "url": "http://localhost:7860"},
        "cloud": {"target": "skypilot", "config": "sky.yaml", "accelerators": spec["accel"]},
    }
    if not spec.get("common", True):     # no sky.yaml, tracker, dataset or pinned model in a bare program
        for key in ("datasets", "tracking", "cloud", "models"):
            manifest.pop(key)
    return variables, manifest


def render_tree(src: Path, variables: dict) -> list[tuple[str, str, int]]:
    out = []
    for p in sorted(src.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts or p.suffix in (".pyc", ".pyo"):
            continue  # stray byte-code caches must never end up in a new project
        rel = str(p.relative_to(src)).replace("__package__", variables["project"]["package"])
        rel = DOTFILES.get(rel, rel)
        text = engine.render(p.read_text(encoding="utf-8"), variables, f"new/{src.name}/{rel}")
        out.append((rel, text, 0o755 if rel.endswith(".sh") else 0o644))
    return out


def main(args, ctx: Ctx | None = None) -> int:
    ctx = ctx or Ctx()
    name = args.name
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        ui.err(tr("sos: project names use letters, digits, '.', '_' and '-'", "sos: в имени проекта — буквы, цифры, '.', '_' и '-'"))
        return 2
    dest = Path(args.dir or os.getcwd()) / name
    if dest.exists() and any(dest.iterdir()):
        ui.err(tr(f"sos: {dest} exists and is not empty", f"sos: {dest} уже есть и не пуст"))
        return 2
    variables, manifest = build_context(ctx, name, args.template)
    data = ctx.paths.data_dir / "new"
    common = render_tree(data / "common", variables) if SPEC[args.template].get("common", True) else []
    files = common + render_tree(data / args.template, variables)
    if args.template == "comfy-node":      # a node is loaded from its folder root, not from src/
        files = [f for f in files if not f[0].startswith("src/") or f[0].endswith(("__init__.py", "sos_progress.py"))]
    files.append(("svoya.toml", "# SOS project manifest — read by `sos run`, Jackson and the bar.\n" + toml_dumps(manifest), 0o644))
    links = [("data", f"{ctx.paths.ai_root}/datasets"), ("models", str(ctx.paths.ai_root))]
    if args.json:
        ui.print_json({"path": str(dest), "files": [f[0] for f in files], "links": dict(links),
                       "torchBackend": variables["gpu"]["backend"], "dryRun": ctx.dry_run})
    if ctx.dry_run:
        if not args.json:
            ui.head(tr(f"would create {dest}", f"будет создан {dest}"))
            for rel, _t, _m in files:
                ui.note(rel)
            for a, b in links:
                ui.note(f"{a} → {b}")
        return 0
    for rel, text, mode in files:
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        os.chmod(p, mode)
    for a, b in links:
        try:
            (dest / a).symlink_to(b, target_is_directory=True)
        except OSError:
            pass
    if not args.no_git and ctx.runner.which("git"):
        ctx.runner.run(["git", "init", "-q", str(dest)], timeout=30, mutating=True)
    if args.json:
        return 0
    st = ui.style()
    ui.head(tr(f"project {name}", f"проект {name}") + st.faint(f" · {args.template} · {dest}"))
    if args.template == "upsil":
        from . import run
        ver = run.upsil_version(run.upsil_home())
        ui.kv("upsil", ver or st.warn(tr("not installed: sudo apt install upsil", "не установлен: sudo apt install upsil")),
              width=9)
    torch_row = f"{variables['gpu']['backend']} " + st.faint(f"({variables['gpu']['detected']})")
    if args.template == "upsil":
        torch_row = "uv add torch " + st.faint(f"→ {variables['gpu']['backend']} ({variables['gpu']['detected']})")
    ui.kv(tr("torch", "torch"), torch_row, width=9)
    ui.kv(tr("data", "данные"), f"data → {ctx.paths.ai_root}/datasets", width=9)
    ui.kv(tr("models", "модели"), f"models → {ctx.paths.ai_root}", width=9)
    if args.template == "upsil":
        ui.note(f"cd {name} && sos run {variables['run']['entry']} && upsil test")
    else:
        ui.note(f"cd {name} && uv sync && sos run {variables['run']['entry']}")
    return 0
