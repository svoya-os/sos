# SPDX-License-Identifier: Apache-2.0
"""Undo registry: every reversible action Jackson takes gets an id (``a-3f9c2e``).

Records are kept in ``actions.jsonl`` (append-only). File actions keep the trash location of
the previous version and content hashes, so an undo never clobbers a file the user changed
afterwards. System-level undo goes through ``svoya undo`` (or snapper).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import secrets
import shutil
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from .i18n import t
from .svoya import Snapshot, SvoyaCli
from .tools.base import UndoSpec
from .trash import Trash, TrashEntry


def file_sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, IsADirectoryError):
        return None


@dataclass
class Action:
    id: str
    ts: str
    kind: str
    summary: str
    data: dict[str, Any]
    turn: str = ""
    client: str = ""
    reversible: bool = True
    auto: bool = False
    undone: bool = False
    undone_ts: str = ""


@dataclass
class UndoOutcome:
    ok: bool
    message: str
    action: Action | None = None
    details: dict[str, Any] = field(default_factory=dict)


class UndoError(Exception):
    """An undo that cannot be done safely; rendered in the user's language."""

    def __init__(self, key: str, **kwargs: Any) -> None:
        super().__init__(key)
        self.key = key
        self.kwargs = kwargs

    def render(self, lang: str) -> str:
        return t(self.key, lang, **self.kwargs)


Handler = Callable[[Action], str]


class UndoLog:
    def __init__(self, path: Path, trash: Trash, svoya: SvoyaCli | None = None, audit: Any = None) -> None:
        self.path = path
        self.trash = trash
        self.svoya = svoya
        self.audit = audit
        self._lock = threading.RLock()
        self.handlers: dict[str, Handler] = {
            "fs.create": self._undo_create,
            "fs.overwrite": self._undo_overwrite,
            "fs.move": self._undo_move,
            "fs.trash": self._undo_trash,
            "snapshot": self._undo_snapshot,
        }

    def register_handler(self, kind: str, handler: Handler) -> None:
        self.handlers[kind] = handler

    # ------------------------------------------------------------------
    def _append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def _load(self) -> dict[str, Action]:
        actions: dict[str, Action] = {}
        try:
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    if rec.get("op") == "add" and isinstance(rec.get("action"), dict):
                        a = rec["action"]
                        try:
                            actions[a["id"]] = Action(**{k: v for k, v in a.items()
                                                         if k in Action.__dataclass_fields__})
                        except TypeError:
                            continue
                    elif rec.get("op") == "undone" and rec.get("id") in actions:
                        actions[rec["id"]].undone = True
                        actions[rec["id"]].undone_ts = rec.get("ts", "")
        except FileNotFoundError:
            pass
        return actions

    def register(self, spec: UndoSpec, turn: str = "", client: str = "", reversible: bool = True) -> Action:
        with self._lock:
            existing = self._load()
            while True:
                aid = "a-" + secrets.token_hex(3)
                if aid not in existing:
                    break
            action = Action(aid, dt.datetime.now().isoformat(timespec="seconds"), spec.kind, spec.summary,
                            spec.data, turn, client, reversible, spec.auto)
            self._append({"op": "add", "action": asdict(action)})
        return action

    def get(self, action_id: str) -> Action | None:
        with self._lock:
            return self._load().get(action_id)

    def list(self, limit: int = 20, include_undone: bool = True) -> list[Action]:
        with self._lock:
            items = list(self._load().values())
        items.reverse()
        if not include_undone:
            items = [a for a in items if not a.undone]
        return items[:limit]

    def last(self) -> Action | None:
        for a in self.list(limit=10_000, include_undone=False):
            if a.reversible and not a.auto:
                return a
        return None

    def undo(self, action_id: str | None = None, lang: str = "ru") -> UndoOutcome:
        with self._lock:
            action = self.get(action_id) if action_id else self.last()
            if action is None:
                key = "undo.not_found" if action_id else "err.no_undo"
                return UndoOutcome(False, t(key, lang, id=action_id or ""))
            if action.undone:
                return UndoOutcome(False, t("undo.already", lang, id=action.id), action)
            if not action.reversible:
                return UndoOutcome(False, t("undo.irreversible", lang, id=action.id), action)
            handler = self.handlers.get(action.kind)
            if handler is None:
                return UndoOutcome(False, t("undo.no_handler", lang, kind=action.kind), action)
            try:
                detail = handler(action)
            except UndoError as exc:
                message = exc.render(lang)
            except OSError as exc:
                message = f"{exc.__class__.__name__}: {exc}"
            else:
                self._append({"op": "undone", "id": action.id,
                              "ts": dt.datetime.now().isoformat(timespec="seconds")})
                action.undone = True
                if self.audit is not None:
                    self.audit.append("undo", action=action.id, actionKind=action.kind, ok=True, detail=detail)
                return UndoOutcome(True, t("undo.done", lang, summary=action.summary), action,
                                   {"detail": detail})
            if self.audit is not None:
                self.audit.append("undo", action=action.id, actionKind=action.kind, ok=False, error=message)
            return UndoOutcome(False, t("undo.failed", lang, why=message), action)

    # ------------------------------------------------------------------
    # built-in handlers

    def _check_unchanged(self, path: Path, expected: str | None) -> None:
        current = file_sha256(path)
        if expected and current != expected:
            raise UndoError("undo.changed", path=str(path))

    def _undo_create(self, a: Action) -> str:
        path = Path(a.data["path"])
        if not path.exists():
            return f"{path}: already gone"
        self._check_unchanged(path, a.data.get("sha256"))
        entry = self.trash.put(path)
        return f"{path} → {entry.files_path}"

    def _undo_overwrite(self, a: Action) -> str:
        path = Path(a.data["path"])
        prev = TrashEntry.from_dict(a.data["prev_trash"])
        if not self.trash.exists(prev):
            raise UndoError("undo.prev_gone", name=path.name)
        if path.exists():
            self._check_unchanged(path, a.data.get("sha256"))
            self.trash.put(path)
        self.trash.restore(prev, dest=path)
        restored = file_sha256(path)
        if a.data.get("prev_sha256") and restored != a.data["prev_sha256"]:
            raise UndoError("undo.hash", path=str(path))
        return f"{prev.files_path} → {path}"

    def _undo_move(self, a: Action) -> str:
        src, dst = Path(a.data["src"]), Path(a.data["dst"])
        if os.path.lexists(src):
            raise UndoError("undo.exists", path=str(src))
        if not os.path.lexists(dst):
            raise UndoError("undo.missing", path=str(dst))
        src.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dst), str(src))
        if a.data.get("dst_prev_trash"):
            self.trash.restore(TrashEntry.from_dict(a.data["dst_prev_trash"]), dest=dst)
        return f"{dst} → {src}"

    def _undo_trash(self, a: Action) -> str:
        entry = TrashEntry.from_dict(a.data["entry"])
        if os.path.lexists(entry.original):
            raise UndoError("undo.exists", path=entry.original)
        if not self.trash.exists(entry):
            raise UndoError("undo.prev_gone", name=Path(entry.original).name)
        self.trash.restore(entry)
        return f"{entry.files_path} → {entry.original}"

    def _undo_snapshot(self, a: Action) -> str:
        if self.svoya is None:
            raise UndoError("undo.no_system")
        ok, out = self.svoya.undo(Snapshot(str(a.data.get("id", "")), str(a.data.get("tool", "svoya"))))
        if not ok:
            raise UndoError("undo.system_failed", why=out)
        return out
