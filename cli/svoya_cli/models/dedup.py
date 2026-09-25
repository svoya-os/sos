"""Find duplicate model files by content hash; on btrfs replace copies with reflinks.

Size groups first (cheap), then a 1 MiB head+tail probe, then full sha256 (cached in the registry by
path/size/mtime/inode). Files that are already hardlinks of each other are not duplicates.
Reflink: ``cp --reflink=always --preserve=all <keep> <dup>.svoya-tmp && mv`` — atomic, same filesystem
only; content is re-verified right before the swap, so a changed file is never replaced.
"""
from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

MIN_SIZE = 16 * 2**20
PROBE = 2**20


@dataclass
class DupGroup:
    sha256: str
    size: int
    files: list[Path]

    @property
    def wasted(self) -> int:
        return self.size * (len(self.files) - 1)


def _probe(path: Path, size: int) -> bytes:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read(PROBE))
        if size > 2 * PROBE:
            f.seek(size - PROBE)
            h.update(f.read(PROBE))
    return h.digest()


def full_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(8 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def walk(roots: list[Path], min_size: int = MIN_SIZE) -> list[tuple[Path, os.stat_result]]:
    out = []
    seen: set[tuple[int, int]] = set()
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirs, files in os.walk(root, followlinks=False):
            # sorted: filesystem order differs between machines; with hardlinks the first path wins
            dirs[:] = sorted(d for d in dirs if d not in (".locks", "views", ".snapshots"))
            for fn in sorted(files):
                p = Path(dirpath) / fn
                try:
                    st = p.lstat()
                except OSError:
                    continue
                if not (st.st_mode & 0o170000 == 0o100000) or st.st_size < min_size:
                    continue          # regular files only (no symlinks), big enough to matter
                if fn.endswith((".incomplete", ".svoya-tmp", ".lock")):
                    continue
                key = (st.st_dev, st.st_ino)
                if key in seen:
                    continue          # hardlink of a file already listed
                seen.add(key)
                out.append((p, st))
    return out


def find(roots: list[Path], *, min_size: int = MIN_SIZE, cached: Callable | None = None,
         store: Callable | None = None) -> list[DupGroup]:
    by_size: dict[int, list[tuple[Path, os.stat_result]]] = defaultdict(list)
    for p, st in walk(roots, min_size):
        by_size[st.st_size].append((p, st))
    groups: list[DupGroup] = []
    for size, items in by_size.items():
        if len(items) < 2:
            continue
        by_probe: dict[bytes, list[tuple[Path, os.stat_result]]] = defaultdict(list)
        for p, st in items:
            try:
                by_probe[_probe(p, size)].append((p, st))
            except OSError:
                continue
        for cands in by_probe.values():
            if len(cands) < 2:
                continue
            by_hash: dict[str, list[Path]] = defaultdict(list)
            for p, st in cands:
                sha = cached(p, st) if cached else None
                if not sha:
                    try:
                        sha = full_hash(p)
                    except OSError:
                        continue
                    if store:
                        store(p, st, sha)
                by_hash[sha].append(p)
            for sha, paths in by_hash.items():
                if len(paths) > 1:
                    groups.append(DupGroup(sha, size, sorted(paths)))
    return sorted(groups, key=lambda g: -g.wasted)


def reflink_group(g: DupGroup, runner, *, dry_run: bool = False) -> list[tuple[Path, bool, str]]:
    """Keep the first file, replace the others with reflinks of it (same filesystem only)."""
    keep = g.files[0]
    results = []
    try:
        dev = keep.stat().st_dev
    except OSError as e:
        return [(p, False, str(e)) for p in g.files[1:]]
    for dup in g.files[1:]:
        try:
            if dup.stat().st_dev != dev:
                results.append((dup, False, "different filesystem"))
                continue
        except OSError as e:
            results.append((dup, False, str(e)))
            continue
        tmp = dup.with_name(dup.name + ".svoya-tmp")
        if dry_run:
            runner.run(["cp", "--reflink=always", "--preserve=all", str(keep), str(tmp)], mutating=True)
            runner.run(["mv", "-f", str(tmp), str(dup)], mutating=True)
            results.append((dup, True, "dry-run"))
            continue
        if full_hash(dup) != g.sha256 or full_hash(keep) != g.sha256:
            results.append((dup, False, "content changed since scan"))
            continue
        r = runner.run(["cp", "--reflink=always", "--preserve=all", str(keep), str(tmp)], timeout=600, mutating=True)
        if not r.ok:
            tmp.unlink(missing_ok=True)
            results.append((dup, False, (r.err.strip() or "cp failed") + " (not btrfs/xfs?)"))
            continue
        r = runner.run(["mv", "-f", str(tmp), str(dup)], timeout=60, mutating=True)
        results.append((dup, r.ok, "" if r.ok else r.err.strip()))
    return results
