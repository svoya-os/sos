# SPDX-License-Identifier: Apache-2.0
"""freedesktop.org Trash (home trash). Jackson never hard-deletes: it moves to the trash,
so the user can also restore from the file manager."""

from __future__ import annotations

import datetime as dt
import errno
import os
import shutil
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class TrashEntry:
    original: str
    files_path: str
    info_path: str
    deleted_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrashEntry":
        return cls(str(data["original"]), str(data["files_path"]), str(data["info_path"]),
                   str(data.get("deleted_at", "")))


class Trash:
    def __init__(self, trash_dir: Path) -> None:
        self.dir = trash_dir
        self.files = trash_dir / "files"
        self.info = trash_dir / "info"

    def _ensure(self) -> None:
        for d in (self.dir, self.files, self.info):
            d.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(d, 0o700)
            except OSError:
                pass

    def _reserve(self, name: str, original: Path, when: dt.datetime) -> tuple[Path, Path]:
        stem, suffix = os.path.splitext(name)
        for n in range(1, 10_000):
            candidate = name if n == 1 else f"{stem}.{n}{suffix}"
            info_path = self.info / f"{candidate}.trashinfo"
            try:
                fd = os.open(info_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                continue
            if (self.files / candidate).exists():
                os.close(fd)
                os.unlink(info_path)
                continue
            body = ("[Trash Info]\n"
                    f"Path={urllib.parse.quote(str(original), safe='/')}\n"
                    f"DeletionDate={when.strftime('%Y-%m-%dT%H:%M:%S')}\n")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(body)
            return self.files / candidate, info_path
        raise OSError(errno.EEXIST, "too many files with the same name in the trash")

    def put(self, path: Path, copy: bool = False) -> TrashEntry:
        """Move *path* to the trash (or copy it there, keeping the original)."""
        path = Path(os.path.abspath(path))
        if not path.exists() and not path.is_symlink():
            raise FileNotFoundError(str(path))
        self._ensure()
        when = dt.datetime.now()
        target, info_path = self._reserve(path.name or "unnamed", path, when)
        try:
            if copy:
                if path.is_dir() and not path.is_symlink():
                    shutil.copytree(path, target, symlinks=True)
                else:
                    shutil.copy2(path, target, follow_symlinks=False)
            else:
                try:
                    os.rename(path, target)
                except OSError as exc:
                    if exc.errno != errno.EXDEV:
                        raise
                    shutil.move(str(path), str(target))  # other filesystem: copy, then remove original
        except BaseException:
            try:
                os.unlink(info_path)
            except OSError:
                pass
            raise
        return TrashEntry(str(path), str(target), str(info_path), when.isoformat(timespec="seconds"))

    def exists(self, entry: TrashEntry) -> bool:
        return os.path.lexists(entry.files_path)

    def restore(self, entry: TrashEntry, dest: Path | None = None, overwrite: bool = False) -> Path:
        dest = Path(dest or entry.original)
        if not os.path.lexists(entry.files_path):
            raise FileNotFoundError(f"{entry.files_path} is no longer in the trash")
        if os.path.lexists(dest):
            if not overwrite:
                raise FileExistsError(str(dest))
            if dest.is_dir() and not dest.is_symlink():
                raise IsADirectoryError(str(dest))
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(entry.files_path, dest) if overwrite else os.rename(entry.files_path, dest)
        except OSError as exc:
            if exc.errno != errno.EXDEV:
                raise
            shutil.move(entry.files_path, str(dest))
        try:
            os.unlink(entry.info_path)
        except OSError:
            pass
        return dest
