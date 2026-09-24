"""The Hugging Face cache layout under ``/srv/ai/hub`` (``HF_HOME=/srv/ai``) — the single source of truth.

::

    hub/models--org--name/
        blobs/<etag>                      content (etag = sha256 for LFS/Xet files)
        refs/main                         commit hash
        snapshots/<commit>/<path>         relative symlink → ../../blobs/<etag>
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass
class CachedFile:
    repo: str
    repo_type: str
    commit: str
    filename: str            # path inside the repo
    snapshot_path: Path
    blob_path: Path
    size: int
    etag: str

    @property
    def sha256(self) -> str | None:
        return self.etag if SHA256.match(self.etag) else None


def repo_dir(hub: Path, repo: str, repo_type: str = "model") -> Path:
    return hub / f"{repo_type}s--{repo.replace('/', '--')}"


def _repo_from_dir(name: str) -> tuple[str, str] | None:
    m = re.match(r"^(model|dataset|space)s--(.+)$", name)
    if not m:
        return None
    return m.group(1), m.group(2).replace("--", "/", 1)


def scan(hub: Path, repo_types: tuple[str, ...] = ("model",)) -> list[CachedFile]:
    out: list[CachedFile] = []
    try:
        repos = sorted(hub.iterdir())
    except OSError:
        return out
    for rd in repos:
        parsed = _repo_from_dir(rd.name)
        if not parsed or parsed[0] not in repo_types:
            continue
        rtype, repo = parsed
        snaps = rd / "snapshots"
        try:
            commits = sorted(snaps.iterdir())
        except OSError:
            continue
        for cdir in commits:
            for dirpath, _dirs, files in os.walk(cdir):
                for fn in files:
                    sp = Path(dirpath) / fn
                    if not sp.is_symlink():
                        blob = sp
                        etag = ""
                    else:
                        blob = (sp.parent / os.readlink(sp)).resolve()
                        etag = blob.name
                    try:
                        size = blob.stat().st_size
                    except OSError:
                        continue          # dangling link (blob removed)
                    out.append(CachedFile(repo=repo, repo_type=rtype, commit=cdir.name,
                                          filename=str(sp.relative_to(cdir)), snapshot_path=sp,
                                          blob_path=blob, size=size, etag=etag))
    return out


def add_file(hub: Path, repo: str, commit: str, filename: str, src: Path, etag: str,
             revision: str | None = "main") -> Path:
    """Move a finished download into the cache: ``blobs/<etag>`` + snapshot symlink + ref."""
    rd = repo_dir(hub, repo)
    blob = rd / "blobs" / etag
    blob.parent.mkdir(parents=True, exist_ok=True)
    if blob.exists():
        if src.resolve() != blob.resolve():
            src.unlink(missing_ok=True)
    else:
        os.replace(src, blob)
    snap = rd / "snapshots" / commit / filename
    snap.parent.mkdir(parents=True, exist_ok=True)
    rel = os.path.relpath(blob, snap.parent)
    if snap.is_symlink() or snap.exists():
        snap.unlink()
    snap.symlink_to(rel)
    if revision and revision != commit:
        ref = rd / "refs" / revision
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_text(commit)
    return snap


def blob_dest(hub: Path, repo: str, etag: str) -> Path:
    return repo_dir(hub, repo) / "blobs" / etag


def remove_repo(hub: Path, repo: str, dry_run: bool = False) -> list[Path]:
    rd = repo_dir(hub, repo)
    if not rd.exists():
        return []
    if not dry_run:
        shutil.rmtree(rd)
    return [rd]


def remove_file(hub: Path, cf: CachedFile, all_files: list[CachedFile], dry_run: bool = False) -> list[Path]:
    """Remove one snapshot entry; its blob goes too when nothing else in the repo points at it."""
    removed = [cf.snapshot_path]
    still_used = any(o.blob_path == cf.blob_path and o.snapshot_path != cf.snapshot_path for o in all_files)
    if not still_used and cf.blob_path != cf.snapshot_path:
        removed.append(cf.blob_path)
    if not dry_run:
        for p in removed:
            try:
                p.unlink()
            except OSError:
                pass
    return removed
