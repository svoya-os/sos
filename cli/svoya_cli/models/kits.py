"""Kits: the files one ComfyUI graph loads together, from several repositories.

A kit (``data/model_catalog.toml`` ``[[kit]]``) is what «Джексон, нарисуй …» needs: FLUX.2 [klein] 4B
is a diffusion model, a text encoder and an autoencoder, each published in its own repository.
``sos models pull <kit>`` (or ``sos install <kit>``, ``sos install draw``) downloads the missing
ones into the store, and ``views.comfy_plan`` links them where the Studio's ComfyUI finds them —
under the names Jackson's graphs load (``jackson/draw.py``).
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import hfcache, views

_cache: list["Kit"] | None = None


@dataclass(frozen=True)
class KitFile:
    repo: str
    file: str                          # path inside the repository
    alt: tuple[str, ...] = ()          # other repositories with the same file, tried in order

    @property
    def name(self) -> str:
        return Path(self.file).name

    @property
    def folder(self) -> str:
        """The ComfyUI folder the view links it into (diffusion_models, text_encoders, vae…)."""
        probe = hfcache.CachedFile(self.repo, "model", "", self.file, Path(), Path(), 0, "")
        return views.comfy_folder(probe) or "diffusion_models"


@dataclass(frozen=True)
class Kit:
    id: str
    name: str
    kind: str
    model: str                         # the [[model]] entry whose license applies
    files: tuple[KitFile, ...]
    aliases: tuple[str, ...] = ()
    vram_gb: float | None = None
    default: bool = False


def kits(data_dir: Path | None = None) -> list[Kit]:
    global _cache
    if _cache is not None and data_dir is None:
        return _cache
    base = data_dir or Path(__file__).resolve().parent.parent / "data"
    with open(base / "model_catalog.toml", "rb") as f:
        raw = tomllib.load(f).get("kit", [])
    out = []
    for k in raw:
        files = tuple(KitFile(str(x["repo"]), str(x["file"]), tuple(x.get("alt", []))) for x in k.get("files", []))
        out.append(Kit(id=str(k["id"]), name=str(k.get("name", k["id"])), kind=str(k.get("kind", "image")),
                       model=str(k.get("model", k["id"])), files=files,
                       aliases=tuple(str(a) for a in k.get("aliases", [])),
                       vram_gb=float(k["vram_gb"]) if k.get("vram_gb") is not None else None,
                       default=bool(k.get("default"))))
    if data_dir is None:
        _cache = out
    return out


def resolve(name: str, data_dir: Path | None = None) -> Kit | None:
    """A kit by id or alias (case does not matter)."""
    n = name.strip().lower()
    for k in kits(data_dir):
        if n == k.id.lower() or n in (a.lower() for a in k.aliases):
            return k
    return None


def default(kind: str = "image", data_dir: Path | None = None) -> Kit | None:
    return next((k for k in kits(data_dir) if k.kind == kind and k.default), None)


def present(files: list[hfcache.CachedFile], kit: Kit) -> dict[str, hfcache.CachedFile | None]:
    """Which of the kit's files are in the store, by file name. Any repository counts when the
    file lands in the same ComfyUI folder under the same name (Z-Image and klein share
    ``qwen_3_4b.safetensors``): that is what ComfyUI loads."""
    found: dict[str, hfcache.CachedFile | None] = {}
    for kf in kit.files:
        own = (kf.repo, *kf.alt)
        exact = [c for c in files if c.repo in own and c.filename == kf.file]
        same = exact or [c for c in files if Path(c.filename).name == kf.name
                         and views.comfy_folder(c) == kf.folder]
        found[kf.name] = same[0] if same else None
    return found


def status(ai_root: Path, kit: Kit, studio: bool | None = None, built: bool | None = None) -> dict:
    """``sos models kits --json`` row: what is there, what is missing. ``complete``: the files;
    ``ready``: the files, the Studio (``sos-studio``) and its container, so «нарисуй» works."""
    have = present(hfcache.scan(ai_root / "hub"), kit)
    rows = [{"file": kf.name, "folder": kf.folder, "repo": kf.repo, "present": have[kf.name] is not None,
             "sizeBytes": have[kf.name].size if have[kf.name] is not None else None} for kf in kit.files]
    complete = all(r["present"] for r in rows)
    return {"id": kit.id, "name": kit.name, "kind": kit.kind, "model": kit.model, "default": kit.default,
            "vramGb": kit.vram_gb, "aliases": list(kit.aliases), "files": rows, "complete": complete,
            "studio": studio, "built": built, "ready": complete and studio is not False and built is not False}
