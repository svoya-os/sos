"""User-level undo journal: changes that need no btrfs snapshot (the look: theme, accent).

``~/.local/state/svoya/undo.json``::

    {"seq": 12, "entries": [{"id": "look-12", "kind": "look", "at": "2026-09-25T10:11:12Z",
                             "description": {"en": "accent Lilac", "ru": "акцент Сирень"},
                             "before": {"theme": "auto", "accent": null},
                             "after":  {"theme": "auto", "accent": "lilac"}, "system": false}]}

``sos undo`` takes the newest change of all — a journal entry or an sos snapshot pair, whichever is
newer; ``sos undo look-12`` names one. Undoing an entry removes it (the journal is a stack).
"""
from __future__ import annotations

import datetime as dt
import fcntl
import re
from contextlib import contextmanager
from typing import Iterator

from .paths import Paths
from .util import iso, read_json, write_json

MAX_ENTRIES = 50
ID_RE = re.compile(r"^[a-z]+-\d+$")


def path(paths: Paths):
    return paths.state_dir / "undo.json"


def is_id(text: str | None) -> bool:
    return bool(text) and bool(ID_RE.match(str(text))) and not str(text).startswith("snap-")


@contextmanager
def _locked(paths: Paths) -> Iterator[dict]:
    p = path(paths)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p.with_name("undo.lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = read_json(p) or {}
        if not isinstance(data.get("entries"), list):
            data = {"seq": 0, "entries": []}
        yield data
        write_json(p, data)


def entries(paths: Paths) -> list[dict]:
    data = read_json(path(paths)) or {}
    return [e for e in data.get("entries", []) if isinstance(e, dict) and is_id(e.get("id"))]


def newest(paths: Paths) -> dict | None:
    e = entries(paths)
    return e[-1] if e else None


def find(paths: Paths, entry_id: str) -> dict | None:
    return next((e for e in entries(paths) if e["id"] == entry_id), None)


def push(paths: Paths, kind: str, *, before: dict, after: dict, description: dict, now: dt.datetime,
         system: bool = False) -> dict:
    with _locked(paths) as data:
        data["seq"] = int(data.get("seq", 0)) + 1
        entry = {"id": f"{kind}-{data['seq']}", "kind": kind, "at": iso(now), "description": description,
                 "before": before, "after": after, "system": system}
        data["entries"] = (data["entries"] + [entry])[-MAX_ENTRIES:]
    return entry


def remove(paths: Paths, entry_id: str) -> None:
    with _locked(paths) as data:
        data["entries"] = [e for e in data["entries"] if e.get("id") != entry_id]
