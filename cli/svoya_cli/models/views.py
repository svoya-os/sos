"""Per-tool views of the one store — symlinks and configs, never copies.

``/srv/ai/views/llama.cpp/``   for ``llama-server --models-dir`` (router mode):
    single-file models as ``<name>.gguf`` symlinks; multi-shard or vision models as ``<name>/``
    directories (first shard ``-00001-of-``, ``mmproj*`` sidecar) — the layout llama.cpp scans —
    and ``presets.ini`` for ``--models-preset``: a section for each model that needs settings of
    its own (see ``kv_presets`` in cli.py), never a setting outside a section.
``/srv/ai/views/comfyui/``     ``extra_model_paths.yaml`` + category folders of symlinks
    (``split_files/<folder>/`` of Comfy-Org repackages and top-level ComfyUI folders such as
    ``diffusion_models/`` are honoured; otherwise filename heuristics).
``/srv/ai/views/ollama/``      one Modelfile per GGUF + ``import.sh`` with the ``ollama create`` commands
    (Ollama copies weights into its own store; put ``OLLAMA_MODELS`` on the same btrfs volume and
    run ``sos models dedup --apply`` afterwards to share the blocks).
"""
from __future__ import annotations

import os
import re
import tempfile
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .hfcache import CachedFile
from .licenses import match_catalog

MARK = "svoya:generated"
PRESETS = "presets.ini"
SHARD = re.compile(r"-(\d{5})-of-(\d{5})\.gguf$", re.I)
COMFY_FOLDERS = ("checkpoints", "diffusion_models", "text_encoders", "vae", "loras", "clip_vision",
                 "controlnet", "upscale_models", "embeddings", "audio_encoders", "model_patches")
COMFY_EXT = (".safetensors", ".sft", ".ckpt", ".pt", ".pth", ".gguf", ".bin")
MEDIA_HINTS = ("comfy", "flux", "sdxl", "stable-diffusion", "wan2", "wan-", "ltx", "hunyuanvideo", "qwen-image",
               "z-image", "hidream", "cosmos", "chroma", "sd3", "sd-", "controlnet", "lora", "upscale", "esrgan")


@dataclass
class Plan:
    links: list[tuple[Path, Path]] = field(default_factory=list)      # (link, target)
    files: list[tuple[Path, str]] = field(default_factory=list)       # (path, content)
    remove: list[Path] = field(default_factory=list)                  # stale links we created
    commands: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    presets: dict[str, dict[str, str]] = field(default_factory=dict)  # model → llama.cpp settings


def _stem(filename: str) -> str:
    base = Path(filename).name
    base = SHARD.sub("", base)
    return re.sub(r"\.gguf$", "", base, flags=re.I)


# What a model needs beyond the server's settings, from its files (first shard first):
# (llama.cpp options, why) or None.
Presets = Callable[[list[Path]], "tuple[dict[str, str], str] | None"]


def presets_text(sections: list[tuple[str, Path, dict[str, str], str]]) -> str:
    """``llama-server --models-preset``: one section per model, nothing outside a section (llama.cpp
    would list such settings as a model of its own, named "default")."""
    lines = [f"; {MARK} by `sos models views`: settings of single models for llama-server --models-preset.",
             "; Rewritten at every start of svoya-llm; your own settings go in ~/.config/svoya/llm.env"]
    for name, model, opts, why in sections:
        lines += ["", f"[{name}]", f"; {why}", f"model = {model}"] + [f"{k} = {v}" for k, v in opts.items()]
    return "\n".join(lines) + "\n"


def llama_plan(files: list[CachedFile], out: Path, presets: Presets | None = None) -> Plan:
    plan = Plan()
    ggufs = [f for f in files if f.filename.lower().endswith(".gguf")]
    groups: dict[tuple[str, str, str], list[CachedFile]] = defaultdict(list)   # (repo, commit, dir)
    for f in ggufs:
        groups[(f.repo, f.commit, str(Path(f.filename).parent))].append(f)
    names: dict[str, int] = defaultdict(int)
    entries: list[tuple[str, list[CachedFile], CachedFile | None, str]] = []
    for (repo, _commit, _d), fs in sorted(groups.items()):
        mmproj = next((f for f in fs if "mmproj" in Path(f.filename).name.lower()), None)
        models: dict[str, list[CachedFile]] = defaultdict(list)
        for f in fs:
            if f is mmproj:
                continue
            models[_stem(f.filename)].append(f)
        for stem, parts in sorted(models.items()):
            entries.append((stem, sorted(parts, key=lambda p: p.filename), mmproj, repo))
            names[stem] += 1
    sections: list[tuple[str, Path, dict[str, str], str]] = []
    for stem, parts, mmproj, repo in entries:
        name = stem if names[stem] == 1 else f"{repo.split('/')[0]}--{stem}"
        if len(parts) == 1 and mmproj is None:
            model = out / f"{name}.gguf"
            plan.links.append((model, parts[0].blob_path))
        else:
            for p in parts:
                plan.links.append((out / name / Path(p.filename).name, p.blob_path))
            if mmproj is not None:
                plan.links.append((out / name / Path(mmproj.filename).name, mmproj.blob_path))
            model = out / name / Path(parts[0].filename).name
        # a name the INI file cannot carry keeps the server's settings
        got = presets([p.blob_path for p in parts]) if presets and not re.search(r"[]\[;#\n]", name) else None
        if got:
            sections.append((name, model, got[0], got[1]))
            plan.presets[name] = dict(got[0])
    plan.files.append((out / PRESETS, presets_text(sections)))     # always there: the server needs the file
    return plan


def comfy_folder(f: CachedFile) -> str | None:
    path = f.filename.replace("\\", "/")
    low = path.lower()
    if not low.endswith(COMFY_EXT):
        return None
    m = re.search(r"(?:^|/)split_files/([a-z_]+)/", low)
    if m:
        folder = m.group(1)
        return {"unet": "diffusion_models", "clip": "text_encoders"}.get(folder, folder)
    # Comfy-Org's newer repackages keep ComfyUI's own folders at the top (diffusion_models/…,
    # text_encoders/…, vae/…); a diffusers repository also has vae/, with diffusion_pytorch_model*
    top = low.split("/", 1)[0] if "/" in low else ""
    if top in COMFY_FOLDERS and low.count("/") == 1 and not Path(low).name.startswith("diffusion_pytorch_model"):
        return top
    entry = match_catalog(f"{f.repo}/{f.filename}")
    media = (entry is not None and entry.get("kind") in ("image", "video")) or \
        any(h in f.repo.lower() for h in MEDIA_HINTS)
    if not media or "/" in path:
        return None       # not a media repo, or a diffusers sub-folder (sharded; ComfyUI loads single files)
    name = low
    if "lora" in name:
        return "loras"
    if "clip_vision" in name or "image_encoder" in name:
        return "clip_vision"
    if "vae" in name or name in ("ae.safetensors", "ae.sft"):
        return "vae"
    if any(k in name for k in ("text_encoder", "t5xxl", "umt5", "clip_l", "clip_g", "qwen_2.5_vl", "llava")):
        return "text_encoders"
    if "controlnet" in name:
        return "controlnet"
    if "upscale" in name or "esrgan" in name:
        return "upscale_models"
    if "embedding" in name:
        return "embeddings"
    return "diffusion_models"


def comfy_plan(files: list[CachedFile], out: Path) -> Plan:
    plan = Plan()
    used: set[Path] = set()
    for f in files:
        folder = comfy_folder(f)
        if not folder:
            continue
        link = out / folder / Path(f.filename).name
        if link in used:
            link = out / folder / f"{f.repo.split('/')[0]}--{Path(f.filename).name}"
        used.add(link)
        plan.links.append((link, f.blob_path))
    lines = [f"# {MARK} by `sos models views` — regenerate instead of editing.",
             "# ComfyUI: python main.py --extra-model-paths-config " + str(out / "extra_model_paths.yaml"),
             "svoya:", f"    base_path: {out}/", "    is_default: false"]
    for folder in COMFY_FOLDERS:
        lines.append(f"    {folder}: {folder}/")
    plan.files.append((out / "extra_model_paths.yaml", "\n".join(lines) + "\n"))
    return plan


def ollama_name(filename: str) -> str:
    stem = _stem(filename).lower()
    m = re.search(r"[-_.](i?q\d[\w]*|f16|bf16|f32|q8_0)$", stem)
    base, tag = (stem[: m.start()], m.group(1)) if m else (stem, "latest")
    base = re.sub(r"[^a-z0-9._-]+", "-", base).strip("-._") or "model"
    return f"{base}:{tag}"


def ollama_plan(files: list[CachedFile], out: Path) -> Plan:
    plan = Plan()
    script = ["#!/usr/bin/env bash", f"# {MARK} by `sos models views` — review, then run: bash {out}/import.sh",
              "set -euo pipefail"]
    for f in files:
        fn = Path(f.filename).name.lower()
        if not fn.endswith(".gguf") or "mmproj" in fn:
            continue
        m = SHARD.search(fn)
        if m and m.group(1) != "00001":
            continue
        if m:
            plan.notes.append(f"{f.repo}/{f.filename}: split GGUF — merge with llama-gguf-split first for Ollama")
            continue
        name = ollama_name(f.filename)
        mf = out / f"{name.replace(':', '--')}.Modelfile"
        plan.files.append((mf, f"# {MARK}\nFROM {f.blob_path}\n"))
        cmd = f"ollama create {name} -f {mf}"
        plan.commands.append(cmd)
        script.append(cmd)
    plan.files.append((out / "import.sh", "\n".join(script) + "\n"))
    return plan


def apply(plan: Plan, root: Path, dry_run: bool = False) -> dict:
    """Create links/files; remove stale symlinks under ``root`` that point into the store."""
    wanted = {link for link, _ in plan.links}
    stale: list[Path] = []
    if root.is_dir():
        for dirpath, _dirs, fns in os.walk(root):
            for fn in fns:
                p = Path(dirpath) / fn
                if p.is_symlink() and p not in wanted:
                    stale.append(p)
    made = 0
    if not dry_run:
        for p in stale:
            p.unlink(missing_ok=True)
        for link, target in plan.links:
            link.parent.mkdir(parents=True, exist_ok=True)
            if link.is_symlink() and Path(os.readlink(link)) == target:
                continue
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(target)
            made += 1
        for path, content in plan.files:
            path.parent.mkdir(parents=True, exist_ok=True)
            # whole or not at all (a server starting meanwhile reads the old file), and into a
            # folder shared by the group ai: replacing needs the folder's permission only
            fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.chmod(tmp, 0o664)
                os.replace(tmp, path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
        # remove now-empty model dirs
        for dirpath, dirs, fns in sorted(os.walk(root), key=lambda x: -len(x[0])) if root.is_dir() else []:
            if dirpath != str(root) and not dirs and not fns:
                os.rmdir(dirpath)
    return {"links": len(plan.links), "created": made, "stale": [str(p) for p in stale],
            "files": [str(p) for p, _ in plan.files], "commands": plan.commands, "notes": plan.notes,
            "presets": plan.presets}
